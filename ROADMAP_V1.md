# ROADMAP V1.0 — ADLY DESPLIEGUE
> Plan ejecutable. Una semana. Sin frentes nuevos.
> Creado: 2026-05-14
> Deadline: Viernes 22 de mayo de 2026

---

## 🎯 Objetivo único

**Camí usa Adly desde su casa el viernes 22 de mayo.**

Todo lo demás se mide contra eso. Si una tarea no acerca a ese objetivo, no entra esta semana.

---

## ✅ Qué incluye v1.0

- CLI v5 funcional (✅ ya está)
- Web UI conectada al engine real (✅ ya está)
- 3 bugs críticos tapados (🟡 2/3 cerrados)
- Gráficos Plotly inline en respuestas del chat para `/embudo`, `/cohorts`, tendencias
- Conector gspread con service account — Camí comparte el Sheet con `adly-service@gen-lang-client-0574573686.iam.gserviceaccount.com`
- Fallback a CSV manual si Camí no comparte el Sheet a tiempo
- Despliegue en Railway (backend FastAPI + frontend Vite)
- Variables de entorno como secrets, no en repo

---

## ❌ Qué NO incluye v1.0

| Feature | Cuándo |
|---------|--------|
| Dashboards configurables | v2.0 — cuando haya 3+ clientes pagando |
| OAuth2 completo de Google | v1.1 si Camí lo pide |
| Conexión directa a GHL/Meta | Fase 2 |
| Refactor `ingestion_normalizer.py` | Pos-v1.0 (deuda técnica, no bloquea) |
| Cachear SemanticInferencer en state.py | Pos-v1.0 (optimización) |
| `docs/errores_y_soluciones.md` | Empezar cuando Adly esté en prod |
| Tests Nivel 6 y 7 | Pos-v1.0 |
| Onboarding conversacional sin dataset | Fase 3 |
| `/metricas` por ad/campaña | No hay col_campana en cami_real.csv — no es bug |
| `/velocidad` | No hay fecha_cierre en cami_real.csv — no es bug |

---

## 📅 Cronograma día por día

### ✅ Jueves 14 de mayo — COMPLETADO
**Tareas completadas:**
- ✅ Bug 1 — `metrics.py` NORM dinámico → `/cohorts` funcional con `cami_real.csv`
- ✅ Bug 2 — NaN serialization en `bridge_head/bridge_sample` → `/head` y `/sample` funcionando
- ✅ SemanticInferencer sinónimos ES ampliados
- ✅ ValueMapper variantes underscore (`cerrado_ganado`, etc.)
- ✅ `_estados_venta()` en `commands.py` ampliado

**Resultado:**
```
/cohorts cami_real.csv: 9 cohortes Nov-2025 a Jul-2026, tasas 4.7%-11.2% ✅
/head 20, /sample 20: funcionando ✅
```

---

### Viernes 15 de mayo
**Tarea:** Bug 3 — umbral n≥5 para tasas.

**Qué hacer:**
- Abrir `metrics.py` → `_calcular_metricas()`
- Antes de reportar tasa de conversión, validar `n >= 5`
- Si `n < 5`: retornar "muestra insuficiente — n=X, mínimo 5"
- También en `resumen_ejecutivo_llm()` — mismo control

**Criterio de éxito:** `/cohorts` con cohorte de 2 leads dice "muestra insuficiente". Cohortes grandes reportan normalmente.

**Tiempo estimado:** 1 hora.

---

### Sábado 16 de mayo — sesión larga
**Tarea:** Gráficos Plotly inline en respuestas del chat.

**Qué hacer:**
- Crear `src/processing/visualizer.py`
- Función `funnel_chart(data) -> plotly.Figure` para `/embudo`
- Función `cohort_heatmap(data) -> plotly.Figure` para `/cohorts`
- Función `time_series(data) -> plotly.Figure` para tendencias temporales
- Backend serializa como JSON (`fig.to_json()`), frontend renderiza con `react-plotly.js`
- Si la respuesta NO incluye gráfico → comportamiento actual (solo texto)

**Criterio de éxito:** Camí escribe "embudo de marzo" → Adly responde con texto + funnel chart interactivo.

**Tiempo estimado:** 4-6 horas (sesión larga).

---

### Domingo 17 de mayo
**Tarea:** Conector gspread con service account.

**Qué hacer:**
- Verificar que `credentials.json` de la service account está disponible
- En `src/ingestion/sheets.py`, agregar método `leer_por_link(sheet_url: str)`
- En Web UI, agregar input "Pega el link de tu Google Sheet"
- Pasar el DataFrame por el mismo pipeline (SemanticInferencer → normalizar → engine)
- Mensaje de error claro si el Sheet no está compartido con el service account

