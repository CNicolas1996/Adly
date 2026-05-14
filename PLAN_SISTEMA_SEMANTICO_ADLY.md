# Plan: Sistema Semántico Adly — Refactor Agnóstico

> **Objetivo:** Eliminar todo hardcoding de vocabulario del cliente (nombres de columna, stages, valores categóricos) de Adly. El sistema debe operar sobre cualquier CSV sin tocar código.
>
> **Duración estimada:** 3 días (~12-15h totales)
> **Atraso entrega Camí:** ~4 días
> **Justificación:** Es uno de los puntos más fuertes de Adly y resuelve problemas reales de analítica de datos para múltiples fuentes.

---

## Hallazgos del código actual

### `ingestion_normalizer.py` — Hardcodeo total

1. **`STAGE_MAP`** (líneas 60-80) — 19 entradas en inglés/español. Conflicto directo con `value_mapper`.
2. **`_encontrar_col(df, "correo")`** — busca literal "correo". Si Camí usa "email", "Email", "e_mail" → falla silenciosamente.
3. **`_encontrar_col(df, "telefono")`** — mismo problema con "phone", "Teléfono", "celular".
4. **`_encontrar_col(df, "nombre")`** — falla con "name", "full_name", "contacto".
5. **`_encontrar_col(df, "stage")`** — falla con "etapa", "status", "estado_funnel".
6. **`_clasificar_duplicados`** busca "duplicado"/"duplicate" como string literal en stages (línea 161).
7. **`_normalizar_titulacion`** excluye con `_EXCLUIR = {"correo", "telefono", "fecha", "email", "id", "url"}` (línea 196).
8. **`_analizar_3fn`** tiene dict completo de "entidades" con palabras clave (líneas 352-356).
9. **`_analizar_2fn`** tiene 4 pares de nombres exactos hardcodeados (líneas 300-305).
10. **`_analizar_4fn`** busca "ad primera atribucion" y "ad segunda atribucion" como strings literales.

**Diagnóstico:** el archivo está construido entero asumiendo que los nombres de columna de Camí son universales. Peor de lo que pensábamos.

### Lo que NO es problema (no se toca)

- `_EMAIL_VALIDO` regex RFC — estándar universal.
- Detección de prefijo `+` en teléfono — estándar universal.
- Detección de pipe/punto y coma en 1FN — estructural.
- Lógica de capitalización — estructural.

---

## Arquitectura final

```
┌─────────────────────────────────────────────────────────┐
│  SemanticInferencer  (capa transversal)                 │
│  semantic_inferencer.py                                 │
├─────────────────────────────────────────────────────────┤
│  __init__():                                            │
│    carga modelo sentence-transformers (1 vez, cacheado) │
│    embedde vocabulario canónico de Adly                 │
│                                                          │
│  analizar(df) → SemanticSchema                          │
│    Capa 1: detectar_tipos_estadisticos(df)              │
│      └─ email/phone/date/numeric/id/categorical         │
│    Capa 2: mapear_columnas(df)                          │
│      └─ embeddings sobre nombres + samples              │
│      └─ LLM fallback solo si confianza baja             │
│    Capa 3: mapear_valores_categoricos(df, schema)       │
│      └─ embeddings vs vocab canónico                    │
└─────────────────────────────────────────────────────────┘
                       ↓ SemanticSchema
┌─────────────────────────────────────────────────────────┐
│  SemanticSchema  (dataclass, fuente única de verdad)    │
├─────────────────────────────────────────────────────────┤
│  col_email, col_phone, col_name, col_stage, col_date,   │
│  col_campana, col_adset, col_ad, col_leads, col_id,     │
│  col_inversion, col_valor                               │
│  value_map_stages: {valor_cliente: canónico_adly}       │
│  attribution_columns: [(col, [niveles])]                │
│  confidence: {col_email: 0.95, ...}                     │
│  warnings: [...]                                        │
└─────────────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│  Pipeline                                                │
│  CSV → SemanticInferencer.analizar() → schema           │
│      → ingestion_normalizer.normalizar(df, schema)      │
│      → MetricsCalculator(schema)                        │
└─────────────────────────────────────────────────────────┘
```

---

## Día 1 — Fundación semántica (4-5h)

### 1.1 — Instalar y validar dependencias (30 min)

```bash
pip install sentence-transformers
```

- Probar carga del modelo `paraphrase-multilingual-MiniLM-L12-v2`.
- Verificar que descarga + embed funciona en local.
- Agregar a `requirements.txt` junto con `rapidfuzz>=3.0.0` pendiente.

### 1.2 — Crear `src/processing/semantic_inferencer.py` (2h)

- Clase `SemanticInferencer` con modelo cacheado a nivel de instancia.
- Vocabulario canónico de Adly definido como constantes (este SÍ se hardcodea — es TU vocabulario, no del cliente).
- Método `detectar_tipos_estadisticos(df)` — heurísticas puras, 0 LLM, 0 embeddings:
  - **Email:** regex RFC, threshold 70% matches.
  - **Teléfono:** regex dígitos + opcional `+`, threshold 70%.
  - **Fecha:** `pd.to_datetime(errors='coerce')`, threshold 70% no-nulos.
  - **Numérico continuo:** `pd.to_numeric` + cardinality alta + no booleano.
  - **ID:** `nunique/len > 0.95`.
  - **Categórico:** `dtype object` + `nunique < 50`.

