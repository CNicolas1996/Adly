# MAESTRO ADLY
> Pegar junto con CLAUDE.md cuando la sesión sea sobre Adly
> Última actualización: 2026-04-22 (sesión backend FastAPI + estética global + debug engine)

---

## Qué es

**Observador de integridad de datos de marketing con interfaz conversacional.**
Adly no confía ciegamente en ninguna fuente. Lee lo que entra y sale de Meta Ads y GHL, lo compara contra la fuente de verdad local (Sheets / DB), detecta inconsistencias, y responde preguntas con contexto explícito sobre la confiabilidad del dato.

Primer módulo de Data-Buddy en producción real con cliente real.

**Cliente 0:** Camí (hermano de Nico) — director de marketing, agencia pequeña. Cliente y socio.

**Premisa de diseño:** Adly asume siempre que hay error. No es solo un chatbot de analytics — es una capa de integridad de datos con LLM encima.

**Tres problemas que resuelve:**
1. Consistencia — Meta, GHL y Sheet con discrepancias estructurales (no solo errores)
2. Análisis — métricas en tiempo real por lenguaje natural con confidence score explícito
3. Recomendaciones accionables — qué pausar, escalar, ajustar, y con qué nivel de certeza

---

## Stack

Python · gspread · pandas · numpy · FastAPI · APScheduler · Groq + Llama 3.3 70b · Rich · Plotly
Frontend: React + Vite · Tailwind CSS · Framer Motion · React Router

---

## Skills instaladas en Claude Code

Ubicación: `C:\Users\moonw\Proyectos\.claude\skills\`

| Skill | Comandos clave | Para qué |
|---|---|---|
| **impeccable** | `/animate` `/audit` `/critique` `/polish` `/overdrive` `/bolder` `/colorize` `/harden` | Auditoría y mejora estética general |
| **emilkowalski** | automático | Animaciones y micro-interacciones de nivel profesional |
| **refactoring-ui** | `/ui-refactor` `/fix-hierarchy` `/fix-typography` | Auditoría visual, jerarquía, espaciado |

**Regla:** Antes de tocar cualquier archivo frontend, correr `/audit` primero. Antes de animar, correr `/animate` con contexto específico.

**Modelo:** Sonnet para código/componentes/animaciones. Opus para arquitectura profunda o cuando Sonnet falla repetidamente.

---

## Visión UI — Home page (definitiva)

Adly ES un chat. La home nunca debió ser un dashboard.
Referencia visual: **https://codewiki.google/** — gradiente vivo, hero full screen, scroll reveal.

```
/ (ruta home)
│
├── HERO — 100vh, full screen
│   ├── Fondo negro #000 con halo naranja #e8742a
│   │   respirando lentamente (radial gradient animado,
│   │   igual al azul de Code Wiki pero en naranja)
│   ├── "Adly" — tipografía enorme, display bold, mucho aire
│   ├── Subtítulo — "Tu analista de datos de marketing"
│   ├── Input de chat centrado y prominente
│   │   → escribes una pregunta → arranca análisis nuevo
│   │   → o seleccionas uno existente del historial
│   └── Adly flotante (el Clippy) sobre el gradiente
│
└── SCROLL ↓ — secciones que aparecen al bajar
    ├── Análisis recientes — historial de conversaciones
    ├── Comandos rápidos — /metricas, /embudo, /rfm...
    └── Estado del dataset activo — integridad, freshness
