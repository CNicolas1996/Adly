# MAESTRO ADLY
> Pegar junto con CLAUDE.md cuando la sesión sea sobre Adly
> Última actualización: 2026-05-07

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
  Groq + Llama 3.3 70b (principal) · Gemini 2.5 Flash (fallback) · Ollama (local)
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
│   │   ├── alerts.py           ✅ fix 2026-05-07 — DataValidator + AlertManager correctos
│   │   ├── metrics.py          ✅ resumen_ejecutivo_llm() comprimido
│   │   ├── schema_watcher.py   ✅
│   │   ├── query_engine.py     ✅ v3 Text-to-Pandas — planner Gemini + sandbox exec()
│   │   └── reconciler.py       ⬜ PENDIENTE FASE 2
│   └── ai/
│       └── engine.py           ✅ v4 + cambiar_llm() + limpiar_contexto_comando()
│   └── api/
│       ├── main.py             ✅
│       ├── state.py            ✅ pending_model + modelo_activo
│       ├── limiter.py          ✅
│       └── routes/
│           ├── analyses.py     ✅
│           ├── chat.py         ✅ fix cache bug 2026-05-07 + /alertas arreglado
│           └── config.py       ✅
├── interfaces/
│   ├── cli/
│   │   ├── theme.py            ✅
│   │   ├── renderer.py         ✅
│   │   ├── commands.py         ✅
│   │   ├── onboarding.py       ✅
│   │   └── cli.py              ✅
│   └── web/                    ✅ CONECTADA AL ENGINE REAL
│       └── .env.local          ⚠️ VITE_MOCK=false — no revertir
├── data/raw/
│   ├── mock_ghl.csv            ✅ 500 leads
│   ├── mock_sheet.csv          ✅
│   ├── mock_ambiguo.csv        ✅ 300 leads
│   ├── mock_danado.csv         ✅ 206 leads
│   └── cami_real.csv           ⚠️ NUEVO — datos reales de Camí, NO subir a GitHub
├── requirements.txt            ⚠️ agregar rapidfuzz>=3.0.0
└── .env                        ✅ sin comillas, rutas relativas
```

---

## Estado actual — 2026-05-07

### ✅ Completado en sesión 2026-05-07

| Archivo | Cambio |
|---|---|
| `src/ai/engine.py` | `limpiar_contexto_comando()` — nuevo método. Limpia `_ultimo_resumen` entre preguntas para evitar contaminación de contexto |
| `src/api/routes/chat.py` | **Fix bug cache** — detecta si pregunta es seguimiento (`_REFS_PREVIAS`) o nueva. Si es nueva sin resultado pandas → limpia contexto anterior |
| `src/api/routes/chat.py` | **Fix `/alertas`** — reescrito con `DataValidator` de `validation.py` + `AlertManager` de `alerts.py`. Auto-detecta columnas. En Fase 1 corre con un solo df |
| `DataTable.jsx` | ✅ Scroll horizontal funcionando |

### Tests de comandos Web UI — mock_ghl.csv (2026-05-07)

| Comando | Estado |
|---|---|
| `/columnas` | ✅ |
| `/nulos` | ✅ |
| `/describe` | ✅ |
| `/head [N]` | ✅ |
| `/sample [N]` | ✅ |
| `/alertas` | ✅ fix 2026-05-07 — Score 100% con mock |
| `/metricas` | ✅ |
| `/embudo` | ✅ |
| `/cohorts` | ✅ |
| `/rfm` | ✅ |
| `/rentabilidad` | ✅ |
| `/velocidad` | ✅ |
| `/outliers` | ✅ |
| `/correlacion` | ✅ |
| `/unicos` | ✅ |
| `/rango` | ✅ |
| `/top` | ✅ |
| `/estado` | ✅ |
| `/modelo` | ✅ |

### Preguntas libres — estado tras fix cache (2026-05-07)

| Pregunta | Estado |
|---|---|
| "cuál campaña tiene mejor conversión" | ✅ |
| "cuál campaña me cuesta más conseguir un cliente" | ✅ |
| "cuál anuncio me trae más plata" | ✅ |
| "qué adset tiene peor rendimiento" | ✅ |
| "ordéname las campañas de mejor a peor" | ✅ |
| "qué está fallando" | ✅ |
| "dónde meto más presupuesto" | ✅ |
| "qué pasa si le bajo el presupuesto a esa" | ✅ fix cache — ya no agarra resultado anterior |
| "qué está quemando presupuesto sin resultado" | ✅ |
| "qué campaña me tiene más enamorado y no debería" | ✅ análisis semántico correcto |
| "cómo me fue en febrero vs marzo" | ✅ |
| "compara el costo por lead entre adsets" | ✅ |
| "cuál anuncio convierte mejor en retargeting" | ⚠️ responde pero sin filtrar por campaña — confianza 70% automática |
| "si le bajo presupuesto a la peor campaña" | ✅ fix cache — responde sobre Branding correctamente |

### 🔄 Pendientes próxima sesión

- [ ] **Remover prints de debug** — `query_engine.py` y `chat.py` antes de cualquier demo
- [ ] **Probar 3 mocks restantes** — `mock_sheet`, `mock_ambiguo`, `mock_danado` con preguntas complejas
- [ ] **CSV real de Camí** — cargar `cami_real.csv` y probar engine agnóstico con datos feos (ver notas abajo)
- [ ] **`docs/errores_y_soluciones.md`** — documentar sesiones 2026-05-06 y 2026-05-07

### 🔄 Pendientes post-demo

- [ ] **Chat sin dataset** — onboarding conversacional
- [ ] **requirements.txt** — agregar `rapidfuzz>=3.0.0`
- [ ] **GitHub** — subir repo privado (⚠️ nunca incluir `cami_real.csv`)
- [ ] **Refactoring MetricsCalculator** — detección semántica vs CONFIG_DEFAULT hardcodeado
- [ ] **Layout recostado izquierda** — `#root` sin `margin: auto`
- [ ] **AdlyFloat** — imágenes con fondo transparente

