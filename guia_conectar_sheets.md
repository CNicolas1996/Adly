# 🔗 Guía — Conectar Google Sheets a Adly

> Todo lo que necesitas para conectar el Sheet real de Camí.
> Tiempo estimado: 10 minutos.

---

## Lo que ya tienes listo

- ✅ Proyecto en Google Cloud Console (`adly-dev`)
- ✅ Google Sheets API habilitada
- ✅ Cuenta de servicio creada (`adly-service`)
- ✅ `credentials.json` en la raíz del proyecto
- ✅ `.env` configurado con la ruta a credentials

---

## Paso 1 — Compartir el Sheet con Adly

El Sheet debe estar compartido con el email de la cuenta de servicio.

1. Abre el Google Sheet de Camí
2. Clic en **Compartir** (esquina superior derecha)
3. Agrega este email como **Lector**:

```
adly-service@gen-lang-client-0574573686.iam.gserviceaccount.com
```

4. Desactiva "Notificar a las personas"
5. Clic en **Compartir**

> ⚠️ Si no compartes el Sheet con este email, Adly no puede leerlo.
> No necesita permisos de edición — solo lectura.

---

## Paso 2 — Obtener el Sheet ID

El Sheet ID está en la URL del Google Sheet:

```
https://docs.google.com/spreadsheets/d/  ESTE_ES_EL_ID  /edit
```

Ejemplo:
```
https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms/edit
                                        ↑
                               Copia solo esta parte
```

---

## Paso 3 — Configurar el .env

Abre `~/Proyectos/Adly/.env` y agrega el Sheet ID:

```bash
GOOGLE_SHEETS_CREDENTIALS=./credentials.json
GOOGLE_SHEET_ID=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms
ENV=development
```

---

## Paso 4 — Probar la conexión

```bash
cd ~/Proyectos/Adly
venv\Scripts\activate
python -m src.ingestion.sheets sheets
```

**Si funciona verás:**
```
[SheetsConnector] Conexión establecida
[SheetsConnector] 85 filas · 12 columnas leídas
[SheetsConnector] Schema detectado:
  id         → ✓  ghl_id
  campana    → ✓  campana
  adset      → ✓  adset
  ...
```

---

## Errores comunes

| Error | Causa | Solución |
|---|---|---|
| `FileNotFoundError: credentials.json` | El archivo no está en la raíz | Mover `credentials.json` a `~/Proyectos/Adly/` |
| `gspread.exceptions.NoValidUrlKeyFound` | Sheet ID incorrecto | Copiar solo el ID de la URL, no la URL completa |
| `gspread.exceptions.APIError: PERMISSION_DENIED` | Sheet no compartido | Compartir con el email de la cuenta de servicio |
| `gspread.exceptions.SpreadsheetNotFound` | Sheet ID no existe | Verificar que el Sheet no está en papelera |

---

## Notas importantes

- La cuenta de servicio solo tiene permisos de **lectura** — no puede modificar el Sheet
- Si el Sheet tiene múltiples hojas, por defecto lee la primera (índice 0)
- Para leer otra hoja, modificar en `sheets.py`: `SheetsConnector(sheet_id, hoja=1)`
- El Sheet ID no cambia aunque cambies el nombre del archivo

---

*Adly · Guía de conexión v1.0 · Marzo 2026*