```

**Principios de diseño:**
- El gradiente naranja ES la identidad — no decoración, es la UI
- Movimiento lento y orgánico — nunca rápido ni agresivo
- Tipografía enorme en el hero — Adly manda, no el contenido
- El input del chat es el CTA principal — no hay botones, solo escribir
- Al scrollear el contenido aparece con fade suave (Framer Motion)
- Sin dashboard, sin cards de métricas en el hero — eso va en el chat

**Efecto visual:** Shimmer loading effect aplicado como estética permanente del fondo.
El mismo efecto de skeleton/carga pero como identidad visual — barrido de luz naranja
moviéndose muy lento (8s/ciclo) sobre fondo negro.

**Implementación:**
- CSS `linear-gradient` animado con `@keyframes shimmer` — no librería externa
- `background-size: 200%` + `background-position` animado de -200% a 200%
- Ciclo lento: 8-12 segundos, `ease-in-out infinite`
- Framer Motion `whileInView` para reveal al scrollear
- El input conecta directo con `POST /api/chat` o crea análisis nuevo
- Historial cargado desde `GET /api/analyses`

---

## Flujo de datos — arquitectura por capas

```
CAPA 0 — FUENTES EXTERNAS (solo lectura)
  Meta Ads API v22  ⚠️ attribution drift  |  GHL API v2  ⚠️ webhook loss
        ↓                                          ↓
CAPA 1 — INGESTA DEFENSIVA
  n8n (automatización) + Ingestor Python
  System User Token · Async Jobs · Backoff exponencial · Header Monitor
        ↓
CAPA 2 — VALIDACIÓN & NORMALIZACIÓN
  Schema Fingerprint · Timezone → UTC · Attribution Metadata · Confidence Scorer
        ↓
CAPA 3 — STORE LOCAL (fuente de verdad de Adly)
  Google Sheets (Fase 1-2) → SQLite/Postgres (Fase 3+)
  Cache + Timestamps · Snapshot histórico
        ↓
CAPA 4 — ENGINE ADLY
  engine.py · metrics.py · validation.py · Reconciliador Meta↔GHL
        ↓
CAPA 5 — LLM + RESPUESTA
  Groq + Llama 3.3 70b
  Prompt con contexto de confiabilidad → RespuestaAdly (JSON estructurado)
        ↓
CAPA 6 — INTERFAZ
  CLI v5 (✅) · Web UI React (🔄 en desarrollo) · API REST FastAPI (✅ MVP)
