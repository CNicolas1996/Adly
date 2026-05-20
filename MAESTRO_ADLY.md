# MAESTRO ADLY
> Pegar junto con CLAUDE.md cuando la sesión sea sobre Adly
> Última actualización: 2026-05-14

---

## 🎯 ESTADO ACTUAL — SEMANA DEL DESPLIEGUE V1.0

**Deadline:** Viernes 22 de mayo de 2026 — Camí usando Adly desde su casa.

**Visión v1.0 acordada:**
- CLI + Web UI funcionales (✅ ya están)
- 3 bugs críticos tapados (🟡 2/3 cerrados — Bug 1 y Bug 2 ✅)
- Gráficos en respuestas del chat para `/embudo`, `/cohorts`, tendencias temporales
- Conector gspread con service account (lectura del Sheet de Camí por link compartido)
- Desplegado en **Railway**
- Fallback automático: CSV manual si Camí no comparte el Sheet a tiempo

**Bugs activos:**
- ✅ Bug 1 — NORM dinámico `metrics.py` — CERRADO 2026-05-14
- ✅ Bug 2 — NaN serialization `bridge_head/bridge_sample` — CERRADO 2026-05-14
- 🔴 Bug 3 — Umbral n≥5 para tasas — pendiente viernes 15

**Lo que NO entra en v1.0** (decidido 2026-05-14):
- Dashboards configurables → v2.0 cuando haya 3+ clientes pagando
- OAuth2 completo de Google → v1.1 si Camí lo pide
- Conexión a GHL/Meta directa → Fase 2
- Refactor `ingestion_normalizer.py` → deuda técnica, no bloquea
- Cachear SemanticInferencer en state.py → optimización, no funcionalidad
- `docs/errores_y_soluciones.md` → se empieza cuando Adly esté en producción
- `/metricas` agrupado por campaña → `cami_real.csv` no tiene col_campana real
- `/velocidad` → `cami_real.csv` no tiene fecha_cierre

**Ver `ROADMAP_V1.md` para el cronograma día por día.**

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

**Propuesta de valor pendiente de definir:** ¿Qué vende Adly frente a Kimi o Claude with Work? Responder después de que Camí lo use 2 semanas.

---

## Stack

Python · gspread · pandas · numpy · FastAPI · APScheduler · Groq + Llama 3.3 70b · Rich · Plotly · rapidfuzz · sentence-transformers
Frontend: React + Vite · Tailwind CSS · Framer Motion · React Router
**Despliegue (v1.0):** Railway

**Versiones fijadas (no cambiar sin probar):**
- `groq==0.4.2` — versión superior rompe con httpx
- `httpx==0.27.0` — versión superior no acepta argumento `proxies`
- `sentence-transformers==5.5.0` — instalado 2026-05-12, groq/httpx sobrevivieron intactos
- `torch==2.11.0` — dependencia de sentence-transformers
- `scikit-learn==1.8.0` — dependencia de sentence-transformers

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

**Mascota:** Gato naranja rechoncho, estética tinta + acuarela. Paleta: `#E8742A` / `#f5f0e8` / `#2a1f14`

---

## Visualización en v1.0 — gráficos dentro del chat

**Decisión (2026-05-14):** No hay dashboards en v1.0. Cuando Adly responda a comandos con dimensión visual obvia, devuelve gráfico inline en la respuesta.

| Comando | Gráfico | Librería |
|---------|---------|----------|
| `/embudo` | Funnel chart | Plotly |
| `/cohorts` | Heatmap | Plotly |
| Tendencias temporales | Line chart | Plotly |

Plotly ya está en el stack. El gráfico se renderiza en la respuesta del chat (no en panel aparte).
Arquitectura: backend serializa `fig.to_json()`, frontend renderiza con `react-plotly.js`.

**Lo que NO se hace en v1.0:** dashboards configurables, gráficos persistentes, exportar gráficos, gráficos para todos los comandos.

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

## Pipeline de datos interno — ACTUALIZADO 2026-05-14

```
CSV
  → SemanticInferencer.analizar(df)       # 3 capas: estadística + embeddings + stages
      → SemanticSchema                    # fuente única de verdad (dataclass tipada)
  → ingestion_normalizer.normalizar(df, schema)
  → MetricsCalculator(schema.as_config())
  → AdlyEngine.chat()
```

