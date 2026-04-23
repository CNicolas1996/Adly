# Adly — APIs, Seguridad y Escalabilidad
> Documento de estudio para Nico · Basado en la sesión real de configuración

---

## 1. Qué es una API y por qué Adly las usa

Una **API** (Application Programming Interface) es un contrato entre dos sistemas — defines qué puedes pedir y qué recibes a cambio. Adly usa tres APIs principales:

| API | Para qué | Quién la provee |
|---|---|---|
| Google Sheets API | Leer y escribir datos del Sheet de Camí | Google Cloud |
| Groq API | Procesar lenguaje natural (el "cerebro" de Adly) | Groq |
| GoHighLevel API | Leer leads del CRM (Fase 2) | GHL |

**Regla clave:** Ninguna API es gratuita para siempre. Siempre revisa los límites antes de escalar.

---

## 2. Cuenta de servicio — qué es y por qué existe

Una **cuenta de servicio** es una identidad que representa a una aplicación, no a una persona. En vez de que Adly use las credenciales de Nico o de Camí, usa su propia identidad independiente.

**Por qué importa:**
- Si Camí cambia su contraseña, Adly sigue funcionando
- Si Adly se compromete, no expones la cuenta personal de nadie
- Puedes dar permisos específicos — solo lectura, solo un Sheet, etc.

**En el proyecto:**
- Cuenta: `adly-service@gen-lang-client-0574573686.iam.gserviceaccount.com`
- Proyecto GCP: `gen-lang-client-0574573686`
- Archivo clave: `credentials.json` — **NUNCA subir a GitHub**

---

## 3. El archivo credentials.json — qué contiene y cómo protegerlo

Es un JSON con la clave privada de la cuenta de servicio. Quien lo tenga puede actuar como Adly.

**Reglas de oro:**
1. Siempre en `.gitignore` — nunca en el repo
2. Un archivo por entorno — desarrollo vs producción
3. Si se filtra accidentalmente, ve a Google Cloud → Credenciales → Eliminar clave → Crear nueva
4. Google detecta automáticamente si la clave aparece en un repo público y la deshabilita

**Estructura del .gitignore mínimo para Adly:**
```
credentials.json
.env
*.csv
__pycache__/
venv/
```

---

## 4. Variables de entorno (.env) — separar config del código

El `.env` guarda todo lo que cambia entre entornos o que es secreto:

```bash
# LLM
ADLY_LLM_PROVIDER=groq
ADLY_LLM_API_KEY=gsk_xxxxxxxxxxxx
ADLY_LLM_MODEL=llama-3.3-70b-versatile

# Datos
ADLY_FUENTE=sheets
GOOGLE_SHEET_ID=wb1d5V75_dAI2G-s5sR9legU-85kH59J8FTwwrqP2J8

# Debug
ADLY_DEBUG=false
```

**Por qué no hardcodear en el código:**
- Si compartes el código, no compartes las claves
- Cada cliente de Adly tiene su propio `.env` con su Sheet ID y su API key
- Cambiar de proveedor LLM = cambiar una línea en `.env`, no reescribir código

---

## 5. Flujo completo de autenticación — cómo Adly accede al Sheet

```
Adly (Python)
    ↓ lee credentials.json
gspread (librería)
    ↓ hace OAuth2 con Google
Google Cloud IAM
    ↓ verifica que adly-service tiene acceso al Sheet
Google Sheets API
    ↓ retorna datos como JSON
pandas DataFrame
    ↓ procesa métricas
Engine LLM
```

**Lo que hiciste hoy paso a paso:**
1. Verificaste que Google Sheets API estaba habilitada en el proyecto
2. Encontraste la cuenta de servicio `adly-service` ya existente
3. Localizaste el `credentials.json` en tu máquina
4. Creaste un Sheet nuevo y subiste el mock de 500 leads
5. Compartiste el Sheet con la cuenta de servicio (como Editor)
6. Configuraste el Sheet ID en el onboarding de Adly
7. Adly leyó los datos con score 100% ✓

---

## 6. Escalabilidad — qué cambia cuando Adly tiene 10 clientes

### Hoy (1 cliente — Camí)
- 1 `credentials.json`
- 1 Sheet ID en `.env`
- 1 instancia de Adly corriendo local

### Con 10 clientes
Cada cliente necesita:
- Su propio Sheet compartido con `adly-service`
- Su propio `.env` con su `GOOGLE_SHEET_ID`
- Su propia API key de Groq (o una compartida con límites)

Lo que **no** cambia:
- El código de Adly es el mismo para todos
- `credentials.json` puede ser el mismo (una sola cuenta de servicio)
- El engine, validación y métricas son agnósticos

### Con 100 clientes
Ahí sí necesitas infraestructura:
- **Base de datos** para guardar configuración por cliente
- **Multi-tenancy** — Adly sabe qué Sheet leer según qué cliente está logueado
- **Rate limiting** — no puedes hacer 100 llamadas a Groq al mismo tiempo
- **Deployment en servidor** — Railway, Render, o AWS

---

## 7. Seguridad — qué debes saber antes de vender Adly

### Nivel MVP (hoy)
- `.env` y `credentials.json` fuera del repo ✓
- Una cuenta de servicio con permisos mínimos ✓
- API key de Groq solo en `.env` ✓

### Nivel producción (cuando tengas clientes pagando)
- **Rotación de claves** — cambiar API keys cada 90 días
- **Permisos mínimos** — la cuenta de servicio solo debe tener acceso de lectura al Sheet, no de editor
- **Logs de acceso** — saber quién leyó qué y cuándo
- **Encriptación en tránsito** — HTTPS siempre (Google y Groq ya lo manejan)

### Lo que los datos de Camí NO deberían hacer
- Salir del Sheet hacia un modelo LLM sin consentimiento explícito
- Guardarse en los servidores de Groq (por política no lo hacen, pero verificar)
- Exponerse en logs de debug (`ADLY_DEBUG=false` en producción)

---

## 8. Conceptos que debes dominar antes de vender

| Concepto | Para qué lo necesitas | Dónde aprenderlo |
|---|---|---|
| OAuth2 | Entender cómo funciona la auth de Google | Google Identity docs |
| REST APIs | Todas las APIs que usa Adly son REST | cualquier curso de APIs |
| Variables de entorno | Ya lo manejas | ✓ |
| `.gitignore` | Proteger credenciales en repos | Git docs |
| Rate limiting | Evitar costos inesperados de APIs | Docs de cada proveedor |
| Multi-tenancy | Escalar a múltiples clientes | Cuando llegues ahí |

---

## 9. Checklist antes de darle Adly a un cliente nuevo

- [ ] Crear Sheet y subir datos del cliente
- [ ] Compartir Sheet con `adly-service@gen-lang-client-0574573686.iam.gserviceaccount.com`
- [ ] Copiar Sheet ID de la URL
- [ ] Crear `.env` del cliente con su Sheet ID
- [ ] Poner `credentials.json` en la raíz del proyecto
- [ ] Correr Adly y verificar score de integridad
- [ ] `ADLY_DEBUG=false` antes de entregar
- [ ] Documentar qué columnas tiene su Sheet para `CONFIG_DEFAULT`

---

*Generado en sesión Adly · 2026-04-16*