**Criterio de éxito:** Pegar link de un Sheet de prueba → Adly lo lee y responde a comandos.

**Tiempo estimado:** 3-4 horas.

---

### Lunes 18 de mayo
**Tarea:** Despliegue Railway.

**Qué hacer:**
- Crear proyecto desde el repo de GitHub
- Backend: `uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`
- Variables de entorno: `GROQ_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_SERVICE_ACCOUNT_JSON` como secrets
- Frontend: `npm run build`, `VITE_API_URL` apuntando al backend Railway
- Probar URL en producción

**Criterio de éxito:** URL pública funcional, Camí puede abrirla desde su computador.

**Tiempo estimado:** 3-5 horas.

---

### Martes 19 de mayo
**Tarea:** Testing end-to-end con `cami_real.csv` en producción.

**Qué hacer:**
- Subir `cami_real.csv` a la URL de producción
- Correr: `/columnas`, `/head 10`, `/sample 5`, `/embudo`, `/cohorts`, `/rfm`, `/alertas`
- Probar preguntas en lenguaje natural
- Anotar todo lo que falle en BITÁCORA

**Criterio de éxito:** 0 errores 500 en producción con datos reales.

**Tiempo estimado:** 2-3 horas.

---

### Miércoles 20 de mayo
**Tarea:** Pulir UI + edge cases identificados el martes.

**Criterio de éxito:** Adly se ve y funciona pulido. Sin errores visibles para el usuario.

**Tiempo estimado:** 3-4 horas.

---

### Jueves 21 de mayo — BUFFER
Reservado para imprevistos. Si todo va bien:
- Documentar para Camí: 1 página "cómo usar Adly" con 5 ejemplos
- Grabar Loom de 3 min
- Recordatorio gentil a Camí para compartir Sheet

---

### Viernes 22 de mayo — LANZAMIENTO
- Mensaje a Camí: link + Loom + "dale, juega con esto y dime"
- NO sentarse a observar — dejarlo respirar

**Criterio de éxito:** Camí entró a Adly al menos una vez ese día.

---

## ⚠️ Reglas no negociables esta semana

1. **No abrir frentes nuevos.** Ideas → `BITACORA.md`, no a esta semana.
2. **No refactorizar lo que ya funciona.** `engine.py` no se toca. `SemanticInferencer` no se toca.
3. **No esperar a Camí.** Si no comparte el Sheet → fallback a CSV manual.
4. **No optimizar prematuramente.** Cachear SemanticInferencer, mejorar prompts, reducir tokens — pos-v1.0.
5. **Documentar mientras se construye.**

---

## 🚨 Plan de contingencia

| Si pasa esto... | ...entonces |
|-----------------|-------------|
| Bug 3 toma más de lo esperado | Mover a lunes. Gráficos el sábado igual. |
| Gráficos toman más del sábado | Lanzar v1.0 con solo `/embudo` graficado. Los otros van a v1.1. |
| Railway tiene problemas raros | Backup: Render. Setup similar, 1-2 horas adicionales. |
| Camí no comparte el Sheet | v1.0 sale solo con CSV manual. La conexión Sheet va a v1.1. |
| Aparece un bug crítico nuevo el martes | Triage: ¿bloquea uso de Camí? Si no → BITACORA. Si sí → corregir. |
| Nico se enferma / surge crisis personal | Mover deadline a viernes 29. Avisar a Camí. |

---

## 📊 Métricas de éxito v1.0

**Mínimas (para considerar lanzamiento exitoso):**
- [x] Bug 1 cerrado ✅
- [x] Bug 2 cerrado ✅
- [ ] Bug 3 cerrado
- [ ] Desplegado en Railway con URL pública
- [ ] Al menos un gráfico funcionando inline
- [ ] Camí abrió la URL al menos una vez

**Ideales:**
- [ ] Camí usó Adly 3+ veces la primera semana
- [ ] Camí preguntó algo en lenguaje natural
- [ ] 0 errores 500 reportados
- [ ] Sheet conectado por service account

---

## Próxima decisión grande (después de v1.0)

**Pregunta abierta:** ¿Qué vende Adly frente a Kimi o Claude with Work?

Se contesta observando a Camí usar el producto:
- Qué preguntas hace que no podría hacer en Kimi
- Qué confianza le da el footer de integridad
- Cuántas veces vuelve sin que Nico le diga nada

Si después de 2 semanas la respuesta es "nada que Kimi no haga" → replantear desde la propuesta de valor.
