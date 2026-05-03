# MAESTRO ADLY
> Pegar junto con CLAUDE.md cuando la sesión sea sobre Adly
> Última actualización: 2026-05-02

---

## Qué es

**Observador de integridad de datos de marketing con interfaz conversacional.**
Adly no confía ciegamente en ninguna fuente. Lee lo que entra y sale de Meta Ads y GHL, lo compara contra la fuente de verdad local (Sheets / DB), detecta inconsistencias, y responde preguntas con contexto explícito sobre la confiabilidad del dato.

Primer módulo de Data-Buddy en producción real con cliente real.

**Cliente 0:** Camí (hermano de Nico) — director de marketing, agencia pequeña. Cliente y socio.

**Premisa de diseño:** Adly asume siempre que hay error. No es solo un chatbot de analytics — es una capa de integridad de datos con LLM encima.

**Diferenciador clave:** Eficiencia de tokens. System prompt comprimido (~430 tokens vs ~1,670 original), helper `_env()` que resuelve variables vacías, multi-provider robusto. Esto diferencia Adly de usar Claude/Kimi directamente — funciona eficientemente con cualquier modelo free/paid.

**Tres problemas que resuelve:**
1. Consistencia — Meta, GHL y Sheet con discrepancias estructurales
2. Análisis — métricas en tiempo real por lenguaje natural con confidence score explícito
3. Recomendaciones accionables — qué pausar, escalar, ajustar, y con qué nivel de certeza

---

## Stack

Python · gspread · pandas · numpy · FastAPI · APScheduler · Groq + Llama 3.3 70b · Rich · Plotly · rapidfuzz
Frontend: React + Vite · Tailwind CSS · Framer Motion · React Router

**Versiones fijadas (no cambiar sin probar):**
- `groq==0.4.2` — versión superior rompe con httpx
- `httpx==0.27.0` — versión superior no acepta argumento `proxies`

---

## Skills instaladas en Claude Code

Ubicación: `C:\Users\moonw\Proyectos\.claude\skills\`

| Skill | Comandos clave | Para qué |
|---|---|---|
| **impeccable** | `/animate` `/audit` `/critique` `/polish` `/overdrive` `/bolder` `/colorize` `/harden` | Auditoría y mejora estética general |
| **emilkowalski** | automático | Animaciones y micro-interacciones de nivel profesional |
| **refactoring-ui** | `/ui-refactor` `/fix-hierarchy` `/fix-typography` | Auditoría visual, jerarquía, espaciado |

**Regla:** Antes de tocar cualquier archivo frontend, correr `/audit` primero.
**Modelo:** Sonnet para código/componentes/animaciones. Opus para arquitectura profunda o cuando Sonnet falla repetidamente.

---

## Visión UI — Home page (definitiva)

Adly ES un chat. La home nunca debió ser un dashboard.
Referencia visual: **https://codewiki.google/** — gradiente vivo, hero full screen, scroll reveal.

```
/ (ruta home)
│
├── HERO — 100vh, full screen
│   ├── Fondo negro #000 con halo naranja #e8742a respirando lentamente
│   ├── "Adly" — tipografía enorme, display bold, mucho aire
│   ├── Subtítulo — "Tu analista de datos de marketing"
│   ├── Input de chat centrado y prominente
│   └── Adly flotante (el Clippy) sobre el gradiente
│
└── SCROLL ↓ — secciones que aparecen al bajar
    ├── Análisis recientes — historial de conversaciones
    ├── Comandos rápidos — /metricas, /embudo, /rfm...
    └── Estado del dataset activo — integridad, freshness
```

**Principios:** Gradiente naranja ES la identidad. Movimiento lento y orgánico. Input del chat = CTA principal. Sin dashboard en el hero.
**Efecto visual:** Shimmer loading como estética permanente — barrido de luz naranja (8s/ciclo) sobre negro.

---

## Flujo de datos — arquitectura por capas

```
CAPA 0 — FUENTES EXTERNAS (solo lectura)
  Meta Ads API v22 ⚠️ attribution drift  |  GHL API v2 ⚠️ webhook loss
        ↓
CAPA 1 — INGESTA DEFENSIVA
  n8n + Ingestor Python · System User Token · Async Jobs · Backoff exponencial
        ↓
CAPA 2 — VALIDACIÓN & NORMALIZACIÓN
  Schema Fingerprint · Timezone→UTC · Attribution Metadata · Confidence Scorer
        ↓
CAPA 3 — STORE LOCAL (fuente de verdad de Adly)
  Google Sheets (Fase 1-2) → SQLite/Postgres (Fase 3+)
        ↓
CAPA 4 — ENGINE ADLY
  engine.py · metrics.py · validation.py · Reconciliador Meta↔GHL
        ↓
CAPA 5 — LLM + RESPUESTA
  Groq + Llama 3.3 70b (principal) · Gemini Flash (fallback) · Ollama (local)
        ↓
