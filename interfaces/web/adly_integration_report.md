# Reporte de Integración y Auditoría: Adly (Frontend ↔ Backend)

A continuación se detalla exhaustivamente todo el trabajo realizado durante estas sesiones para llevar a Adly de ser una herramienta puramente de terminal (CLI) a una **Aplicación Web Completa con un Backend API Robusto, Seguro y con Estado**.

---

## 1. Arquitectura Implementada

Se construyó una API REST en **FastAPI** para servir como puente entre la interfaz web en React y el motor analítico subyacente de Adly (`AdlyEngine` y `MetricsCalculator`).

El enfoque principal fue mantener la API **"Stateful" en memoria** (como MVP) para evitar la dependencia inmediata de una base de datos compleja, permitiendo que el LLM recuerde el historial del chat y el contexto de los datos subidos.

---

## 2. Archivos Nuevos Creados (Directorio `src/api/`)

Se creó todo un nuevo módulo en el core de Adly para manejar las peticiones HTTP de la web:

```text
src/api/
├── main.py             # Entrypoint de FastAPI. Configura middlewares (CORS) y enruta.
├── limiter.py          # Instancia central de SlowAPI (Rate Limiting por IP).
├── state.py            # Singleton de estado (AppState). Maneja DataFrames, Engines y chat.
└── routes/
    ├── analyses.py     # Manejo de subida de CSVs, Google Sheets y cálculo de métricas.
    ├── chat.py         # Recepción de mensajes, comandos (/rfm, /cohorts) y puente al LLM.
    └── config.py       # Exposición de credenciales/modelos permitidos al frontend.
```

### Detalles de Lógica Nueva:
- **`state.py`**: Implementa `AppState` con colecciones `OrderedDict` que actúan como caché LRU (Least Recently Used). Limita estrictamente el sistema a un máximo de **50 sesiones activas** para evitar desbordamientos de RAM (Memory Leaks) cuando múltiples usuarios suben CSVs pesados.
- **`limiter.py`**: Implementa control de tráfico basado en la IP del cliente para proteger la cuota de la API de LLMs (Groq, OpenAI).

---

## 3. Archivos Modificados (Revisión y Refactorización)

### A. Frontend (React)
Ubicación: `interfaces/web/src/`

- **`pages/Home.jsx`**
  - **Problema**: El diseño global del halo de fondo no se renderizaba correctamente.
  - **Corrección**: Se eliminó un fondo negro sólido hardcodeado (`bg-black`) en el wrapper principal, permitiendo que la herencia visual de Tailwind fluyera.
- **`pages/NewAnalysis.jsx`**
  - **Problema**: La vista solo tenía datasets hardcodeados de prueba en un JSON.
  - **Corrección**: Se implementó una lógica de subida dual: arrastrar y soltar archivos reales vía `FormData` para archivos locales (`.csv`), o un input de texto para leer IDs de `Google Sheets`.
- **`api/client.js`**
  - **Corrección**: Se modificó la función `createAnalysis` para manejar peticiones mutables (`multipart/form-data` para archivos locales, y `application/json` para Google Sheets), reemplazando el comportamiento mock anterior.

### B. Backend Core (Python)
Ubicación: `src/processing/`

- **`metrics.py` (CRÍTICO)**
  - **Problema**: El chat del frontend "alucinaba" respondiendo sin coherencia. Esto se debía a que cuando un usuario subía un CSV cuyas columnas no encajaban exactamente en el molde de Adly, el mapeador de IA (`ColumnMapper`) ponía esos campos como `None`. Al iterar, `MetricsCalculator` generaba errores internos de llave (`KeyError: None`), bloqueando la extracción de datos y entregándole al LLM un prompt vacío de contexto.
  - **Corrección**: Se refactorizó la función `_agrupar` y `_limpiar_tipos` para hacerla **inmune a fallos por falta de columnas**. Ahora, si falta la columna de campaña, agrupa por "Global". Si faltan estados de embudo, devuelve 0 pero calcula la inversión. Esto garantiza que el LLM siempre reciba datos reales, aunque estén incompletos.

---

## 4. Auditoría de Seguridad Aplicada

Para garantizar que el backend FastAPI pueda estar expuesto en un entorno local o de red sin colapsar, se aplicaron los siguientes parches de seguridad:

1. **Denegación de Servicio (DoS) por Archivos Masivos:**
   - *Implementación (`analyses.py`):* Limitación dura `MAX_CSV_SIZE_BYTES`. Se bloquea a nivel de Request cualquier archivo mayor a **25 MB** antes de intentar cargarlo en Pandas.
2. **Abuso de Costos de IA (Rate Limiting):**
   - *Implementación (`main.py`, `chat.py`, `analyses.py`):* Se usó `slowapi` limitando el Endpoint de creación de análisis a **20 req/min** y el chat de LLM a **30 req/min** por IP.
3. **Inyección por Google Sheets:**
   - *Implementación (`analyses.py`):* Validación mediante Expresiones Regulares (`Regex`) del `sheetId`. Se rechaza cualquier string que no coincida con el patrón alfa-numérico oficial de Google (30 a 60 caracteres).
4. **Fugas de Memoria (Memory Leaks):**
   - *Implementación (`state.py`):* Migración de diccionarios planos `Dict` a `OrderedDict`. Se incluyó un mecanismo FIFO que hace `popitem(last=False)` al superar los 50 análisis concurrentes.

---

## 5. Resumen del Flujo Actual (Cómo funciona ahora)

1. El usuario entra a la Web y sube un **CSV**.
2. React envía un `multipart/form-data` al endpoint `/api/analyses`.
3. FastAPI recibe el archivo, verifica que pese < 25MB.
4. El archivo se convierte en un DataFrame de `pandas`.
5. Se invoca a `ColumnMapper` que, mediante un pequeño prompt al LLM, deduce qué columna es qué (Inversión, MQL, Ventas).
6. `MetricsCalculator` calcula los KPIs sin fallar si hay columnas ausentes.
7. Se instancia `AdlyEngine` y se le inyecta la memoria.
8. Todo se guarda temporalmente en `state.py`.
9. Cuando el usuario chatea en la interfaz, React ataca a `/api/chat`, la cual recupera el `AdlyEngine` en memoria y genera una respuesta contextualizada (sin alucinaciones).

> [!TIP]
> **Revisión del Desarrollador:** Todo el código implementado es escalable. Si en el futuro necesitas balanceadores de carga con múltiples procesos `uvicorn` (workers), tendrás que migrar `state.py` hacia una capa en **Redis** o una base de datos ligera como **SQLite**, dado que la memoria actual pertenece a un solo proceso.
