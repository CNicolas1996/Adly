# PATCH MAESTRO_ADLY — 2026-05-12
> Pegar estas secciones en MAESTRO_ADLY.md reemplazando las equivalentes

---

## Arquitectura de archivos — actualizar árbol

```
src/processing/
  ├── semantic_inferencer.py  ✅ NUEVO — capa semántica transversal
  ├── column_mapper.py        🟡 demovido a fallback del SemanticInferencer
  ├── ingestion_normalizer.py 🔄 EN REFACTOR — recibe schema como parámetro
  ├── metrics.py              🔄 PENDIENTE REFACTOR — NORM hardcodeado
  └── ...resto igual
```

---

## Pipeline de datos — ACTUALIZADO

```
ANTES:
  CSV → normalizar(df) → ColumnMapper.mapear(df) → MetricsCalculator(config)

AHORA:
  CSV
    → SemanticInferencer.analizar(df)     # 3 capas: estadística + embeddings + stages
        → SemanticSchema                  # fuente única de verdad
    → ingestion_normalizer.normalizar(df, schema)
    → MetricsCalculator(schema.as_config())
    → AdlyEngine.chat()
```

---

## SemanticInferencer — nuevo módulo core

**Archivo:** `src/processing/semantic_inferencer.py`
**Instanciar:** UNA VEZ en `state.py` al arrancar FastAPI — no por request (cold start ~3s)

**3 capas:**
1. Heurísticas estadísticas — detecta email/phone/date/numeric por contenido, sin LLM
2. Embeddings semánticos — mapea nombres de columna al schema canónico (matching directo primero, embeddings para casos ambiguos)
3. Mapeo de stages — matching directo para siglas (mql/sql/lead), embeddings para texto libre (Warm Lead, Closed Won, etc.)

**Fallback:** Si embeddings fallan → `ColumnMapper` LLM existente

**Validado con:**
- `mock_ghl.csv` — 13 columnas español técnico → 11/11 detectadas
- `cami_real.csv` — 9 columnas inglés con espacios → schema completamente distinto → detecta correctamente lo que existe, null honesto en lo que no existe

---

## Decisiones de arquitectura — 2026-05-12

| Decisión | Qué | Por qué |
|---|---|---|
| SemanticInferencer | Capa transversal nueva | Centraliza semántica — evita aliases dispersos en N archivos |
| SemanticSchema | Dataclass fuente única de verdad | Reemplaza dict suelto de ColumnMapper — tipado y predecible |
| sentence-transformers | Embeddings locales | Ya instalado — groq y httpx pinneadas sobrevivieron intactas |
| ColumnMapper → fallback | Demovido de principal a fallback | Embeddings locales más rápidos y sin costo de tokens |
| Vocabulario canónico hardcodeado | lead/mql/sql/venta/perdido etc. en SemanticInferencer | Es vocabulario de ADLY, no del cliente — lo agnóstico es el mapeo |

---

## Pendientes refactor semántico — próximas sesiones

- [ ] Refactor `ingestion_normalizer.py` — recibir `schema: SemanticSchema` como parámetro, eliminar STAGE_MAP y búsquedas por nombre exacto
- [ ] Refactor `metrics.py` — `NORM` dinámico desde schema, `CONFIG_DEFAULT` → `CONFIG_VACIO`
- [ ] Fix `column_mapper.py` — `_fallback_keyword()` retorna None en vez de config inventada
- [ ] Cachear `SemanticInferencer` en `state.py` al arrancar FastAPI
- [ ] Agregar a `requirements.txt`: `sentence-transformers==5.5.0`, `rapidfuzz>=3.0.0`
- [ ] Calibración fina SemanticInferencer: `as_config()` para estado_mql/sql, falso positivo attribution_columns