**Cambios sesión 2026-05-14:**
- `metrics.py` `resumen_ejecutivo_llm()`: NORM dinámico desde config — lee `estado_venta/mql/sql` en runtime
- `command_bridge.py` `bridge_head/bridge_sample`: NaN → None antes de serializar
- `semantic_inferencer.py`: sinónimos ES en `NOMBRE_DIRECTO` y `STAGE_DIRECTO`
- `value_mapper.py`: variantes underscore (`cerrado_ganado`, `no_se_presento`, etc.)
- `commands.py` `_estados_venta()`: patrones ampliados + `.strip()`

---

## Estructura de archivos

```
Adly/
├── src/
│   ├── ingestion/
│   │   ├── mock_data.py             ✅ Mock A/B/C/D
│   │   ├── sheets.py                ✅ llama normalizar() en leer() — correcto
│   │   ├── ingestion_normalizer.py  🔴 hardcodeo total — refactor pos-v1.0
│   │   ├── meta_ingestor.py         ⬜ PENDIENTE FASE 2
│   │   └── ghl_ingestor.py          ⬜ PENDIENTE FASE 2
│   ├── processing/
│   │   ├── semantic_inferencer.py   ✅ ACTUALIZADO 2026-05-14 — sinónimos ES
│   │   ├── column_mapper.py         🟡 demovido a fallback del SemanticInferencer
│   │   ├── value_mapper.py          ✅ ACTUALIZADO 2026-05-14 — variantes underscore
│   │   ├── validation.py            ✅
│   │   ├── alerts.py                ✅ fix 2026-05-07
│   │   ├── metrics.py               ✅ ACTUALIZADO 2026-05-14 — NORM dinámico
│   │   ├── schema_watcher.py        ✅
│   │   ├── query_engine.py          ✅ v3 Text-to-Pandas
│   │   └── reconciler.py            ⬜ PENDIENTE FASE 2
│   └── ai/
│       └── engine.py                ✅ agnóstico real — no tocar
│   └── api/
│       ├── main.py                  ✅
│       ├── state.py                 🟡 falta cachear SemanticInferencer aquí (pos-v1.0)
│       ├── limiter.py               ✅
│       └── routes/
│           ├── analyses.py          ✅
│           ├── chat.py              ✅
│           └── config.py            ✅
├── interfaces/
│   ├── cli/
│   │   ├── commands.py              ✅ ACTUALIZADO 2026-05-14 — _estados_venta() ampliado
│   │   └── theme.py                 ✅
│   └── web/                         ✅ React + Vite conectado al engine real
└── src/api/
    └── command_bridge.py            ✅ ACTUALIZADO 2026-05-14 — NaN fix
```

---

## Bugs activos

### ✅ Bug 1 — CERRADO 2026-05-14 — NORM hardcodeado
**Fix:** `metrics.py` `resumen_ejecutivo_llm()` — NORM_BASE + extensión dinámica desde config.

### ✅ Bug 2 — CERRADO 2026-05-14 — NaN no serializable
**Fix:** `command_bridge.py` `bridge_head/bridge_sample` — `.where(pd.notnull(sub), None)`

### 🔴 Bug 3 — MEDIO — Tasa de conversión sin advertencia de muestra pequeña
**Archivo:** `metrics.py` (`_calcular_metricas()` y `resumen_ejecutivo_llm()`)
**Síntoma:** n=1 lead que convirtió → engine reporta 100% sin warning.
**Fix:** Umbral n≥5 antes de reportar tasas; debajo de eso → "muestra insuficiente".
**Prioridad:** Viernes 15.

---

## Plan de la semana — ver ROADMAP_V1.md

**Resumen del orden de ataque:**
1. ✅ Jueves 14 (hoy) — Bug 1 + Bug 2
2. Viernes 15 — Bug 3
3. Sábado 16 — Gráficos en chat
4. Domingo 17 — Conector gspread con service account
5. Lunes 18 — Despliegue Railway
6. Martes 19 — Testing end-to-end con cami_real
7. Miércoles 20 — Pulir UI + edge cases
8. Jueves 21 — Buffer
9. Viernes 22 — Adly v1.0 listo

---

## Estado de tests

### cami_real.csv — Web UI (2026-05-14)
| Comando | Estado | Notas |
|---------|--------|-------|
| `/columnas` `/nulos` `/describe` | ✅ | |
| `/head [N]` `/sample [N]` | ✅ | Fix NaN aplicado |
| `/cohorts` | ✅ | 9 cohortes, ventas detectadas correctamente |
| `/embudo` `/rfm` `/rentabilidad` | 🟡 no verificado hoy | Pendiente |
| `/velocidad` | ⚠️ sin fecha_cierre | Normal — cami_real.csv no la tiene |
| `/metricas` | ⚠️ agrupa por fecha | Normal — cami_real.csv no tiene col_campana |
| `/alertas` | 🟡 parcial | No corrido completo |

