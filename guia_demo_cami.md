# 🎯 Guía de demo — Llamada con Camí

> Paso a paso para mostrar lo que ya funciona.
> Usa datos de prueba o los datos reales que Camí te pase.

---

## Antes de la llamada — setup

```bash
# 1. Ir al proyecto
cd ~/Proyectos/Adly

# 2. Activar entorno virtual
venv\Scripts\activate

# 3. Verificar que los datos de prueba existen
ls data/raw/
# Debes ver: mock_ghl.csv y mock_sheet.csv

# Si no existen, generarlos:
python src/ingestion/mock_data.py
```

---

## Demo 1 — Mostrar los datos simulados

**Qué le dices a Camí:** "Esto simula exactamente cómo se vería tu GoHighLevel y tu Sheet."

```bash
python src/ingestion/mock_data.py
```

**Qué muestra:**
- 100 leads simulados en GHL (fuente de verdad)
- El mismo Sheet con errores reales: faltantes, duplicados, campos vacíos
- Preview de ambas fuentes en terminal

---

## Demo 2 — Leer datos con el conector

**Qué le dices a Camí:** "Adly se conecta a tu Sheet y detecta automáticamente qué columnas tienes, sin importar cómo las hayas nombrado."

```bash
python -m src.ingestion.sheets mock
```

**Qué muestra:**
- Conexión exitosa al MockConnector
- Número de filas y columnas detectadas
- Schema dinámico — mapa de columnas encontradas
- Preview de los primeros 3 registros

---

## Demo 3 — Reporte de integridad

**Qué le dices a Camí:** "Antes de analizar cualquier cosa, Adly revisa que tus datos estén limpios. Esto es lo que encuentra hoy en tu Sheet."

```bash
python -m src.processing.validation
```

**Qué muestra:**
- GHL: 100 registros (fuente de verdad)
- Sheet: 92 registros (espejo con errores)
- Faltantes, duplicados, campos vacíos, estados desactualizados
- Score de integridad: 67%

**Punto clave para Camí:** "Si analizamos sobre estos datos sin limpiarlos primero, cualquier decisión está basada en información incompleta."

---

## Demo 4 — Sistema de alertas

**Qué le dices a Camí:** "En vez de un reporte técnico, Adly convierte los problemas en mensajes claros y accionables. Esto es lo que te llegaría por WhatsApp."

```bash
python -m src.processing.alerts
```

**Qué muestra:**
- Alertas críticas en rojo — requieren acción inmediata
- Advertencias en amarillo — monitorear
- Lo que Adly le diría a Camí en lenguaje natural

---

## Si Camí quiere usar sus datos reales

### Opción A — Pegar datos en un CSV

1. Exporta tu Sheet como CSV desde Google Drive
2. Guárdalo como `data/raw/cami_sheet.csv`
3. Modificar temporalmente en `validation.py`:

```python
# Cambiar esta línea:
df_sheet = pd.read_csv("data/raw/mock_sheet.csv")

# Por esta:
df_sheet = pd.read_csv("data/raw/cami_sheet.csv")
```

4. Correr la validación:
```bash
python -m src.processing.validation
```

### Opción B — Conectar Google Sheets directo

Ver guía separada: `guia_conectar_sheets.md`

---

## Preguntas que puede hacer Camí

| Pregunta | Respuesta honesta |
|---|---|
| ¿Esto ya funciona con mis datos reales? | El pipeline de validación sí. El chatbot de IA viene en la siguiente fase. |
| ¿Cuándo puedo preguntarle sobre campañas? | Esta semana — es la siguiente tarea. |
| ¿Esto reemplaza n8n? | No, Adly trabaja encima de n8n. n8n sigue siendo el que mueve los datos. |
| ¿Funciona con cualquier Sheet? | Sí — el schema es dinámico, se adapta a la estructura que tengas. |

---

## Puntos clave para comunicar

1. **Lo que ya funciona hoy:** validación de datos, detección de inconsistencias, alertas
2. **Lo que viene esta semana:** conectar el LLM — Adly responde preguntas sobre campañas
3. **Lo que viene después:** agente autónomo que trabaja solo y te avisa por WhatsApp
4. **Lo que necesitamos de Camí:** responder el cuestionario de 20 preguntas + compartir acceso al Sheet

---

*Adly · Demo v0.1 · Marzo 2026*