### 🔬 Investigación BITACORA — no abrir antes de tener datos reales estables

- [ ] **Meta API — bots baneados** — investigar ingesta directa robusta sin triggear bans. Alimenta `meta_ingestor.py` Fase 2
- [ ] **Modelado y normalización** — estudiar 1FN/2FN/3FN y aplicar al CSV de Camí. La atribución doble viola 1FN, debería ser tabla separada. Prepara migración Sheets→Postgres Fase 3
- [ ] **Parser de atribución múltiple** — celda `"AI_AUTOMATION_FUNNEL | WhatsApp Leads | Reel IA"` son 3 atribuciones. Detectar separadores ` | `, `,`, `;`. Explotar antes de que el planner vea el df. Candidato: `attribution_parser.py` o extensión de `value_mapper.py`

---

## CSV real de Camí — notas para próxima sesión

**Archivo:** `data/raw/cami_real.csv`
**⚠️ NO subir a GitHub — datos reales de clientes**

**Schema detectado:**
- `Fecha de creacion` · `Nombre` · `correo` · `telefono`
- `ad primera atribucion` · `ad segunda atribucion`
- `stage` · `ad set primera atribucion` · `ad set segunda atribucion`

**Problemas identificados a atacar:**
- Emails rotos — `m@ría jesús753@hotmail.com` — caracteres especiales en usuario
- Duplicado real — Hilda Pomares aparece dos veces, una con `stage = Duplicate`
- Teléfonos sin prefijo internacional — `5316545371` vs `+18690534518`
- Stages en inglés mezclados — `Warm Lead`, `No Show`, `Appointment Set`, `Lead`, `Duplicate`, `Closed Lost` → `value_mapper.py` debe mapearlos
- `NONE` como string en columna ad — no es null real
- Atribución doble en columnas separadas — el engine debe entender ambas
- Atribución múltiple en una celda — `"AI_AUTOMATION_FUNNEL | WhatsApp Leads | Reel IA"`

**Qué probar:**
1. `value_mapper.py` — ¿mapea los stages correctamente?
2. `schema_watcher.py` — detecta schema completamente diferente al mock
3. Planner — columnas con espacios y tildes en nombres
4. `/alertas` — debe mostrar duplicados reales

---

## Query Engine v3 — Text-to-Pandas

### Arquitectura (2026-05-06)