CAPA 6 — INTERFAZ
  CLI v5 (✅) · Web UI React (✅ conectada) · API REST FastAPI (✅ MVP)
```

**Regla de oro:** CRM siempre gana sobre el Sheet. Pero ambos pueden estar mal — Adly lo dice.

---

## Estructura de archivos

```
Adly/
├── src/
│   ├── ingestion/
│   │   ├── mock_data.py        ✅ Mock A/B/C/D
│   │   ├── sheets.py           ✅ BaseConnector · SheetsConnector · MockConnector
│   │   ├── meta_ingestor.py    ⬜ PENDIENTE FASE 2
│   │   └── ghl_ingestor.py     ⬜ PENDIENTE FASE 2
│   ├── processing/
│   │   ├── column_mapper.py    ✅
│   │   ├── value_mapper.py     ✅
│   │   ├── validation.py       ✅
│   │   ├── alerts.py           ✅
│   │   ├── metrics.py          ✅ resumen_ejecutivo_llm() comprimido
│   │   ├── schema_watcher.py   ✅
│   │   ├── query_engine.py     ✅ v2 cruce adset×estado resuelto
│   │   └── reconciler.py       ⬜ PENDIENTE FASE 2
│   └── ai/
│       └── engine.py           ✅ v4 + _env() helper + hot-reload LLM + system prompt -74% tokens
│   └── api/
│       ├── main.py             ✅
│       ├── state.py            ✅
│       ├── limiter.py          ✅
│       └── routes/
│           ├── analyses.py     ✅
│           ├── chat.py         ✅ manejo CONFIRMAR sin LLM
│           └── config.py       ✅
├── interfaces/
│   ├── cli/
│   │   ├── theme.py            ✅
│   │   ├── renderer.py         ✅
│   │   ├── commands.py         ✅ todos los comandos probados
│   │   ├── onboarding.py       ✅
│   │   └── cli.py              ✅
│   └── web/                    ✅ CONECTADA AL ENGINE REAL
│       └── .env.local          ⚠️ VITE_MOCK=false — no revertir
├── data/raw/
│   ├── mock_ghl.csv            ✅ 500 leads
│   ├── mock_sheet.csv          ✅
│   ├── mock_ambiguo.csv        ✅ 300 leads
│   └── mock_danado.csv         ✅ 206 leads
├── requirements.txt            ⚠️ agregar rapidfuzz>=3.0.0
└── .env                        ✅ sin comillas, rutas relativas
```

---

## Estado actual — 2026-05-02

### ✅ Completado en sesión 2026-05-02

| Archivo | Cambio |
|---|---|
| `query_engine.py` | Fix cruce adset×estado — executor ranking separado en 2 casos: con val_est (filtra + cruza) y sin val_est (fallback venta) |
| `commands.py` | Tests completos contra mock_danado.csv — todos los comandos pendientes funcionando |
| `interfaces/web/.env.local` | `VITE_MOCK=false` — Web UI conectada al backend real |
| `requirements.txt` | `groq==0.4.2` + `httpx==0.27.0` — fix incompatibilidad proxies |

### Tests de comandos — estado actual (mock_danado.csv)

| Comando | Estado |
|---|---|
| `/columnas` | ✅ |
| `/nulos` | ✅ |
| `/describe` | ✅ |
| `/head` | ✅ |
| `/sample` | ✅ |
| `/alertas` | ✅ |
| `/metricas` | ✅ |
| `/embudo` | ✅ |
| `/config` + hot-reload | ✅ |
| `/outliers` | ✅ 8 outliers en costo_lead |
| `/correlacion` | ✅ aviso correcto (1 col numérica) |
| `/limpiar_duplicados` | ✅ 6 duplicados → 200 filas |
| `/cohorts` | ✅ 4 cohortes, conversión ene→mar creciente |
| `/rfm` | ✅ usa costo_lead como proxy Monetary |
| `/rentabilidad` | ✅ aviso correcto (sin valor_venta) |
| `/velocidad` | ✅ aviso correcto (sin fecha_cierre) |
| Chat básico Web UI | ✅ engine real respondiendo |

### ⚠️ Problemas conocidos — roadmap

- [ ] **"ranking de campañas con perdidos"** — "de X por Y" no tokeniza bien col_agr. Se resuelve en v2 intent por LLM
- [ ] **Pregunta de seguimiento sin contexto** — "¿de qué campañas son?" después de un resultado falla
- [ ] **Intent por LLM** — reemplazar keywords de `_detectar_intent()`. En roadmap post 30 días Camí

### 🔄 Pendientes inmediatos

- [ ] **Chat sin dataset** — modo conversacional donde Adly responde sin CSV/Sheet cargado y guía al usuario a conectar su fuente. **Próxima sesión**
- [ ] **requirements.txt** — agregar `rapidfuzz>=3.0.0`
- [ ] **GitHub** — subir repo privado
- [ ] **Conectar Sheet real de Camí** — pendiente por disponibilidad de Camí
- [ ] **docs/errores_y_soluciones.md** — documentar bugs resueltos
- [ ] **Layout recostado izquierda** — `#root` sin `margin: auto`
- [ ] **AdlyFloat** — imágenes con fondo transparente