```

**Regla de oro:** CRM siempre gana sobre el Sheet. Pero ambos pueden estar mal — Adly lo dice.

---

## Estructura de archivos

```
Adly/
├── src/
│   ├── ingestion/
│   │   ├── mock_data.py        ✅ Mock A (500 leads) · Mock B · Mock C (dañado) · Mock D (ambiguo)
│   │   ├── sheets.py           ✅ BaseConnector · SheetsConnector · MockConnector
│   │   ├── meta_ingestor.py    ⬜ PENDIENTE FASE 2
│   │   └── ghl_ingestor.py     ⬜ PENDIENTE FASE 2
│   ├── processing/
│   │   ├── column_mapper.py    ✅
│   │   ├── value_mapper.py     ✅
│   │   ├── validation.py       ✅
│   │   ├── alerts.py           ✅
│   │   ├── metrics.py          ✅ inmune a columnas ausentes (fix sesión 2026-04-22)
│   │   ├── schema_watcher.py   ✅
│   │   └── reconciler.py       ⬜ PENDIENTE FASE 2
│   └── ai/
│       └── engine.py           ✅ v3
│   └── api/                    ✅ NUEVO — FastAPI backend completo
│       ├── main.py             ✅ CORS · rate limiting · routers
│       ├── state.py            ✅ AppState singleton · LRU 50 sesiones · OrderedDict
│       ├── limiter.py          ✅ SlowAPI rate limiting por IP
│       └── routes/
│           ├── analyses.py     ✅ upload CSV · Google Sheets · métricas · engine init
│           ├── chat.py         ✅ mensajes · comandos /rfm /cohorts /embudo · LLM bridge
│           └── config.py       ✅ GET/POST config · test connection
├── interfaces/
│   ├── cli/
│   │   ├── theme.py            ✅
│   │   ├── renderer.py         ✅
│   │   ├── commands.py         ✅ v4
│   │   ├── onboarding.py       ✅
│   │   └── cli.py              ✅ v5
│   └── web/                    🔄 EN DESARROLLO — React + Vite
│       ├── public/
│       │   ├── favicon.ico
│       │   └── seals/          ✅ idle.png · error.svg · thinking.svg · sleep.svg · happy.svg · warning.svg · alert.svg
│       ├── src/
│       │   ├── App.jsx         ✅ halo global aplicado · sidebar glass effect
│       │   ├── context/
│       │   │   └── AdlyContext.jsx  ✅ state machine + 30s sleep timer
│       │   ├── api/
│       │   │   └── client.js   ✅ mock completo · VITE_MOCK=true activo
│       │   ├── pages/
│       │   │   ├── Splash.jsx       ✅ huella de gato SVG como barra de carga ✅
│       │   │   ├── Onboarding.jsx   ✅ wizard 4 pasos · halo global heredado
│       │   │   ├── Home.jsx         ✅ halo naranja · scroll reveal Framer Motion · input scanner
│       │   │   ├── NewAnalysis.jsx  ✅ upload CSV real + Google Sheets input
│       │   │   └── Chat.jsx         ✅ chat funcional · typing indicator = huellas de gato ✅
│       │   ├── components/
│       │   │   ├── adly/       ⚠️ AdlyFloat.jsx — return null (oculto hasta tener imágenes limpias)
│       │   │   ├── chat/       ✅ ChatWindow · Message · DataTable · ConfidenceBar · InputZone
│       │   │   │               ✅ Typing indicator = 4 huellas de gato SVG inline animadas
│       │   │   ├── sidebar/    ✅ Sidebar · DatasetCard · CommandList · IntegrityBar
│       │   │   └── ui/         ✅ Badge · Spinner · Transition
│       │   ├── hooks/          ✅ useMousePosition · useAdlyState · useAnalysis
│       │   └── styles/
│       │       └── index.css   ✅ halo global .adly-bg · @keyframes halo-breathe · border-scan
│       ├── .env.local          ✅ VITE_MOCK=true · VITE_API_URL=http://localhost:8000
│       ├── package.json        ✅
│       └── vite.config.js      ✅ proxy → localhost:8000
├── Imagenes/                   ✅ SVGs originales del gato (fondo beige — pendiente rehacer con transparencia)
├── data/raw/
│   ├── mock_ghl.csv            ✅ 500 leads
│   ├── mock_sheet.csv          ✅
│   ├── mock_ambiguo.csv        ✅ 300 leads
│   └── mock_danado.csv         ✅ 206 leads
├── .adly_schema.json           ✅
├── .env                        ⚠️ NO commitear — sin comillas simples en variables
└── credentials.json            ⚠️ NO commitear
```

---

## Cómo correr

### CLI (ya funciona)
```bash
cd C:\Users\moonw\Proyectos\Adly
venv\Scripts\activate
python interfaces/cli/cli.py
```

### Web UI con mock (funciona hoy)
```bash
# .env.local debe tener VITE_MOCK=true
cd C:\Users\moonw\Proyectos\Adly\interfaces\web
npm run dev
# → http://localhost:5173
```

### Web UI + Backend real (próximo — CORS preflight pendiente)
```bash
# Terminal 1 — FastAPI
cd C:\Users\moonw\Proyectos\Adly
venv\Scripts\activate
uvicorn src.api.main:app --reload --port 8000

