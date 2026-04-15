# MAESTRO ADLY
> Pegar junto con CLAUDE.md cuando la sesión sea sobre Adly
> Última actualización: 2026-04-13

---

## Qué es

Chatbot inteligente que analiza campañas publicitarias desde GoHighLevel CRM.
Primer módulo de Data-Buddy en producción real con cliente real.

**Cliente 0:** Camí (hermano de Nico) — director de marketing, agencia pequeña. Cliente y socio.

**Tres problemas que resuelve:**
1. Consistencia — CRM y Sheet con discrepancias
2. Análisis — métricas en tiempo real por lenguaje natural
3. Recomendaciones accionables — qué pausar, escalar, ajustar

---

## Stack

Python · gspread · pandas · FastAPI · APScheduler · Claude API · Plotly · Rich

---

## Flujo de datos

```
GoHighLevel CRM → n8n → Google Sheets
                              ↓
                    APScheduler (cada 30 min)
                    Lee CRM + Sheet · Compara · Corrige · Cachea
                              ↓
                    Datos limpios → Motor IA → CLI / Web / WhatsApp
```

Regla de oro: CRM siempre gana sobre el Sheet.

---

## Estructura de archivos

```
Adly/
├── src/
│   ├── ingestion/
│   │   ├── mock_data.py      ✅ Mock A (500 leads, fechas históricas, fecha_cierre) · Mock B (sheet errores) · Mock C (datos dañados) · Mock D (ambiguo inglés/UTM)
│   │   └── sheets.py         ✅ BaseConnector · SheetsConnector · MockConnector (schema via LLM)
│   ├── processing/
│   │   ├── column_mapper.py  ✅ ColumnMapper · inferencia LLM · fallback keyword · cache sesión
│   │   ├── validation.py     ✅ DataValidator · ResultadoValidacion
│   │   ├── alerts.py         ✅ AlertManager · NivelAlerta
│   │   └── metrics.py        ✅ MetricsCalculator · 9 métricas · resumen_para_llm()
│   └── ai/
│       └── engine.py         ✅ BaseLLM · 11 proveedores · AdlyEngine · LLMFactory · system prompt anti-markdown
├── interfaces/
│   ├── cli/cli.py            ✅ Rich · Blade Runner · 12 comandos · Rich panels por severidad
│   ├── web/index.html        ⏳ pendiente
│   └── whatsapp/webhook.py   ⏳ pendiente
├── data/raw/
│   ├── mock_ghl.csv          ✅ 500 leads simulados · fechas históricas por campaña · fecha_cierre
│   ├── mock_sheet.csv        ✅ con errores intencionales
│   ├── mock_ambiguo.csv      ✅ 300 leads · columnas en inglés/UTM · para probar ColumnMapper
│   └── mock_danado.csv       ✅ 206 leads · nulos/estados inválidos/costos negativos/duplicados
├── credentials.json          ⚠️ NO commitear — en .gitignore
└── .env
```

---

## Estado por fases

| Fase | Estado | Notas |
|---|---|---|
| Fase 0 — Fundación | ✅ 6/6 | Completa |
| Fase 1 — Base de datos | 🔄 5/7 | Faltan: error n8n · APScheduler · docs |
| Fase 2 — Métricas | ✅ 4/4 | Completa |
| Fase 3 — Motor IA | 🔄 4/5 | Falta: sanitizar inputs |
| Fase 4 — Visualización | ⬜ 0/3 | Pendiente |
| Fase 5 — Interfaces | 🔄 1/3 | CLI listo · Web y WhatsApp pendientes |

---

## Pendientes inmediatos

- [ ] ADLY_DEBUG=false en .env — logs del JSON parser se muestran al usuario
- [ ] Probar estructura de respuesta con preguntas complejas
- [ ] Identificar error n8n — 12 leads no llegaron al Sheet (requiere acceso de Camí)
- [ ] Probar ColumnMapper con mock_ambiguo.csv subido a Google Sheets real
- [ ] Sanitizar inputs en engine.py (Fase 3 pendiente)
- [ ] DataValidator.COLUMNAS_CLAVE hardcodeada — hacerla dinámica desde config (baja prioridad, no explota)
- [ ] Identificar parámetros hardcodeados que deban ser agnósticos/configurables

---

## Pendiente de Camí

- ✅ Demo realizada — proyecto aprobado
- ✅ PDF ejecutivo: adly_brief_cami.pdf
- [ ] Compartir Sheet con adly-service@gen-lang-client-0574573686.iam.gserviceaccount.com
- [ ] Responder cuestionario 20 preguntas (enviado por WhatsApp)
- [ ] Revisar error n8n — 12 leads no llegaron

---

## Cómo correr

```bash
cd C:\Users\moonw\Proyectos\Adly
venv\Scripts\activate
python interfaces/cli/cli.py
```

## Variables .env relevantes

| Variable | Efecto |
|---|---|
| `ADLY_MOCK_CSV=data/raw/mock_ambiguo.csv` | Carga CSV externo en modo mock (activa ColumnMapper) |
| `ADLY_DEBUG=false` | Silencia logs del JSON parser |
| `GOOGLE_SHEET_ID=...` | ID del Sheet de Camí |

## Comandos CLI

/alertas · /metricas · /refresh · /limpiar · /estado · /guardar · /dashboard · /ayuda · salir

---

## Errores conocidos

| Error | Causa | Solución |
|---|---|---|
| WARNING JSON parser visible | ADLY_DEBUG no configurado | ADLY_DEBUG=false en .env |
| Ollama puerto 11434 | Servidor no corriendo | Abrir desde bandeja sistema |
| qwen2.5-coder respuestas pobres | Modelo de código, no marketing | Usar Gemini o Groq |
| google.generativeai deprecada | Google migró | Migrar a google.genai (pendiente) |

---

## Métricas que maneja

Embudo: Leads · MQL · SQL · Venta · CPL · CPMQL · CPSQL · CPA · Tasas de conversión
Pauta: CTR · CPC · CPM · ROAS · Frecuencia · Saturación
Comparativo: Ranking eficiencia · Benchmark · Índice calidad lead · Overlap audiencias