---

## Cómo levantar el proyecto

```bash
# Terminal 1 — backend
cd C:\Users\moonw\Proyectos\Adly
.venv\Scripts\activate
uvicorn src.api.main:app --reload --port 8000

# Terminal 2 — frontend
cd C:\Users\moonw\Proyectos\Adly\interfaces\web
npm run dev
```

**Verificar antes de levantar:**
- `.env` en raíz tiene `GROQ_API_KEY` sin comillas
- `interfaces/web/.env.local` tiene `VITE_MOCK=false`
- venv activo con `groq==0.4.2` y `httpx==0.27.0`

---

## Tokens por request — estado actual

| Componente | Tokens aprox |
|---|---|
| System prompt base | ~431 (era ~1,670) |
| resumen_ejecutivo_llm() | ~375 |
| schema_llm | ~180 |
| Último resultado pandas | ~200 |
| Pregunta del usuario | ~20 |
| **Total por request** | **~1,206** |

Antes: ~2,445 tokens. Ahora: ~1,206. **Preguntas por minuto Groq free: ~8 (era ~4).**

---

## Query Engine — estado y roadmap

### v2 — cruce adset×estado ✅

**Resuelto en sesión 2026-05-02:**
- Executor ranking separado en 2 casos: `col_est + val_est` → filtra df por estado antes de agrupar, muestra volumen + tasa. `col_est` sin `val_est` → fallback a venta.
- Funciona: "adset con más perdidos", "campaña con más ventas", "top adset por leads"
- Falla aún: "ranking de campañas con perdidos" (tokenización de "de X")

**Limitaciones conocidas:**
- Cruce con "de X por Y" no tokeniza bien col_agr
- Intent por keywords — falla con frases semánticas sin keywords explícitos
- Pregunta de seguimiento sin contexto prev

### v3 — Intent por LLM (Roadmap)
Reemplazar `_detectar_intent()` por llamada a LLM liviano.
Criterio de arranque: después de que Camí use Adly 30 días.

### v4 — Queryn Text-to-Pandas (Fase 2)
LLM pequeño genera código pandas → executor sandbox → LLM grande formatea.

---

## Roadmap SaaS

| Fase | Objetivo | Criterio de salida |
|---|---|---|
| **Fase 1** | Camí lo usa hoy | CLI + Sheet real. Camí confía en los números. |
| **Fase 2** | Ingesta defensiva | meta_ingestor + ghl_ingestor. Reconciliador. |
| **Fase 3** | Web UI + multi-cliente | FastAPI + React. Postgres. +1 cliente activo. Onboarding conversacional sin dataset. |
| **Fase 4** | SaaS competitivo | Onboarding self-serve. Billing. Benchmarks. |

**Criterio Fase 1→2:** Camí usa Adly 30 días consecutivos y confía en los números.

**Roadmap Fase 3 — chat sin dataset:**
Adly responde sin CSV/Sheet cargado. Modo conversacional: explica conceptos, sugiere análisis, y guía al usuario paso a paso para conectar su fuente (Sheet ID, subir CSV). Onboarding desde el chat mismo.

---

## Mapa de riesgos conocidos

- **R1** Meta rate limit: 200 calls/hora. Batch requests obligatorio.
- **R2** Meta attribution window cambia sin aviso.
- **R3** GHL webhook puede perderse. Log + reconciliación periódica.
- **R13** Nunca pasar PII al prompt. IDs anonimizados.
- **R14** Si campo es null → decirlo explícitamente.
- **R15** Toda respuesta incluye `data_freshness` y `confidence_note`.
- **R16** Adly admite ignorancia. "No tengo ese dato" > número inventado.
- **R17** Groq free ~8 preguntas/minuto con system prompt optimizado.

---

## Comandos CLI — referencia rápida

### Exploración
`/columnas` · `/nulos` · `/describe` · `/head [N]` · `/sample [N]` · `/unicos [col]` · `/rango [col]` · `/top [col] [N]`

### Estadística
`/outliers [col]` · `/correlacion`

### Modelos de marketing
`/cohorts` · `/rentabilidad` · `/rfm` · `/embudo [campaña]` · `/velocidad`

### Limpieza
`/limpiar_duplicados` · `/rellenar [col] [estrategia]` · `/eliminar_por [col] [op] [valor]`

### Sistema
`/config` · `/alertas` · `/metricas` · `/refresh` · `/limpiar` · `/estado` · `/guardar` · `/exportar` · `/ayuda`

---

## Dependencias

```
groq==0.4.2        ← NO actualizar, rompe con httpx superior
httpx==0.27.0      ← NO actualizar, versión superior no acepta 'proxies'
rapidfuzz>=3.0.0   ← agregar a requirements.txt
```
