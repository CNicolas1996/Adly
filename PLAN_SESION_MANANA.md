# PLAN SESIÓN — Continuación Mock Data + CLI
> Fecha: 2026-04-13 · Actualizado: 2026-04-14

---

## CONTEXTO

**Adly** — chatbot de análisis de campañas publicitarias. CLI funcionando con Groq + Llama 3.3 70b.
ColumnMapper implementado y probado — LLM infiere columnas de cualquier CSV sin config manual.

**Correr:**
```bash
cd C:\Users\moonw\Proyectos\Adly
venv\Scripts\activate
python interfaces/cli/cli.py
```

**Para probar mock ambiguo:** en onboarding, fuente → 1 (mock), CSV → `data/raw/mock_ambiguo.csv`

---

## LO QUE SE HIZO EN LA SESIÓN ANTERIOR (2026-04-13)

- ColumnMapper — LLM infiere columnas desde header + muestra, fallback por keywords, cache sesión
- mock_ambiguo.csv — 300 leads, columnas en inglés/UTM (utm_campaign, funnel_stage, spend, record_ts)
- CLI: onboarding pregunta CSV de prueba al elegir mock (persiste en .env como ADLY_MOCK_CSV)
- Fix DataValidator: col_id y col_estado se leen del config en vez de hardcodeados
- SheetsConnector y MockConnector delegan detectar_schema al ColumnMapper
- Auto-memory hook desactivado en .claude/settings.local.json

## LO QUE SE HIZO EN ESTA SESIÓN (2026-04-14)

- ✅ **Mock A ampliado** — 500 leads · fecha_creacion con distribución por campaña (Retargeting 4m, Branding 2m, Leads_Marzo 6sem) · fecha_cierre para ventas · commit `70a34fb`
- ✅ **Mock C dañado** — 206 registros con 15% nulos, 10% estados inválidos, 5% costos negativos, 3% fechas mal formateadas, duplicados por ID · `data/raw/mock_danado.csv` · commit `01a335d`
- ✅ **Formato de respuestas** — system prompt prohíbe markdown en valores JSON · renderizar_respuesta() con Rich Panels coloreados por severidad · commit `744a762`
- ✅ **Comandos de exploración** — /head [N] · /sample [N] · /describe · /exportar · Rich Tables · commit `925a3cd`

---

## PENDIENTES DEL PLAN ORIGINAL (aún relevantes)

### Prioritarios

- [x] **Mock A ampliado** — ✅ hecho 2026-04-14
- [x] **Mock C — datos dañados** — ✅ hecho 2026-04-14

### Secundarios (no urgentes)

- [ ] Mock E — estructura minimalista (3 columnas: campaña, leads, inversión)
- [ ] Mock F — multi-cliente en mismo Sheet (columna `cliente` o `account`)
- [ ] Preguntas de análisis temporal en CLI con Mock A ampliado

---

## NUEVOS PENDIENTES (agregados 2026-04-13)

- [x] **Formato de respuestas de Adly** — ✅ hecho 2026-04-14
- [x] **Comandos de exploración de datos en CLI** — ✅ hecho 2026-04-14 (/head /sample /describe /exportar)

- [ ] **DataValidator.COLUMNAS_CLAVE hardcodeada**
  - Actualmente no explota (filtra columnas que no existen) pero no valida bien con CSVs externos
  - Hacerla dinámica desde el config del ColumnMapper
  - Prioridad: baja

- [] **Identificar parametros Hardcodeados que deban ser agnosticos***
  - Identificar mas caracteristias del  sistemas que esten hardcodeados pero que deben tener una naturaleza agnostica o configurable por el usuario.

---

## ARCHIVOS A REVISAR AL INICIO DE SESIÓN

1. `src/ingestion/mock_data.py` — para ampliar Mock A y crear Mock C
2. `interfaces/cli/cli.py` — para agregar comandos /head, /sample, /describe, /exportar
3. `src/ai/engine.py` — para ajustar system prompt y eliminar markdown en respuestas

- [ ] **Conectar Sheet real de Camí**
  - Camí debe compartir el Sheet con `adly-service@gen-lang-client-0574573686.iam.gserviceaccount.com`
  - Agregar `GOOGLE_SHEET_ID=...` en `.env`
  - Probar fuente → 2 (sheets) en CLI — ColumnMapper debe inferir columnas del Sheet real
  - Validar que las métricas de campañas reales se calculan correctamente

---

## CRITERIO DE ÉXITO

- [x] Mock A con 500+ leads y análisis temporal funcionando en CLI
- [x] Mock C con datos dañados — Adly avisa pero no explota
- [x] `/describe` y `/exportar` funcionando en CLI
- [x] Respuestas de Adly con formato Rich limpio — sin markdown crudo, estructura visual clara
- [ ] Sheet real de Camí conectado y respondiendo preguntas sobre campañas reales
