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

# Rango de historia por campaña — cuántos días hacia atrás tiene datos
HISTORIA_CAMPANAS = {
    "Campaña_Retargeting":  120,  # 4 meses
    "Campaña_Branding":      60,  # 2 meses
    "Campaña_Leads_Marzo":   42,  # 6 semanas
}

# ─────────────────────────────────────────
# GENERADOR DE DATOS GHL (fuente de verdad)
# ─────────────────────────────────────────

def generar_datos_ghl(n_leads: int = 500) -> pd.DataFrame:
    """
    Simula los datos que viven en GoHighLevel CRM.
    Cada fila es un lead con su ID único y estado en el embudo.
    v2: 500+ leads · fecha_creacion con distribución realista por campaña · fecha_cierre para ventas.
    """
    random.seed(42)
    fecha_tope = datetime(2026, 4, 1)  # fecha más reciente del dataset

    registros = []
    for i in range(1, n_leads + 1):
        campana = random.choice(CAMPANAS)
        historia_dias = HISTORIA_CAMPANAS.get(campana, 60)
        dias_offset = random.randint(0, historia_dias)
        fecha_creacion = fecha_tope - timedelta(days=dias_offset)

        estado = random.choices(ESTADOS, weights=PESOS)[0]

        # fecha_cierre solo si el lead llegó a venta — entre 3 y 30 días después
        if estado == "venta":
            fecha_cierre = fecha_creacion + timedelta(days=random.randint(3, 30))
            fecha_cierre_str = fecha_cierre.strftime("%Y-%m-%d %H:%M:%S")
        else:
            fecha_cierre_str = ""

        registros.append({
            "ghl_id":          f"GHL-{i:04d}",
            "nombre":          f"Lead_{i:04d}",
            "email":           f"lead{i}@ejemplo.com",
            "telefono":        f"300{i:07d}",
            "campana":         campana,
            "adset":           random.choice(ADSETS),
            "ad":              random.choice(ADS),
            "estado":          estado,
            "costo_lead":      round(random.uniform(8000, 25000), 2),  # COP
            "valor_venta":     round(random.uniform(200000, 800000), 2) if estado == "venta" else 0,
            "fecha_creacion":  fecha_creacion.strftime("%Y-%m-%d %H:%M:%S"),
            "fecha_cierre":    fecha_cierre_str,
            "fecha_update":    (fecha_creacion + timedelta(hours=random.randint(1, 72))).strftime("%Y-%m-%d %H:%M:%S"),
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
    df["sheet_timestamp"] = pd.to_datetime(df["fecha_creacion"]) + \
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

    df_ghl   = generar_datos_ghl(n_leads=500)
    df_sheet = generar_datos_sheet(df_ghl)

    df_ghl.to_csv(f"{output_dir}/mock_ghl.csv",   index=False)
    df_sheet.to_csv(f"{output_dir}/mock_sheet.csv", index=False)

    print(f"[GHL]   {len(df_ghl)} registros   -> {output_dir}/mock_ghl.csv")
    print(f"[Sheet] {len(df_sheet)} registros  -> {output_dir}/mock_sheet.csv")
    print(f"\nErrores introducidos intencionalmente:")
    print(f"  Faltantes en Sheet : ~{int(len(df_ghl)*0.12)} registros")
    print(f"  Duplicados         : ~{max(1, int(len(df_ghl)*0.05))} registros")
    print(f"  Campos vacíos      : ~3% en campana, adset, costo_lead")
    print(f"  Estado desactualiz : ~4% de registros")

    return df_ghl, df_sheet


# ─────────────────────────────────────────
# MOCK AMBIGUO — columnas en inglés, estados distintos
# Para probar ColumnMapper + Sheets real
# ─────────────────────────────────────────

def generar_datos_ambiguos(n_leads: int = 300) -> pd.DataFrame:
    """
    Dataset con estructura completamente distinta al mock estándar.
    Diseñado para que Adly tenga que inferir el contexto por sí solo.

    Diferencias intencionales:
    - Nombres de columnas en inglés y abreviados
    - Estados del embudo en inglés (qualified, opportunity, closed_won, cold, new)
    - Columna de fecha llamada 'record_ts' (no 'fecha' ni 'date')
    - Inversión llamada 'spend' con valores en USD
    - Ingresos llamados 'revenue'
    - ID llamado 'contact_id'
    - Campaña llamada 'utm_campaign'
    """
    random.seed(77)
    fecha_base = datetime(2026, 1, 15)

    CAMPAIGNS = [
        "paid_search_q1",
        "social_retargeting_feb",
        "brand_awareness_mar",
        "influencer_collab_q1",
    ]
    ADSETS_ENG = ["lookalike_25-40", "interest_fitness", "retarget_visitors"]
    ADS_ENG    = ["video_15s", "carousel_3img", "static_banner"]
    # Estados en inglés — Adly debe inferir cuál es MQL, SQL, Venta
    STAGES     = ["new", "qualified", "opportunity", "closed_won", "lost"]
    WEIGHTS    = [0.40, 0.25, 0.18, 0.10, 0.07]

    registros = []
    for i in range(1, n_leads + 1):
        dias = random.randint(0, 85)   # ~3 meses de datos
        ts   = fecha_base + timedelta(days=dias)
        stage = random.choices(STAGES, weights=WEIGHTS)[0]

        registros.append({
            "contact_id":  f"CRM-{i:05d}",
            "full_name":   f"Contact_{i:05d}",
            "email":       f"contact{i}@domain.com",
            "utm_campaign": random.choice(CAMPAIGNS),
            "utm_adset":   random.choice(ADSETS_ENG),
            "utm_ad":      random.choice(ADS_ENG),
            "funnel_stage": stage,
            "spend":       round(random.uniform(5, 80), 2),        # USD por lead
            "revenue":     round(random.uniform(500, 5000), 2) if stage == "closed_won" else 0.0,
            "record_ts":   ts.strftime("%Y-%m-%dT%H:%M:%SZ"),      # ISO 8601 — sin "fecha"
            "country":     random.choice(["CO", "MX", "AR", "US"]),
            "source":      random.choice(["facebook", "google", "tiktok"]),
        })

    return pd.DataFrame(registros)


def exportar_mock_ambiguo(output_dir: str = "data/raw") -> pd.DataFrame:
    """
    Genera y guarda el dataset ambiguo.
    Este CSV está pensado para subirse a Google Sheets y probar ColumnMapper.
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    df = generar_datos_ambiguos(n_leads=300)
    path = f"{output_dir}/mock_ambiguo.csv"
    df.to_csv(path, index=False)

    print(f"[Ambiguo] {len(df)} registros -> {path}")
    print(f"\nColumnas generadas (intencionalmente distintas al schema de Adly):")
    for col in df.columns:
        muestra = df[col].dropna().iloc[0] if not df[col].empty else "-"
        print(f"  {col:20} -> ej: {muestra}")
    print(f"\nEstados del embudo: {df['funnel_stage'].value_counts().to_dict()}")
    print(f"\nSube data/raw/mock_ambiguo.csv a tu Google Sheet para probar ColumnMapper.")

    return df


# ─────────────────────────────────────────
# MAIN — correr directamente para generar datos
# ─────────────────────────────────────────

if __name__ == "__main__":
    import sys
    modo = sys.argv[1] if len(sys.argv) > 1 else "standard"

    if modo == "ambiguo":
        print(">> Generando mock ambiguo (para Sheets + ColumnMapper)...\n")
        exportar_mock_ambiguo()
    else:
        print(">> Generando datos de prueba...\n")
        df_ghl, df_sheet = exportar_mock()
        print("\n>> Muestra GHL (primeras 3 filas):")
        print(df_ghl.head(3).to_string())
        print("\n>> Muestra Sheet (primeras 3 filas):")
        print(df_sheet.head(3).to_string())
        print("\n>> Mock data listo.")
        print("\n>> Para generar mock ambiguo: python src/ingestion/mock_data.py ambiguo")