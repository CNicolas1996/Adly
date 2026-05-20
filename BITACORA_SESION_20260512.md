# BITÁCORA — Sesión 2026-05-12
> Adly · Auditoría sistema agnóstico + inicio refactor SemanticInferencer

---

## Objetivo de la sesión
Auditar el sistema completo de Adly para identificar hardcodeo de vocabulario del cliente.
Diseñar e iniciar implementación de capa semántica transversal.

---

## Archivos auditados

| Archivo | Veredicto |
|---|---|
| `engine.py` | ✅ Agnóstico real — no tocar |
| `column_mapper.py` | 🟡 Agnóstico en flujo LLM, fallback malo |
| `ingestion_normalizer.py` | 🔴 Hardcodeo total — problema central |
| `metrics.py` | 🟡 Estructura agnóstica, semántica hardcodeada |
| `sheets.py` | ✅ Correcto — versión con normalizar() en leer() |

---

## Hallazgos críticos

### ingestion_normalizer.py — 10 puntos de hardcodeo
1. `STAGE_MAP` — 19 entradas vocabulario Camí hardcodeadas
2. `_encontrar_col(df, "correo")` — nombre exacto, falla con "email", "e-mail", etc.
3. `_encontrar_col(df, "telefono")` — falla con "phone", "celular", "mobile"
4. `_encontrar_col(df, "nombre")` — falla con "name", "full_name", "contacto"
5. `_encontrar_col(df, "stage")` — falla con "etapa", "status", "estado_funnel"
6. `_clasificar_duplicados` busca "duplicado"/"duplicate" como string literal
7. `_normalizar_titulacion` excluye con lista hardcodeada de nombres de columna
8. `_analizar_3fn` tiene dict de "entidades" con palabras clave fijas
9. `_analizar_2fn` tiene 4 pares de nombres exactos hardcodeados
10. `_analizar_4fn` busca "ad primera atribucion" y "ad segunda atribucion" literales

### metrics.py — 2 puntos
1. `resumen_ejecutivo_llm()` tiene `NORM` dict hardcodeado con vocabulario de stages
2. `CONFIG_DEFAULT` usa nombres de columnas del CSV de Camí como default real

### column_mapper.py — 1 punto
1. `_fallback_keyword()` retorna config inventada silenciosamente cuando LLM falla

---

## Decisiones de arquitectura tomadas

### Decisión 1 — SemanticInferencer como capa transversal
**Qué:** Nuevo módulo `src/processing/semantic_inferencer.py` con clase `SemanticInferencer`.
**Por qué:** Centraliza toda la lógica semántica en un solo lugar. Evita que aliases,
listas y heurísticas se dispersen en N archivos otra vez.
**Alternativa descartada:** Listas de aliases por categoría — sigue siendo hardcodeo disfrazado.

### Decisión 2 — SemanticSchema como dataclass única fuente de verdad
**Qué:** Reemplaza el dict suelto que devuelve ColumnMapper.
**Por qué:** Tipado, predecible, un solo contrato para todos los módulos downstream.

### Decisión 3 — sentence-transformers sobre Gemini embeddings API
**Contexto:** Se evaluaron dos opciones para la capa de embeddings:
- `sentence-transformers` con modelo `paraphrase-multilingual-MiniLM-L12-v2` (~2GB total con torch)
- Gemini embeddings API (cero dependencias nuevas, ya teníamos key)

**Decisión final:** `sentence-transformers` — ya instalado antes de evaluar alternativas.
**Resultado instalación:** `groq==0.4.2` y `httpx==0.27.0` sobrevivieron intactos.
**Riesgo conocido:** Cold start al cargar modelo. Mitigación: cachear instancia en `state.py` al arrancar FastAPI.

### Decisión 4 — ColumnMapper demovido a fallback
**Qué:** `ColumnMapper` LLM pasa de ser componente principal a fallback del `SemanticInferencer`.
**Por qué:** Embeddings locales son más rápidos y no consumen tokens. LLM solo cuando confianza baja.

### Decisión 5 — Vocabulario canónico de Adly SÍ se hardcodea
**Qué:** `lead`, `warm_lead`, `contacted`, `follow_up`, `appointment_set`, `venta`, `perdido`, `no_show`, `no_contactado`, `descarte` quedan como constantes en SemanticInferencer.
**Por qué:** Ese es el vocabulario de ADLY, no del cliente. Lo agnóstico es el mapeo cliente→canónico, no el canónico mismo.