### Niveles conversacionales con cami_real.csv
| Nivel | Estado | Notas |
|-------|--------|-------|
| 1 — Exploración básica | ✅ completo | head/sample con arg funcionan |
| 2 — Métricas simples | ✅ completo | |
| 3 — Análisis por atribución | ✅ completo | |
| 4 — Integridad | 🟡 parcial | |
| 5 — Temporal | ✅ completo | |
| 6 — Compuestas | 🟡 parcial | |
| 7 — Conversacional | ❌ pendiente | |

---

## Contexto Camí

- Marketing director en agencia pequeña
- Stack: Formulario → GHL CRM → n8n → Google Sheet
- **Vive en Sheets** — ese es su entorno natural de trabajo
- Acceso al Sheet: **pendiente** (Camí debe compartirlo con service account)
- **CSV real:** `data/raw/cami_real.csv` — 1800 filas, 9 columnas, stages en español
  - Columnas: `Fecha de creacion`, `Nombre`, `correo`, `telefono`, `ad primera atribucion`, `ad segunda atribucion`, `stage`, `ad set primera atribucion`, `ad set segunda atribucion`
  - **No tiene:** col_campana explícita, col_inversion, col_valor, fecha_cierre
- ⚠️ NO subir a GitHub

---

## Archivos NO subir a GitHub

- `data/raw/cami_real.csv` — datos reales de cliente
- `credentials.json` — service account Google
- `.env` — API keys
- `test_cohorts_fix.py` — archivo temporal en raíz (eliminar o mover a /tests)
- `Select-String` — archivo extraño en raíz (revisar qué es, probablemente borrar)

---

## Query Engine v3 — Text-to-Pandas

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
  namespace: {df, pd, builtins limitados} · timeout: 5s
    ↓
CAPA 4 — Validador
  verifica: result no es None/vacío/todo NaN
    ↓
CAPA 5 — Re-prompt (máx 2 intentos)
  si falla: le pasa el error al planner para corregir
    ↓
RESULTADO serializado → LLM principal lo formatea
```

---

## Tokens por request — estado actual

| Componente | Tokens aprox |
|------------|--------------|
| System prompt base | ~431 |
| resumen_ejecutivo_llm() | ~375 |
| schema_llm | ~180 |
| Último resultado pandas | ~200 |
| Pregunta del usuario | ~20 |
| **Total por request** | **~1,206** |

**Planner adicional:** ~300 tokens por pregunta que activa Text-to-Pandas.

---

## Fallback LLM — estado

| Proveedor | Estado |
|-----------|--------|
| Groq `llama-3.3-70b-versatile` | ✅ principal — rate limit 100k tokens/día free |
| Gemini `gemini-2.5-flash` | ✅ fallback operativo · planner usa este |
| Ollama | ❌ no corriendo — excluido del fallback chain |

`.env` fallback chain: `groq,gemini`

---

## Roadmap SaaS

| Fase | Objetivo | Criterio de salida |
|------|----------|--------------------|
| **v1.0** | Camí usando Adly el viernes 22 | Sheet leído + 3 bugs tapados + desplegado Railway |
| **v1.1** | Onboarding + features pedidas por Camí | Lo que pida después de 1-2 semanas usándolo |
| **Fase 2** | Ingesta defensiva | meta_ingestor + ghl_ingestor. Reconciliador. |
| **Fase 3** | Multi-cliente | Postgres + 2do cliente activo. Onboarding conversacional. |
| **Fase 4** | SaaS competitivo | Onboarding self-serve. Billing. Benchmarks. |
| **v2.0** | Dashboards configurables | Cuando haya 3+ clientes pagando que lo pidan |

**Criterio v1.0→v1.1:** Camí usa Adly 7 días consecutivos y reporta valor real.

---

## Cómo levantar el proyecto (local)

```bash
# Terminal 1 — backend
cd C:\Users\moonw\Proyectos\Adly
venv\Scripts\activate
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

## Regla de cierre de sesión
1. Actualizar este MAESTRO
2. Una línea en BITACORA.md
3. Decidir si hay archivos nuevos (preguntar si algo ya cumple esa función)
4. Recordar actualizar `adly_master_v2.html`