# Terminal 2 — React
cd interfaces/web
npm run dev
# Cambiar .env.local a VITE_MOCK=false
```

---

## Estado por fases

| Fase | Estado | Notas |
|---|---|---|
| **Fase 1** CLI + Sheet real | 🔄 En progreso | CLI funciona · Sheet de Camí pendiente |
| **Fase 2** Ingesta defensiva | ⬜ Pendiente | meta_ingestor + ghl_ingestor + reconciler |
| **Fase 3** Web UI + multi-cliente | 🔄 En progreso | React UI + FastAPI MVP listos · conexión browser pendiente |
| **Fase 4** SaaS competitivo | ⬜ Futuro | Onboarding self-serve · Billing |

---

## Pendientes inmediatos (próxima sesión)

- [ ] **CORS preflight fix** — frontend browser no conecta al backend (CLI sí funciona) — revisar con Antigravity
- [ ] **engine.py saludo fix** — saludos cortos (<10 chars) disparan respuesta del LLM con contexto — hardcodear respuesta de saludo sin llamar al LLM
- [ ] **AdlyFloat** — imágenes del gato con fondo transparente real, luego restaurar
- [ ] **Glass effect sidebar** — no se notó el blur, revisar backdropFilter
- [ ] `/colorize` en Claude Code — reemplazar 51 colores hardcodeados por tokens
- [ ] Subir repo a GitHub (privado)
- [ ] `docs/errores_y_soluciones.md`

## Pendientes arquitecturales (Fase 2)

- [ ] `meta_ingestor.py` — System User Token, async, backoff
- [ ] `ghl_ingestor.py` — webhook listener, mapeo por UUID
- [ ] `reconciler.py` — comparar Meta vs GHL, flag discrepancias
- [ ] Normalización timezone UTC en ingesta
- [ ] Contexto de comandos → migrar a `ContextoComando` dataclass

---

## Pendientes técnicos menores

- [ ] Migrar `google.generativeai` deprecada a `google.genai`
- [ ] `docs/flujo_de_datos.md`
- [ ] SQLite persistencia — analyses + messages + config (reemplazar state.py in-memory)

## Pendiente de Camí

- ✅ Demo realizada — proyecto aprobado
- [ ] Hablar con Camí: GHL API v1 o v2 · Timezone Meta · Campos clave CRM
- [ ] Compartir Sheet con `adly-service@gen-lang-client-0574573686.iam.gserviceaccount.com`
- [ ] Revisar error n8n — 12 leads no llegaron
- [ ] Logs del n8n donde fallaron los 12 leads

---

## Animaciones implementadas

### Typing indicator — huellas de gato ✅
- 4 huellas SVG inline en `ChatWindow.jsx`
- Secuencia de caminata: izquierda delantera → derecha trasera → derecha delantera → izquierda trasera
- Color `#e8742a`

### Halo global ✅ (sesión 2026-04-22)
- Clase `.adly-bg` en `index.css` — aplica a todas las rutas
- `@keyframes halo-breathe` — escala 1→1.08 cada 5s
- Aplicado en `App.jsx` wrapper principal

### Barra de carga Splash ✅ (sesión 2026-04-22)
- Huella de gato SVG con clipPath animado
- Se llena de `#e8742a` según progreso
- Texto "cargando... X%" debajo

### Input scanner ✅ (sesión 2026-04-22)
- Luz que recorre el borde del input en Home
- `@keyframes border-scan` — 2.5s linear infinite

### Scroll reveal ✅ (sesión 2026-04-22)
- Framer Motion `whileInView` en secciones de Home
- Fade + slide suave, delay escalonado

### AdlyFloat ⚠️ OCULTO
- `return null` en `AdlyFloat.jsx`
- Restaurar cuando imágenes del gato tengan fondo transparente
- Plan v2 intacto: cola wiggle, parpadeo orgánico, bounce spring, crossfade, hover→happy, sleep 30s

---

## AdlyFloat — Plan v2 (cuando imágenes estén listas)

- **Cola con física CSS** — `@keyframes` con wiggle independiente
- **Parpadeo orgánico** — `@keyframes blink` con timing aleatorio via JS
- **Bounce idle más suave** — spring `cubic-bezier(0.34, 1.56, 0.64, 1)`
- **Transición entre estados** — crossfade de 300ms entre SVGs
- **Reacción al hover** — happy state, vuelve a idle al salir
- **Sleep mode** — después de 30s inactivo: ojos cerrados + ZZZ flotando
- **mix-blend-mode: multiply** — para transparencia del fondo beige

SVGs disponibles en `public/seals/`:
`idle.png` · `error.svg` · `thinking.svg` · `sleep.svg` · `happy.svg` · `warning.svg` · `alert.svg`

---

## Seguridad backend (implementado sesión 2026-04-22)

