# TEST COMPLETO ADLY — cami_real.csv
> Sesión de prueba post-SemanticInferencer
> Ejecutar con backend levantado + cami_real.csv cargado
> Documentar: respuesta obtenida · confianza · tiempo · si fue correcta

---

## Cómo levantar

```bash
# Terminal 1 — backend
cd C:\Users\moonw\Proyectos\Adly
.venv\Scripts\activate
uvicorn src.api.main:app --reload --port 8000

# Terminal 2 — frontend
cd C:\Users\moonw\Proyectos\Adly\interfaces\web
npm run dev
```

**Verificar antes:**
- `.env` tiene `GROQ_API_KEY` y `GEMINI_API_KEY` sin comillas
- `interfaces/web/.env.local` tiene `VITE_MOCK=false`
- Dataset cargado: `cami_real.csv`

---

## NIVEL 1 — Exploración básica
> El engine debe responder sin calcular nada complejo. Si falla aquí, hay problema base.

1. `/columnas`
2. `/nulos`
3. `/describe`
4. `/head 5`
5. `/estado`
6. "¿cuántos leads tengo en total?"
7. "¿qué stages existen en mis datos?"
8. "¿cuántos leads hay por stage?"

---

## NIVEL 2 — Métricas simples
> Requiere que el SemanticInferencer haya mapeado col_estado y col_campana correctamente.

9. `/metricas`
10. `/embudo`
11. "¿cuál es mi tasa de conversión global?"
12. "¿cuántos leads llegaron a Appointment Set?"
13. "¿cuántos Warm Leads tengo?"
14. "¿cuántos leads están como Closed Lost?"
15. "compara la cantidad de leads por stage"
16. "¿qué porcentaje de leads son Duplicate?"

---

## NIVEL 3 — Análisis por atribución
> El CSV de Camí tiene atribución doble. Esto prueba si el engine entiende la estructura.

17. "¿qué anuncio me trajo más leads?"
18. "¿cuál es el anuncio con mejor tasa de conversión a Appointment Set?"
19. "¿qué ad set tiene más leads?"
20. "compara primera atribución vs segunda atribución — ¿hay diferencia?"
21. "¿cuáles son los 3 anuncios con más leads en primera atribución?"
22. "¿qué campaña tiene la mejor tasa de cierre?"
23. "¿hay anuncios que aparecen solo en segunda atribución y nunca en primera?"

---

## NIVEL 4 — Detección de problemas e integridad
> Prueba el lado de integridad de datos — el diferenciador real de Adly.

24. `/alertas`
25. `/limpiar_duplicados`
26. "¿cuántos leads duplicados reales tengo?"
27. "¿hay leads sin stage asignado?"
28. "¿hay correos con formato inválido?"
29. "¿cuántos teléfonos no tienen código de país?"
30. "¿qué tan confiables son mis datos para tomar decisiones?"
31. "¿hay leads que aparecen más de una vez con el mismo correo?"

---

## NIVEL 5 — Análisis temporal
> Requiere que col_date esté mapeada — Fecha de creacion.

32. "¿en qué mes llegaron más leads?"
33. "¿cómo fue la tendencia de leads en los últimos 3 meses?"
34. "¿qué stage domina en los leads más recientes?"
35. "¿los leads de enero convierten mejor que los de marzo?"
36. `/cohorts`
37. `/velocidad`

---

## NIVEL 6 — Preguntas compuestas y semánticas
> Aquí el LLM tiene que razonar, cruzar datos y dar recomendaciones. El nivel más difícil.

38. "¿qué anuncio me cuesta más conseguir un Appointment Set y vale la pena?"
39. "si tuviera que pausar algo hoy, ¿qué pausaría y por qué?"
40. "¿cuál es el camino más común de un lead hasta convertirse en cliente?"
41. "¿hay algún anuncio que trae muchos leads pero pocos cierres — trampa de volumen?"
42. "compara el rendimiento de los anuncios de primera atribución vs segunda — ¿cuál aporta más valor real?"
43. "¿qué está fallando en mi funnel — dónde se caen más leads?"
44. "si duplico el presupuesto del mejor anuncio, ¿cuántos clientes más esperarías?"
45. "¿hay algún patrón entre los leads que llegan a Appointment Set y los que no se presentan?"
46. "¿qué me dice la tasa de No Show sobre la calidad de los leads que estoy atrayendo?"
47. "dame un diagnóstico completo de la salud de mis campañas — qué escalar, qué pausar, qué revisar"

---

## NIVEL 7 — Seguimiento y contexto conversacional
> Prueba memoria de sesión — cada pregunta depende de la anterior.

48. "¿cuál anuncio tiene mejor rendimiento?" → esperar respuesta
49. "¿y por qué crees que ese es mejor?" → sobre el anterior
50. "¿qué pasa si le bajo el presupuesto?" → sobre el mismo
51. "compáralo con el peor" → sobre el mismo contexto
52. "¿cuál de los dos escalarías primero?" → decisión final

---

## Qué documentar por pregunta

```
Pregunta: [número y texto]
Respuesta: [resumen de lo que dijo Adly]
Confianza reportada: [0.0 - 1.0]
Correcta: [sí / parcial / no]
Notas: [algo raro, lento, inventado, o brillante]
```

---

## Bugs a vigilar especialmente

- ¿Confunde primera y segunda atribución?
- ¿Dice "no tengo datos de inversión" correctamente cuando no existe esa columna?
- ¿El contexto de conversación se contamina entre preguntas del Nivel 7?
- ¿`/alertas` detecta duplicados reales (Hilda Pomares)?
- ¿Maneja bien stages en inglés sin confundirse?
- ¿Admite cuando no puede calcular algo en vez de inventar?
