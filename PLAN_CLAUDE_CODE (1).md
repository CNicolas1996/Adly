# PLAN CLAUDE CODE — Adly Chat GUI Fixes
# Sesión: fixes funcionales + tablas estructuradas
# Directorio raíz: C:\Users\moonw\Proyectos\Adly
# Fecha: 2026-05-02

---

## CONTEXTO

Adly es un chatbot de analytics de marketing. Tiene:
- Backend: FastAPI + Python en `src/`
- Frontend: React + Vite en `interfaces/web/src/`
- CLI: Rich + Python en `interfaces/cli/`

El chat GUI está conectado al engine real (`VITE_MOCK=false`).
El backend corre en `http://localhost:8000`.
El frontend corre en `http://localhost:5173`.

---

## ARQUITECTURA DEL CHAT

```
Usuario escribe → POST /api/chat → chat.py
  ├── Si empieza con "/" → comando
  │   ├── /ayuda → command_bridge.py → markdown
  │   ├── /alertas, /metricas → handlers especiales
  │   ├── /rfm, /cohorts, /embudo, /velocidad, /rentabilidad → capturar_cmd()
  │   └── resto → _build_registry() → capturar_cmd()
  ├── Si es lenguaje natural → query_engine.py → pandas → LLM
  └── LLM → RespuestaAdly (tipo: texto|tabla|lista)

Frontend recibe JSON:
  { content: str, table: list|null, confidence: float, ... }
  
  content → Message.jsx → ContentRenderer
    ├── isRichTable() → <pre> monospace
    ├── isMarkdown() → MarkdownRenderer
    └── texto plano → inline
  table → DataTable.jsx → tabla HTML con headers naranjas
```

---

## ARCHIVOS CLAVE

| Archivo | Ruta | Estado |
|---|---|---|
| chat.py | `src/api/routes/chat.py` | ⚠️ bugs menores |
| command_bridge.py | `src/api/command_bridge.py` | ✅ |
| query_engine.py | `src/processing/query_engine.py` | ✅ |
| commands.py | `interfaces/cli/commands.py` | ✅ |
| theme.py | `interfaces/cli/theme.py` | ✅ (console global) |
| Message.jsx | `interfaces/web/src/components/chat/Message.jsx` | ✅ |
| DataTable.jsx | `interfaces/web/src/components/chat/DataTable.jsx` | ✅ |
| InputZone.jsx | `interfaces/web/src/components/chat/InputZone.jsx` | no tocar |

---

## BUG 1 — /alertas y /metricas no responden (CRÍTICO)

**Síntoma:** `/alertas` y `/metricas` responden "❓ Comando no reconocido"
**Causa:** El bloque de `/alertas` en `chat.py` línea ~251 tiene un `try/except`
que en caso de error solo hace `print()` sin `return` — cae al registry
donde no están registrados.

**Fix en `src/api/routes/chat.py`:**

Busca el bloque de `/alertas` (~línea 250) y agrégale `return` en el except:

```python
        if cmd_base == "/alertas" and df is not None:
            try:
                from src.processing.alerts import DataValidator as AlertValidator
                manager = AlertValidator(df)
                manager.validate()
                lines = []
                for a in manager.alertas:
                    icon = "❌" if a.nivel.value == "critica" else "⚠️" if a.nivel.value == "advertencia" else "✅"
                    lines.append(f"{icon} **{a.nivel.value.upper()}** — {a.mensaje}")
                    lines.append(f"   → {a.recomendacion}")
                content = "\n".join(lines) if lines else "✅ Datos en buen estado."
                return _save_and_return(analysis_id, _bot_msg(
                    content = content,
                    note    = "Validación de integridad del dataset",
                ))
            except Exception as e:
                print(f"[chat] Error /alertas: {e}")
                return _save_and_return(analysis_id, _bot_msg(  # ← AGREGAR ESTE RETURN
                    content = f"⚠️ Error ejecutando /alertas: {e}",
                    confidence = 0.5,
                ))
```

Mismo fix para `/metricas` (~línea 229) — agregar `return` en el except.

---

## BUG 2 — Tablas ASCII de Rich en vez de DataTable (IMPORTANTE)

**Síntoma:** `/head`, `/rfm`, `/cohorts`, `/embudo`, `/columnas` muestran
tablas ASCII monospace en vez del componente DataTable bonito.

**Causa:** `capturar_cmd()` retorna el output de Rich como string → va a
`content` del mensaje → `ContentRenderer` lo detecta como `isRichTable()` →
renderiza como `<pre>`. Pero `DataTable` necesita `table: list[dict]`.

**Solución — dos partes:**

### Parte A — Backend: parsear output de Rich a tabla estructurada

En `src/api/routes/chat.py`, modifica la función `capturar_cmd()` para que
además del output de Rich, intente extraer datos estructurados:

NO tocar `capturar_cmd`. En cambio, crear función `_rich_to_table(output: str) -> list | None`:

