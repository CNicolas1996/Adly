# mock_data.py — Adly · Data-Buddy
# Simula la estructura real de GoHighLevel → Google Sheets
# Schema dinámico — se adapta a cualquier estructura de columnas

import pandas as pd
from datetime import datetime, timedelta
import random

# ─────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────

CAMPANAS = ["Campaña_Leads_Marzo", "Campaña_Retargeting", "Campaña_Branding"]
ADSETS   = ["Adset_18-35", "Adset_35-50", "Adset_Intereses"]
ADS      = ["Ad_Video_A", "Ad_Imagen_B", "Ad_Carrusel_C"]
ESTADOS  = ["lead", "mql", "sql", "venta", "perdido"]
PESOS    = [0.45, 0.25, 0.15, 0.10, 0.05]  # probabilidad de cada estado

# ─────────────────────────────────────────
# GENERADOR DE DATOS GHL (fuente de verdad)
# ─────────────────────────────────────────

def generar_datos_ghl(n_leads: int = 100) -> pd.DataFrame:
    """
    Simula los datos que viven en GoHighLevel CRM.
    Cada fila es un lead con su ID único y estado en el embudo.
    """
    random.seed(42)
    fecha_base = datetime(2026, 3, 1)

    registros = []
    for i in range(1, n_leads + 1):
        dias_offset = random.randint(0, 20)
        fecha = fecha_base + timedelta(days=dias_offset)

        registros.append({
            "ghl_id":        f"GHL-{i:04d}",          # ID único del CRM — nunca cambia
            "nombre":        f"Lead_{i:04d}",
            "email":         f"lead{i}@ejemplo.com",
            "telefono":      f"300{i:07d}",
            "campana":       random.choice(CAMPANAS),
            "adset":         random.choice(ADSETS),
            "ad":            random.choice(ADS),
            "estado":        random.choices(ESTADOS, weights=PESOS)[0],
            "costo_lead":    round(random.uniform(8000, 25000), 2),  # COP
            "valor_venta":   round(random.uniform(200000, 800000), 2) if random.random() > 0.85 else 0,
            "fecha_entrada": fecha.strftime("%Y-%m-%d %H:%M:%S"),
            "fecha_update":  (fecha + timedelta(hours=random.randint(1, 72))).strftime("%Y-%m-%d %H:%M:%S"),
        })

    return pd.DataFrame(registros)


# ─────────────────────────────────────────
# GENERADOR DE DATOS SHEET (con errores intencionales)
# ─────────────────────────────────────────

def generar_datos_sheet(df_ghl: pd.DataFrame, pct_faltantes: float = 0.12) -> pd.DataFrame:
    """
    Simula lo que n8n escribió en Google Sheets.
    Introduce errores intencionales para probar el pipeline de validación:
      - Registros faltantes (n8n falló)
      - Registros duplicados (n8n ejecutó dos veces)
      - Campos vacíos (error de mapeo)
      - Estado desactualizado (sincronización tardía)
    """
    random.seed(99)
    df = df_ghl.copy()

    # ERROR 1 — Registros faltantes (simula fallo de n8n)
    n_faltantes = int(len(df) * pct_faltantes)
    indices_faltantes = random.sample(list(df.index), n_faltantes)
    df = df.drop(indices_faltantes).reset_index(drop=True)

    # ERROR 2 — Registros duplicados (n8n ejecutó dos veces)
    n_duplicados = max(1, int(len(df) * 0.05))
    indices_dup = random.sample(list(df.index), n_duplicados)
    duplicados = df.loc[indices_dup].copy()
    df = pd.concat([df, duplicados], ignore_index=True)

    # ERROR 3 — Campos vacíos en columnas clave
    for col in ["campana", "adset", "costo_lead"]:
        indices_vacios = random.sample(list(df.index), max(1, int(len(df) * 0.03)))
        df.loc[indices_vacios, col] = None

    # ERROR 4 — Estado desactualizado en algunos registros
    indices_estado = random.sample(list(df.index), max(1, int(len(df) * 0.04)))
    df.loc[indices_estado, "estado"] = "lead"  # debería ser mql o sql

    # Simular timestamp de llegada al Sheet (siempre después de GHL)
    df["sheet_timestamp"] = pd.to_datetime(df["fecha_entrada"]) + \
                            pd.to_timedelta([random.randint(1, 300) for _ in range(len(df))], unit="s")
    df["sheet_timestamp"] = df["sheet_timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")

    return df


# ─────────────────────────────────────────
# EXPORTAR COMO CSV (para desarrollo sin Sheets API)
# ─────────────────────────────────────────

def exportar_mock(output_dir: str = "data/raw") -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Genera y guarda ambos datasets en data/raw/
    Retorna (df_ghl, df_sheet) para usar directamente en código.
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    df_ghl   = generar_datos_ghl(n_leads=100)
    df_sheet = generar_datos_sheet(df_ghl)

    df_ghl.to_csv(f"{output_dir}/mock_ghl.csv",   index=False)
    df_sheet.to_csv(f"{output_dir}/mock_sheet.csv", index=False)

    print(f"[GHL]   {len(df_ghl)} registros   → {output_dir}/mock_ghl.csv")
    print(f"[Sheet] {len(df_sheet)} registros  → {output_dir}/mock_sheet.csv")
    print(f"\nErrores introducidos intencionalmente:")
    print(f"  Faltantes en Sheet : ~{int(len(df_ghl)*0.12)} registros")
    print(f"  Duplicados         : ~{max(1, int(len(df_ghl)*0.05))} registros")
    print(f"  Campos vacíos      : ~3% en campana, adset, costo_lead")
    print(f"  Estado desactualiz : ~4% de registros")

    return df_ghl, df_sheet


# ─────────────────────────────────────────
# MAIN — correr directamente para generar datos
# ─────────────────────────────────────────

if __name__ == "__main__":
    print(">> Generando datos de prueba...\n")
    df_ghl, df_sheet = exportar_mock()
    print("\n>> Muestra GHL (primeras 3 filas):")
    print(df_ghl.head(3).to_string())
    print("\n>> Muestra Sheet (primeras 3 filas):")
    print(df_sheet.head(3).to_string())
    print("\n>> Mock data listo.")