---

## Pipeline final

```
CSV
  → SemanticInferencer.analizar(df)    # embeddings + heurísticas estadísticas
      → SemanticSchema                 # fuente única de verdad
  → ingestion_normalizer.normalizar(df, schema)
  → MetricsCalculator(schema)
  → AdlyEngine.chat()
```

---

## Dependencias nuevas agregadas

| Librería | Versión | Motivo |
|---|---|---|
| `sentence-transformers` | 5.5.0 | Embeddings semánticos locales |
| `torch` | 2.11.0 | Dependencia de sentence-transformers |
| `scikit-learn` | 1.8.0 | Dependencia de sentence-transformers |
| `rapidfuzz` | pendiente agregar a requirements.txt | Fuzzy matching como fallback adicional |

**⚠️ Versiones críticas verificadas post-instalación:**
- `groq==0.4.2` ✅ intacto
- `httpx==0.27.0` ✅ intacto

---

## Errores / decisiones no obvias

### Error de naming en uploads
Durante la auditoría, `metrics.py` fue subido incorrectamente 3 veces con el contenido
de `sheets.py`. El `metrics.py` real está en `src/processing/metrics.py` y contiene
`MetricsCalculator` + `CONFIG_DEFAULT`. El `sheets.py` correcto es el que tiene
`from src.ingestion.ingestion_normalizer import normalizar` y llama `normalizar()` dentro de `leer()`.

### sentence-transformers instalado antes de evaluar alternativas
Se instaló `sentence-transformers` antes de comparar con Gemini embeddings API.
Gemini habría sido más liviano (0 dependencias nuevas). Decisión: seguir con
sentence-transformers ya que no rompió versiones críticas.

---

## Pendientes post-sesión 2026-05-12

- [ ] Agregar `rapidfuzz>=3.0.0` a `requirements.txt`
- [ ] Agregar `sentence-transformers==5.5.0` a `requirements.txt`
- [ ] Cachear `SemanticInferencer` en `state.py` al arrancar FastAPI
- [ ] Actualizar `adly_master_v2.html` con cambios de Fase actual
- [ ] Fix `column_mapper.py` fallback silencioso
- [ ] Calibración fina SemanticInferencer: `as_config()` estado_mql/sql, falso positivo attribution_columns

---

## Resultado SemanticInferencer — validación con 2 CSVs

### Test 1 — mock_ghl.csv (13 columnas, español técnico)
| Campo | Detectado | Conf |
|---|---|---|
| col_email | email | 0.99 |
| col_phone | telefono | 0.99 |
| col_name | nombre | 0.99 |
| col_date | fecha_creacion | 0.99 |
| col_id | ghl_id | 0.99 |
| col_campana | campana | 0.99 |
| col_adset | adset | 0.99 |
| col_ad | ad | 0.73 |
| col_estado | estado | 0.99 |
| col_inversion | costo_lead | 0.99 |
| col_valor | valor_venta | 0.99 |

Stages: `lead→lead`, `mql→mql`, `sql→sql`, `venta→venta`, `perdido→perdido` ✅

### Test 2 — cami_real.csv (9 columnas, inglés con espacios, schema completamente distinto)
| Campo | Detectado | Conf |
|---|---|---|
| col_email | correo | 0.99 |
| col_phone | telefono | 0.99 |
| col_name | Nombre | 0.99 |
| col_date | Fecha de creacion | 0.99 |
| col_estado | stage | 0.99 |
| col_campana | null | — (no existe en CSV) |
| col_inversion | null | — (no existe en CSV) |
| col_valor | null | — (no existe en CSV) |

Stages: `Warm Lead→lead_caliente`, `No Show→no_se_presento`, `Appointment Set→cita_agendada`,
`Lead→lead`, `Duplicate→duplicado`, `Closed Lost→perdido`, `Contacted→contactado`, `Spam→spam` ✅

**Conclusión: agnóstico real validado.** Dos CSVs completamente distintos, sin tocar código entre uno y otro.

---

---

# BITÁCORA — Sesión 2026-05-14
> Adly · Sprint bugs v1.0 — Jueves del despliegue