| Riesgo | Implementación |
|---|---|
| DoS por archivos masivos | Límite 25MB en `analyses.py` |
| Abuso de LLM | Rate limit 30 req/min chat · 10 req/min analyses |
| Inyección Sheets | Regex validación sheetId 30-60 chars alfanumérico |
| Memory leak | OrderedDict LRU — máx 50 sesiones, FIFO al superar |

---

## Variables .env relevantes

| Variable | Efecto |
|---|---|
| `ADLY_LLM_PROVIDER=groq` | Proveedor LLM activo — sin comillas |
| `ADLY_LLM_API_KEY=gsk_...` | API key Groq — sin comillas |
| `ADLY_LLM_MODEL=llama-3.3-70b-versatile` | Modelo activo |
| `ADLY_LLM_BASE_URL=https://api.groq.com/openai/v1` | Endpoint |
| `ADLY_DEBUG=true` | Activa logs del engine en terminal |
| `ADLY_MOCK_CSV=data/raw/mock_ambiguo.csv` | CSV para modo mock |
| `GOOGLE_SHEET_ID=...` | ID del Sheet de Camí |
| `VITE_MOCK=true` | Frontend usa mock (false = FastAPI real) |
| `VITE_API_URL=http://localhost:8000` | URL del backend |

⚠️ **Regla crítica:** Todas las variables en `.env` sin comillas simples ni dobles. Python-dotenv en Windows las incluye como parte del valor.

---

## Errores conocidos y resueltos

| Error | Causa | Solución |
|---|---|---|
| NaN en `/metricas` | Leads sin campaña | Fix en `metrics._agrupar()` |
| Engine verbose en saludos | SYSTEM_PROMPT | Bypass en chat() |
| Ollama puerto 11434 | Servidor no corriendo | Abrir desde bandeja |
| google.generativeai deprecada | Google migró | Pendiente migrar a google.genai |
| /rfm NaN → int | pd.qcut con duplicados | na_option=bottom + fillna(0) |
| Footer integridad en saludos | confianza > 0.0 | Bypass en chat() |
| KeyError None en metrics | col_valor None | Guard en _limpiar_tipos |
| stdout no restaurado | try sin finally | try/finally en cli.py |
| ColumnMapper infiere mal | Muestra sucia | Muestra limpia antes de LLM |
| NaT en /cohorts | Fechas mal formateadas | Excluir NaT con advertencia |
| Estados inválidos en /embudo | Typos en dataset | ValueMapper normaliza |
| freshness sin alerta | Solo informaba | Retorna "texto\|nivel" |
| useRouterLocation no existe | Import inventado | Reemplazado por useLocation |
| Sidebar no cerraba en desktop | Sin estado toggle | App.jsx refactorizado |
| sonnet[1m] bloquea /animate | Contexto extendido | Cambiar a Default Sonnet 4.6 |
| .env con comillas simples | python-dotenv Windows | Quitar todas las comillas |
| Frontend no conecta backend | CORS preflight browser | ⬜ Pendiente fix |
| Chat responde lo mismo siempre | VITE_MOCK=true activo | Era el mock — esperado |
| Saludo dispara análisis LLM | len < 10 entra al bypass pero igual llama LLM | ⬜ Pendiente hardcodear respuesta |
| metrics.py KeyError columnas | Columnas ausentes en CSV | Fix _agrupar() + _limpiar_tipos() |

---

## Mapa de riesgos conocidos

### APIs externas
- **R1** Meta rate limit: 200 calls/hora por ad account. Batch requests obligatorio.
- **R2** Meta attribution window cambia sin aviso. Marcar ventana activa en cada registro.
- **R3** GHL webhook puede perderse. Log de eventos + reconciliación periódica.
- **R4** Leer headers de throttle antes de cada batch Meta.
- **R5** GHL: webhooks primero, polling como fallback.
- **R6** GHL: mapear custom fields por UUID, nunca por nombre.
- **R7** Ingesta programada 1x/día para histórico. Webhooks para tiempo real.

