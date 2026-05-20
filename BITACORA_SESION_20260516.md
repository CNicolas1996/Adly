# BITÁCORA — Sesión 2026-05-16
> Adly · Pipeline semántico conectado + /metricas dinámico + unificación de variantes

---

## Objetivo de la sesión
Conectar el SemanticInferencer al pipeline real de FastAPI y refactorizar /metricas
para que sea agnóstico al schema del cliente.

---

## Completado

### ✅ SemanticInferencer conectado al pipeline real
**Archivos:** `src/api/state.py`, `src/api/routes/analyses.py`, `src/ingestion/ingestion_normalizer.py`
**Problema:** El SemanticInferencer existía como código huérfano. El pipeline real usaba
ColumnMapper LLM + hardcodeo. El schema no llegaba a ningún módulo downstream.
**Fix:**
- `state.py` → lazy init de SemanticInferencer como singleton, cachea modelo en memoria
- `analyses.py` → `df_raw.columns = [c.strip() for c in df_raw.columns]` como PASO 0 antes de todo
- `analyses.py` → llama `inferencer.analizar(df_raw)` → pasa `semantic_schema` a `normalizar()` y a `add_analysis()`
- `ingestion_normalizer.py` → firma `normalizar(df, schema=None)` — usa columnas del schema cuando están disponibles, fallback a nombres hardcodeados para backward compat

**Resultado:** El log muestra SemanticInferencer corriendo en cada upload. Dos CSVs distintos detectados correctamente sin tocar código entre uno y otro.

### ✅ SemanticSchema persistido por sesión
**Archivo:** `src/api/state.py`
**Problema:** El schema se perdía después del upload — nadie lo guardaba.
**Fix:** `self.semantic_schemas: OrderedDict[str, Any]` en AppState. Guardado en `add_analysis()` como `semantic_schema=semantic_schema`. Disponible para todos los comandos por `analysis_id`.

### ✅ Strip universal como PASO 0
**Problema recurrente:** Columnas con espacios trailing (`stage `, `telefono `) causaban KeyError en normalizer después de que el schema las detectaba con el nombre sucio.
**Fix definitivo:** Una línea en `analyses.py` antes del SemanticInferencer. Resuelve para siempre.

### ✅ /metricas con selector dinámico agnóstico
**Archivos:** `src/api/command_bridge.py` (bridge_metricas), `src/api/routes/chat.py`
**Problema:** Handler viejo hardcodeado — agrupaba por `col_campana` que en `cami_real.csv` mapeaba a `Fecha de creacion` → tabla de 1800 filas con 1 lead por fila.
**Fix:**
- `bridge_metricas(df, schema, dimension)` — detecta dimensiones disponibles desde SemanticSchema + heurísticas sobre el df real
- Si no hay dimensión especificada → muestra selector numerado
- Si hay número → calcula métricas agrupadas por esa dimensión
- Dimensiones temporales generadas automáticamente si hay col_date: mes, semana, trimestre, año
- `_build_registry` recibe `analysis_id` como parámetro para que el lambda tenga acceso
**Resultado:**
```
/metricas → selector con 7 opciones
/metricas 1 → por campaña (272 grupos)
/metricas 6 → por trimestre (Q1/Q2/Q3/Q4)
```

### ✅ Unificación de variantes categóricas
**Archivo:** `src/ingestion/ingestion_normalizer.py`
**Problema:** `Reel IA`, `reel ia`, `Reel_IA` contaban como 3 campañas distintas. Misma raíz — el normalizer detectaba capitalización inconsistente pero no unificaba variantes con underscores/guiones.
**Fix:** `_normalizar_clave()` + `_unificar_variantes_categoricas()` — regla agnóstica universal:
`lowercase + strip + [_, -, .] → espacio + colapsar espacios múltiples`
El canónico es el valor más frecuente del grupo. Aplica a todas las columnas object sin excepción.
**Resultado:** De 321 a 272 grupos en col_campana de `cami_real.csv`.

### ✅ src/ingestion/state.py eliminado
Duplicado muerto — nadie lo importaba. Solo existía `src/api/state.py`.

---

## Pendientes detectados en sesión

- [ ] **Ventas en 0 en /metricas** — `value_map_stages` del SemanticSchema no llega a `bridge_metricas`. Los stages de Camí ("Appointment Set", "Closed Lost", etc.) no se reconocen como ventas en el bridge. El `/cohorts` sí los reconoce porque usa una ruta diferente.
- [ ] **Valores con pipes concatenados en col_campana** — `"0% Interest Biz | Broad USA | Reel IA"` aparece como un valor distinto de `"0% Interest Biz"`. Hay que separar estos valores con pipe ANTES de `_unificar_variantes_categoricas`. El `attribution_parser` debería manejarlo — verificar.
- [ ] **rapidfuzz a requirements.txt** — pendiente desde 2026-05-12
- [ ] **sentence-transformers==5.5.0 a requirements.txt** — pendiente desde 2026-05-12
- [ ] **Actualizar adly_master_v2.html**

---

## Archivos modificados en sesión

| Archivo | Cambio |
|---------|--------|
| `src/api/state.py` | SemanticInferencer lazy init + semantic_schemas OrderedDict |
| `src/api/routes/analyses.py` | Strip PASO 0 + SemanticInferencer en pipeline + semantic_schema a state |
| `src/ingestion/ingestion_normalizer.py` | Firma schema=None + _unificar_variantes_categoricas |
| `src/api/command_bridge.py` | bridge_metricas() completo al final del archivo |
| `src/api/routes/chat.py` | Handler viejo /metricas eliminado + registry entry + analysis_id a _build_registry |
| `src/ingestion/state.py` | ELIMINADO — duplicado muerto |