---

## Objetivo
Cerrar Bug 1, Bug 2 y avanzar en agnóstico de stages.

---

## Completado

### ✅ Bug 1 — NORM dinámico en `metrics.py`
**Archivo:** `src/processing/metrics.py` — `resumen_ejecutivo_llm()` líneas 257-277
**Problema:** Dict `NORM` hardcodeado con stages en español/inglés estándar. `"Cerrado Ganado"` caía en "Otros/sucios" → `/cohorts` reportaba 0 ventas.
**Fix:**
- `NORM_BASE` con aliases genéricos permanentes
- Extensión dinámica desde `self.config` → `estado_venta`, `estado_mql`, `estado_sql` se leen en runtime
- `_normalizar_key()` convierte espacios a underscores antes del lookup
**Resultado:** `VENTA: 1` en test unitario. `/cohorts` con `cami_real.csv` muestra 9 cohortes con ventas reales.

### ✅ Bug 2 — NaN/Inf no serializable en `/head` y `/sample`
**Archivo:** `src/api/command_bridge.py` — `bridge_head()` y `bridge_sample()`
**Problema:** `json.dumps` fallaba con `ValueError: Out of range float values are not JSON compliant` cuando el df tenía NaN o Inf en columnas numéricas.
**Fix:** `.copy()` + `.where(pd.notnull(sub), None)` — convierte NaN → None (JSON null) antes de `to_dict()`.
**Resultado:** `/head 5`, `/head 20`, `/sample 20` funcionando con `cami_real.csv` (1800 filas).

### ✅ SemanticInferencer — sinónimos ES expandidos
**Archivo:** `src/processing/semantic_inferencer.py`
- `NOMBRE_DIRECTO["col_campana"]` ampliado con: `"primera atribucion"`, `"atribucion"`, `"primera_atribucion"`, `"attribution"`, `"fuente"`
- `STAGE_DIRECTO` ampliado con: `"cerrado ganado"`, `"closed ganado"`, `"ganado"`, `"cerrado perdido"`, `"no contactado"`, `"lead caliente"`

### ✅ ValueMapper — variantes underscore
**Archivo:** `src/processing/value_mapper.py` — `SINONIMOS_ESTADO`
- Problema raíz: `_normalizar_key()` convierte espacios → underscores ANTES del dict lookup. `"Cerrado Ganado"` → key `"cerrado_ganado"` que no existía.
- Agregadas: `"cerrado_ganado"`, `"closed_ganado"`, `"cerrado_won"`, `"cerrado_perdido"`, `"closed_perdido"`, `"no_se_presento"` (sin acento), `"lead_caliente"`

### ✅ `_estados_venta()` en `commands.py`
**Archivo:** `interfaces/cli/commands.py`
- Función `_estados_venta()` ampliada con: `"ventas"`, `"closed won"`, `"cerrado ganado"`, `"closed ganado"`, `"ganado"`
- Agregado `.strip()` al comparador para valores con espacios CRM

---

## Resultado final de la sesión

```
/cohorts con cami_real.csv:
2025-11  199 leads  20 ventas  10.1%
2025-12  260 leads  29 ventas  11.2%
2026-01  277 leads  13 ventas   4.7%
2026-02  284 leads  19 ventas   6.7%
2026-03  346 leads  31 ventas   9.0%
2026-04  266 leads  20 ventas   7.5%
2026-05  116 leads   8 ventas   6.9%
2026-06   35 leads   3 ventas   8.6%
2026-07   17 leads   1 venta    5.9%
```

`/head` y `/sample` con N funcional ✅

---

## Pendiente para mañana (viernes 15)

- [ ] **Bug 3** — umbral n≥5 para tasas en `metrics.py` `_calcular_metricas()`
- [ ] **Gráficos Plotly** — mover a sábado per roadmap (bug 3 primero)
- [ ] `test_cohorts_fix.py` en raíz — archivo de test temporal, eliminar antes del commit o mover a `/tests`

## Archivos NO subir a GitHub
- `data/raw/cami_real.csv` — datos reales de cliente
- `credentials.json` — service account Google
- `.env` — API keys
- `test_cohorts_fix.py` — archivo temporal en raíz (eliminar o mover a /tests)
- `Select-String` — archivo extraño en raíz, revisar qué es