### Datos
- **R8** Normalizar timezone a UTC en ingesta.
- **R9** Cada registro: `source`, `ingested_at`, `attribution_window`, `confidence_score`.
- **R10** Schema fingerprinting antes de procesar.
- **R11** Cache obligatorio — respuesta desde último snapshot si API falla.
- **R12** Datos pre/post ene 2026 son metodologías distintas.

### LLM
- **R13** Nunca pasar PII al prompt. IDs anonimizados.
- **R14** Si campo es null → decirlo explícitamente en el prompt.
- **R15** Toda respuesta incluye `data_freshness` y `confidence_note`.
- **R16** Adly admite ignorancia. "No tengo ese dato" > número inventado.

---

## Principios de integridad de datos

| Principio | Qué significa |
|---|---|
| **Freshness explícita** | Todo dato lleva timestamp visible |
| **Confidence score** | 0-1 basado en frescura + discrepancias |
| **Discrepancia visible** | Meta vs GHL reportado explícitamente |
| **Fail loud** | Si algo falla, Adly lo dice |
| **Schema tracking** | Campo desaparece → alerta, no error silencioso |
| **Períodos marcados** | Pre/post ene 2026 requieren nota explícita |

---

## Roadmap SaaS

| Fase | Objetivo | Criterio de salida |
|---|---|---|
| **Fase 1** | Camí lo usa hoy | CLI + Sheet real. Camí confía en los números. |
| **Fase 2** | Ingesta defensiva | meta_ingestor + ghl_ingestor. Reconciliador detecta discrepancias. |
| **Fase 3** | Web UI + multi-cliente | FastAPI + React UI. Postgres. +1 cliente activo. |
| **Fase 4** | SaaS competitivo | Onboarding self-serve. Billing. Benchmarks industria. |

**Criterio Fase 1→2:** Camí usa Adly 30 días consecutivos y confía en los números.

**Ventaja competitiva:** Supermetrics/Dataslayer muestran números. Adly dice qué tan confiables son y por qué difieren. A precio de agencia latinoamericana.

---

## Comandos CLI — referencia rápida

### Exploración
| Comando | Qué hace |
|---|---|
| `/columnas` | Lista columnas con tipos y % nulos |
| `/nulos` | Ranking de columnas con más nulos |
| `/describe` | Estadísticas numéricas |
| `/head [N]` | Primeras N filas |
| `/sample [N]` | N filas aleatorias |
| `/unicos [col]` | Valores únicos con frecuencia |
| `/rango [col]` | Q1, Q3, IQR, límites outlier |
| `/top [col] [N]` | Top N más frecuentes |

### Estadística
| Comando | Qué hace |
|---|---|
| `/outliers [col]` | Detección IQR |
| `/correlacion` | Matriz de Pearson coloreada |

### Modelos de marketing
| Comando | Qué hace |
|---|---|
| `/cohorts` | Cohortes por mes |
| `/rentabilidad` | CAC / LTV / ROI por campaña |
| `/rfm` | Segmentación RFM |
| `/embudo [campaña]` | Cuello de botella del funnel |
| `/velocidad` | Días promedio lead→venta |

### Limpieza
| Comando | Qué hace |
|---|---|
| `/limpiar_duplicados` | Elimina duplicados exactos |
| `/rellenar [col] [estrategia]` | Nulos con media/mediana/moda/valor |
| `/eliminar_por [col] [op] [valor]` | Filtra filas por criterio |

### Sistema
`/alertas` · `/metricas` · `/dashboard` · `/refresh` · `/limpiar` · `/estado` · `/guardar` · `/exportar` · `/ayuda`

---

## Métricas que maneja

Embudo: Leads · MQL · SQL · Venta · CPL · CPMQL · CPSQL · CPA · Tasas de conversión
Pauta: CTR · CPC · CPM · ROAS · Frecuencia · Saturación
Marketing analytics: Cohortes · CAC · LTV · ROI · RFM · Velocidad de venta · Cuello de botella