```
pregunta
    ↓
CAPA 1 — Schema Reader (dinámico — lee el df real)
    ↓
CAPA 2 — Planner LLM (Gemini 2.5 Flash)
  recibe: schema real + pregunta
  genera: código pandas que asigna result = ...
    ↓
CAPA 3 — Sandbox exec() restringido
  namespace: {df, pd, builtins limitados}
  timeout: 5s
    ↓
CAPA 4 — Validador
  verifica: result no es None/vacío/todo NaN
    ↓
CAPA 5 — Re-prompt (máx 2 intentos)
  si falla: le pasa el error al planner para corregir
    ↓
RESULTADO serializado → LLM principal lo formatea
```

**Ventaja clave:** funciona con cualquier schema de cliente — no hay columnas hardcodeadas. Juanito con columnas raras funciona igual que Paco con columnas simples.

### /modelo — comando de cambio de LLM

```
/modelo              → tabla de modelos disponibles con estado de API key
/modelo gemini       → cambia a Gemini (si tiene key → cambia directo)
/modelo openai       → pide API key si no existe → la guarda en .env con máscara ****
```

**Modelos soportados:** groq · gemini · openai · deepseek · qwen · ollama

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
- `.env` en raíz tiene `GROQ_API_KEY` y `GEMINI_API_KEY` sin comillas
- `interfaces/web/.env.local` tiene `VITE_MOCK=false`
- venv activo con `groq==0.4.2` y `httpx==0.27.0`

---

## Tokens por request — estado actual

| Componente | Tokens aprox |
|---|---|
| System prompt base | ~431 |
| resumen_ejecutivo_llm() | ~375 |
| schema_llm | ~180 |
| Último resultado pandas | ~200 |
| Pregunta del usuario | ~20 |
| **Total por request** | **~1,206** |

**Planner adicional:** ~300 tokens por pregunta que activa Text-to-Pandas (schema + pregunta + código generado).

---

## Roadmap SaaS

| Fase | Objetivo | Criterio de salida |
|---|---|---|
| **Fase 1** | Camí lo usa hoy | CLI + Sheet real. Camí confía en los números. |
| **Fase 2** | Ingesta defensiva | meta_ingestor + ghl_ingestor. Reconciliador. |
| **Fase 3** | Web UI + multi-cliente | FastAPI + React. Postgres. +1 cliente activo. Onboarding conversacional sin dataset. |
| **Fase 4** | SaaS competitivo | Onboarding self-serve. Billing. Benchmarks. |

**Criterio Fase 1→2:** Camí usa Adly 30 días consecutivos y confía en los números.

---

## Mapa de riesgos conocidos

- **R1** Meta rate limit: 200 calls/hora. Batch requests obligatorio.
- **R2** Meta attribution window cambia sin aviso.
- **R3** GHL webhook puede perderse. Log + reconciliación periódica.
- **R13** Nunca pasar PII al prompt. IDs anonimizados.
- **R14** Si campo es null → decirlo explícitamente.
- **R15** Toda respuesta incluye `data_freshness` y `confidence_note`.
- **R16** Adly admite ignorancia. "No tengo ese dato" > número inventado.
- **R17** Groq free ~8 preguntas/minuto. Con Gemini como principal: sin rate limit relevante.

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
`/config` · `/alertas` · `/metricas` · `/refresh` · `/limpiar` · `/estado` · `/guardar` · `/exportar` · `/ayuda` · `/modelo [nombre]`

---

## Dependencias

```
groq==0.4.2        ← NO actualizar, rompe con httpx superior
httpx==0.27.0      ← NO actualizar, versión superior no acepta 'proxies'
rapidfuzz>=3.0.0   ← agregar a requirements.txt
google-generativeai ← ya instalado
```

---

## Fallback LLM — estado

| Proveedor | Estado |
|---|---|
| Groq `llama-3.3-70b-versatile` | ✅ principal — rate limit 100k tokens/día free |
| Gemini `gemini-2.5-flash` | ✅ fallback operativo · planner usa este |
| Ollama | ❌ no corriendo — excluido del fallback chain |

`.env` fallback chain: `groq,gemini`

**Nota:** el planner de query_engine v3 usa Gemini directamente vía `google.generativeai` — independiente del fallback chain del engine principal.
