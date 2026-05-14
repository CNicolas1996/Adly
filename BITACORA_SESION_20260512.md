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

## Pendientes post-sesión

- [ ] Agregar `rapidfuzz>=3.0.0` a `requirements.txt`
- [ ] Agregar `sentence-transformers==5.5.0` a `requirements.txt`
- [ ] Cachear `SemanticInferencer` en `state.py` al arrancar FastAPI
- [ ] Actualizar `MAESTRO_ADLY.md` con nueva arquitectura pipeline
- [ ] Actualizar `adly_master_v2.html` con cambios de Fase actual

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

### Calibración aplicada durante sesión
1. Descripciones canónicas reescritas para reducir ambigüedad campana/adset/ad
2. Threshold bajado de 0.45 a 0.38 — nombres técnicos cortos embedean con scores menores
3. Matching directo por nombre de columna (Paso 0) antes de embeddings — resolvió telefono/nombre/costo_lead/ghl_id
4. Matching directo de stages antes de embeddings — resolvió mql/sql/lead

### Pendientes de calibración fina (no bloquean)
- `col_id` en cami_real.csv detecta `ad segunda atribucion` — no hay ID explícito en ese CSV
- `col_ad` en cami_real.csv detecta `ad set segunda atribucion` en vez de `ad primera atribucion`
- `attribution_columns` incluye `stage` como falso positivo
- Warning cosmético `Could not infer format` en pd.to_datetime — silenciar con `format="mixed"`
- `as_config()` — `estado_mql` retorna valor incorrecto con mock (retorna `"lead"` en vez de `"mql"`)

---

## Estado al cierre de sesión

- [x] `semantic_inferencer.py` — ✅ COMPLETADO y validado con 2 CSVs
- [ ] Refactor `ingestion_normalizer.py` — próximo
- [ ] Refactor `metrics.py` — pendiente
- [ ] Fix `column_mapper.py` fallback — pendiente
- [ ] Cachear `SemanticInferencer` en `state.py`
- [ ] Agregar `sentence-transformers==5.5.0` y `rapidfuzz>=3.0.0` a `requirements.txt`
- [ ] Actualizar `MAESTRO_ADLY.md` con nueva arquitectura pipeline
- [ ] Actualizar `adly_master_v2.html`