### 1.3 — Crear `SemanticSchema` dataclass (30 min)

- Estructura clara, una sola fuente de verdad.
- Reemplaza el dict suelto que devuelve `ColumnMapper` hoy.

### 1.4 — Tests de la capa estadística contra CSV de Camí (1h)

- Confirmar que detecta email, teléfono, fecha, stages correctamente sin ningún hardcoding de nombres.

---

## Día 2 — Inferencia semántica + integración (4-5h)

### 2.1 — Método `mapear_columnas(df)` (2h)

- Embeddings de nombres de columna del cliente.
- Embeddings de descripciones canónicas (lo que ya tenés en `SCHEMA_ADLY` del `ColumnMapper`).
- Similitud coseno + threshold (probable 0.55-0.65, lo calibramos con el CSV de Camí).
- Si confidence < threshold → fallback al `ColumnMapper` LLM existente (no lo botamos, lo demotamos a fallback).
- **Cache:** si las columnas no cambian, reusa schema previo.

### 2.2 — Método `mapear_valores_categoricos(df, schema)` (2h)

- Para columnas detectadas como categóricas (especialmente stages).
- Embed valores únicos del cliente.
- Embed vocabulario canónico de Adly: `lead`, `warm_lead`, `contacted`, `follow_up`, `appointment_set`, `venta`, `perdido`, `no_show`, `no_contactado`, `descarte`.
- Mapeo por similitud máxima.
- Threshold de confianza — bajo confianza marca como "ambiguo" en warnings.

### 2.3 — Refactorizar `ingestion_normalizer.py` (1h)

- `normalizar(df, schema)` recibe el schema como parámetro obligatorio.
- **Borrar `STAGE_MAP` completo.**
- Reemplazar todos los `_encontrar_col(df, "correo")` por `schema.col_email`.
- Mismo con telefono, nombre, stage.
- Las heurísticas universales (regex RFC, prefijo `+`, pipe en 1FN) se quedan tal cual.
- Las funciones `_analizar_2fn`, `_analizar_3fn`, `_analizar_4fn` se refactorizan para usar el schema en vez de nombres exactos.
- `_normalizar_stages` ahora usa `schema.value_map_stages`.

---

## Día 3 — Integración + testing (4-5h)

### 3.1 — Actualizar `ColumnMapper` (1h)

- Lo convertimos en fallback del `SemanticInferencer`, no en componente principal.
- Mantenemos el cache que ya tiene.

### 3.2 — Actualizar `ValueMapper` (1h)

- El vocabulario canónico se queda (tu decisión, controlás).
- El método de mapeo cliente→canónico ahora delega al `SemanticInferencer`.
- **Resuelve el bug crítico #2 de la sesión 2026-05-11.**

### 3.3 — Pipeline integrado en `src/api/analyses.py` (1h)

```python
schema = SemanticInferencer().analizar(df)
df, reporte = normalizar(df, schema)
state._quality_reports[analysis_id] = quality_report
state._schemas[analysis_id] = schema  # disponible para todos
```

### 3.4 — Testing exhaustivo con `base_marketing_desordenada_meta_ads_v3.csv` (1h)

- Re-correr toda la batería de la sesión 2026-05-11.
- Confirmar que `/cohorts`, `/rentabilidad`, `/velocidad` ahora funcionan.
- Confirmar que `/alertas` mantiene su comportamiento actual.

### 3.5 — Buffer para imprevistos (1h)

- Siempre aparece algo. Acá lo absorbés.

---

## Fuera de scope (NO se toca en estos 3 días)

> Explícito para evitar scope creep.

- ❌ Integración de `attribution_parser` al pipeline (bug crítico #1 — sesión aparte).
- ❌ Filtrar flags en `/columnas` (bug #3 — sesión aparte).
- ❌ Redirección cuando falta columna de costo (bug #4).
- ❌ Limpiar prints de debug (bug #5).
- ❌ Frontend.
- ❌ Nuevos comandos.
- ❌ Optimizar tokens del system prompt.

**Estos 5 bugs se cierran en una sesión 4 después de este refactor.**

---

## Confirmaciones antes de empezar Día 1

1. **¿De acuerdo con la arquitectura `SemanticInferencer` + `SemanticSchema` como capa transversal?**
   Es lo que evita que la lógica semántica se disperse en N archivos otra vez.

2. **¿Aceptás que el vocabulario canónico de Adly se queda hardcodeado?**
   (`lead`, `warm_lead`, `contacted`, `follow_up`, `appointment_set`, `venta`, `perdido`, `no_show`, `no_contactado`, `descarte`).
   Eso NO es problema — es TU vocabulario. Lo agnóstico es el mapeo cliente → canónico.

3. **¿Algún archivo que NO debería tocar?**
   Especialmente si hay algo del web UI conectado al engine que pueda romperse silenciosamente.

---

## Stack

- **Modelo embeddings:** `paraphrase-multilingual-MiniLM-L12-v2` (~120MB, multiidioma, CPU).
- **Librerías nuevas:** `sentence-transformers`, `rapidfuzz` (pendiente desde sesión anterior).
- **LLM:** se mantiene como fallback en `ColumnMapper`, no como principal.
- **Cache:** schemas se cachean por `analysis_id` en `state._schemas`.