```python
def _rich_to_table(output: str) -> list | None:
    """
    Intenta parsear una tabla ASCII de Rich a list[dict] para DataTable.
    Detecta líneas de datos entre las líneas de separadores (─).
    Retorna None si no puede parsear.
    """
    if not output:
        return None
    
    lineas = output.split('\n')
    # Filtrar líneas de borde (┌┐└┘│─) y líneas vacías
    datos = []
    headers = None
    
    for linea in lineas:
        # Saltar bordes de caja
        if any(c in linea for c in '┌┐└┘'):
            continue
        # Saltar separadores
        if '─' in linea and '│' not in linea:
            continue
        # Extraer contenido entre │
        if '│' in linea:
            # Remover │ del inicio y fin, split por espacios múltiples
            contenido = linea.strip().strip('│').strip()
            if not contenido:
                continue
            # Separar columnas por 2+ espacios
            import re
            cols = [c.strip() for c in re.split(r'\s{2,}', contenido) if c.strip()]
            if not cols:
                continue
            # Primera fila válida = headers (todo uppercase o primera después de borde)
            if headers is None:
                headers = cols
                continue
            # Línea de separación entre header y datos
            if all(c.startswith('─') or c == '' for c in cols):
                continue
            # Fila de datos
            if len(cols) >= len(headers):
                fila = {}
                for i, h in enumerate(headers):
                    fila[h] = cols[i] if i < len(cols) else '—'
                datos.append(fila)
    
    return datos if len(datos) > 0 and headers else None
```

Luego en el bloque del registry donde se construye el bot_msg, usar esto:

```python
                # Intentar convertir tabla ASCII a DataTable estructurada
                table_data = _rich_to_table(content) if content else None
                
                return _save_and_return(analysis_id, _bot_msg(
                    content   = "" if table_data else content,  # vacío si hay tabla
                    freshness = "datos locales",
                    note      = "Resultado directo del análisis",
                    table     = table_data,
                ))
```

### Parte B — Frontend: mostrar DataTable cuando hay tabla, ocultar content vacío

En `interfaces/web/src/components/chat/Message.jsx`, el `ContentRenderer`
ya maneja esto — si llega `table` en el mensaje, `DataTable` lo renderiza.
Si `content` es vacío string, `ContentRenderer` no muestra nada.

Verificar que en `Message.jsx` el orden sea:
1. `ContentRenderer` con `content`  
2. `DataTable` con `table`

Ya está así. No tocar.

---

## BUG 3 — Intent "calcula" no matchea suma (MENOR)

**Síntoma:** "calcula el revenue por utm_ad" → "No hay datos"
**Causa:** `_detectar_intent` en `query_engine.py` no tiene "calcula" como keyword

**Fix en `src/processing/query_engine.py`**, en `_detectar_intent`, bloque "suma":

```python
        "suma": ["cuánto gastamos", "cuanto gastamos", "total gasto", "suma de",
                 "cuánto se gastó", "cuanto se gasto", "gasto total", "total de",
                 "cuánto cuesta", "cuanto cuesta", "sumar", "suma total",
                 "sumatoria", "sumatoria de", "suma total de", "suma por",
                 "total por", "cuanto suma", "cuánto suma", "sumame", "súmame",
                 "calcula", "calcular", "calcula el", "dame el total",  # ← AGREGAR
                 "dame la suma", "cuánto es", "cuanto es"],
```

---

## BUG 4 — /head trunca columnas (MENOR — ya parcialmente resuelto)

El ancho del console de captura ya está en 200 en `capturar_cmd()`.
Si sigue truncando, cambiar a 300.

Verificar en `src/api/routes/chat.py` que `capturar_cmd` tenga `width=200`.

---

## ORDEN DE EJECUCIÓN

1. Fix Bug 1 — `/alertas` y `/metricas` (5 min)
2. Fix Bug 3 — intent "calcula" en query_engine.py (2 min)  
3. Fix Bug 2 — `_rich_to_table` + integración en chat.py (20 min)
4. Verificar Bug 4 — width=200 en capturar_cmd

Reiniciar backend después de cada fix de Python.
Frontend con Vite se recarga solo.

---

## COMANDOS PARA LEVANTAR

```bash
# Terminal 1 — backend
cd C:\Users\moonw\Proyectos\Adly
.venv\Scripts\activate
uvicorn src.api.main:app --reload --port 8000

# Terminal 2 — frontend  
cd C:\Users\moonw\Proyectos\Adly\interfaces\web
npm run dev
```

---

## PRUEBAS DESPUÉS DE CADA FIX

### Bug 1:
- `/alertas` → debe mostrar alertas de integridad
- `/metricas` → debe mostrar métricas por campaña

### Bug 2:
- `/head` → debe mostrar DataTable con todas las columnas
- `/rfm` → debe mostrar DataTable con segmentos
- `/cohorts` → debe mostrar DataTable con cohortes

### Bug 3:
- "calcula el revenue por utm_campaign" → tabla con suma por campaña
- "calcula el total de costo_lead" → número total

### Lenguaje natural que ya funciona (no romper):
- "agrúpame por estado" → DataTable ✅
- "sumatoria de costo_lead por campaña" → DataTable ✅
- "valores únicos de utm_ad" → lista bullets ✅

---

## NOTAS IMPORTANTES

- `groq==0.4.2` y `httpx==0.27.0` — NO actualizar
- `VITE_MOCK=false` en `interfaces/web/.env.local` — NO revertir
- El console global de Rich está en `interfaces/cli/theme.py` — `console = Console()`
- `capturar_cmd()` hace monkey-patch temporal con lock — es thread-safe para demo
- Después de fix, actualizar `docs/errores_y_soluciones.md` con bugs resueltos
