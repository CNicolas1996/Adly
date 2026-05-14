"""
ingestion_normalizer.py
-----------------------
Corre ANTES de que cualquier df llegue al engine o al planner.
Adly asume siempre que los datos están sucios. Este módulo lo prueba.

Qué hace:
    1. Strip de nombres de columna (espacios trailing/leading)
    2. NONE/none/null como string → NaN real
    3. Detección de emails sospechosos (flag, no eliminación)
    4. Normalización de teléfonos (detecta faltantes de prefijo)
    5. Clasificación de duplicados (real vs journey del lead)
    6. Normalización de stages (inglés/español → vocab unificado)
    7. Llama a attribution_parser para explotar celdas con pipe

Filosofía:
    - Nunca elimina datos. Siempre flaggea.
    - El usuario decide qué hacer — Adly solo informa.
    - Funciona con cualquier schema, no solo el de Camí.

Uso:
    from src.processing.ingestion_normalizer import normalizar
    df_limpio, reporte = normalizar(df)
"""

import pandas as pd
import numpy as np
import re
from typing import Tuple

# Import interno — si no está disponible, attribution_parser se omite sin romper
try:
    from src.processing.attribution_parser import parsear_todas_atribuciones, reporte_atribucion
    _ATTRIBUTION_DISPONIBLE = True
except ImportError:
    try:
        from attribution_parser import parsear_todas_atribuciones, reporte_atribucion
        _ATTRIBUTION_DISPONIBLE = True
    except ImportError:
        _ATTRIBUTION_DISPONIBLE = False


# ---------------------------------------------------------------------------
# Vocabulario de stages — normalización inglés/español → canónico
# ---------------------------------------------------------------------------

STAGE_MAP = {
    # Inglés → canónico español
    "lead":             "Lead",
    "warm lead":        "Lead Caliente",
    "hot lead":         "Lead Caliente",
    "cold lead":        "Lead Frío",
    "appointment set":  "Cita Agendada",
    "contacted":        "Contactado",
    "no show":          "No Se Presentó",
    "no contactado":    "No Contactado",
    "follow up":        "Seguimiento",
    "closed won":       "Cerrado Ganado",
    "closed lost":      "Cerrado Perdido",
    "duplicate":        "Duplicado",
    "spam":             "Spam",
    # Ya en español pero con variaciones
    "cita agendada":    "Cita Agendada",
    "contactado":       "Contactado",
    "seguimiento":      "Seguimiento",
    "cerrado ganado":   "Cerrado Ganado",
    "cerrado perdido":  "Cerrado Perdido",
    "duplicado":        "Duplicado",
}

# Valores que se deben tratar como nulos reales en cualquier columna
_NULOS_STRING = {"none", "null", "n/a", "na", "-", "nan", ""}


# ---------------------------------------------------------------------------
# 1. Strip de nombres de columna
# ---------------------------------------------------------------------------

def _limpiar_nombres_columnas(df: pd.DataFrame) -> pd.DataFrame:
    """Elimina espacios leading/trailing de nombres de columnas."""
    df.columns = [c.strip() for c in df.columns]
    return df


# ---------------------------------------------------------------------------
# 2. NONE como string → NaN real
# ---------------------------------------------------------------------------

def _normalizar_nulos_string(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """
    Reemplaza valores tipo 'NONE', 'none', 'null', 'N/A' por NaN real.
    Retorna el df modificado y el conteo de reemplazos.
    """
    total_reemplazos = 0
    for col in df.select_dtypes(include="object").columns:
        mask = df[col].str.strip().str.lower().isin(_NULOS_STRING)
        total_reemplazos += mask.sum()
        df.loc[mask, col] = np.nan
    return df, total_reemplazos


# ---------------------------------------------------------------------------
# 3. Emails sospechosos
# ---------------------------------------------------------------------------

_EMAIL_VALIDO = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')


def _detectar_emails(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """
    Detecta emails con caracteres inválidos o formato roto.
    Agrega columna 'email_sospechoso' (bool). No elimina nada.
    """
    col = _encontrar_col(df, "correo")
    if col is None:
        return df, 0

    # Trailing/leading spaces primero
    df[col] = df[col].str.strip()

    es_sospechoso = ~df[col].apply(
        lambda x: bool(_EMAIL_VALIDO.match(str(x))) if pd.notna(x) else False
    )
    df["email_sospechoso"] = es_sospechoso
    total = es_sospechoso.sum()
    return df, int(total)


# ---------------------------------------------------------------------------
# 4. Teléfonos — detección de faltantes de prefijo
# ---------------------------------------------------------------------------

def _detectar_telefonos(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """
    Detecta teléfonos sin prefijo internacional (+).
    Agrega columna 'telefono_sin_prefijo' (bool). No modifica el número.
    """
    col = _encontrar_col(df, "telefono")
    if col is None:
        return df, 0

    df[col] = df[col].str.strip()

    sin_prefijo = df[col].apply(
        lambda x: not str(x).startswith("+") if pd.notna(x) else False
    )
    df["telefono_sin_prefijo"] = sin_prefijo
    total = sin_prefijo.sum()
    return df, int(total)


# ---------------------------------------------------------------------------
# 5. Clasificación de duplicados
# ---------------------------------------------------------------------------

def _clasificar_duplicados(df: pd.DataFrame) -> Tuple[pd.DataFrame, int, int]:
    """
    Clasifica duplicados en dos tipos:
        - duplicado_real: mismo nombre+correo con stage=Duplicado explícito
        - duplicado_journey: mismo nombre+correo en diferentes stages
          (esto NO es error — es el progreso del lead en el funnel)

    Agrega columna 'tipo_duplicado': None | "real" | "journey"
    """
    nombre_col = _encontrar_col(df, "nombre")
    correo_col = _encontrar_col(df, "correo")
    stage_col  = _encontrar_col(df, "stage")

    df["tipo_duplicado"] = None

    if nombre_col is None or correo_col is None:
        return df, 0, 0

    clave = df[[nombre_col, correo_col]].apply(
        lambda r: f"{str(r.iloc[0]).lower().strip()}|{str(r.iloc[1]).lower().strip()}", axis=1
    )
    duplicados_mask = clave.duplicated(keep=False)

    reales = 0
    journeys = 0

    if stage_col and duplicados_mask.any():
        grupos = df[duplicados_mask].groupby(clave[duplicados_mask])
        for _, grupo in grupos:
            stages = grupo[stage_col].str.lower().str.strip().dropna().tolist()
            if "duplicado" in stages or "duplicate" in stages:
                df.loc[grupo.index, "tipo_duplicado"] = "real"
                reales += len(grupo)
            else:
                df.loc[grupo.index, "tipo_duplicado"] = "journey"
                journeys += len(grupo)

    return df, reales, journeys


# ---------------------------------------------------------------------------
# 6. Normalización de stages
# ---------------------------------------------------------------------------

def _normalizar_stages(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """
    Mapea stages en inglés/español a vocabulario canónico.
    Los stages desconocidos se dejan como están (no se eliminan).
    Retorna df modificado y cantidad de stages normalizados.
    """
    col = _encontrar_col(df, "stage")
    if col is None:
        return df, 0

    def _mapear(val):
        if pd.isna(val):
            return val
        clave = str(val).strip().lower()
        return STAGE_MAP.get(clave, str(val).strip())  # desconocido → sin cambio

    original = df[col].copy()
    df[col] = df[col].apply(_mapear)
    cambiados = (df[col] != original).sum()
    return df, int(cambiados)


# ---------------------------------------------------------------------------
# Helper — buscar columna con tolerancia a espacios y capitalización
# ---------------------------------------------------------------------------

def _encontrar_col(df: pd.DataFrame, nombre: str) -> str | None:
    nombre_limpio = nombre.strip().lower()
    for col in df.columns:
        if col.strip().lower() == nombre_limpio:
            return col
    return None


# ---------------------------------------------------------------------------
# FUNCIÓN PRINCIPAL
# ---------------------------------------------------------------------------

def normalizar(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    """
    Pipeline completo de normalización defensiva.

    Args:
        df: DataFrame crudo tal como viene de Sheets / CSV / Excel

    Returns:
        (df_normalizado, reporte)
        El reporte es un dict con mensajes en lenguaje natural
        listos para mostrarle al usuario.
    """
    df = df.copy()
    reporte = {
        "total_filas": len(df),
        "problemas": [],
        "info": [],
    }

    # 1. Strip nombres de columna
    df = _limpiar_nombres_columnas(df)

    # 2. NONE string → NaN
    df, n_nulos = _normalizar_nulos_string(df)
    if n_nulos > 0:
        reporte["problemas"].append(
            f"{n_nulos} celdas tenían 'NONE' o 'null' escrito como texto — "
            f"Adly los convirtió a vacíos reales."
        )

    # 3. Emails
    df, n_emails = _detectar_emails(df)
    if n_emails > 0:
        reporte["problemas"].append(
            f"{n_emails} correos tienen caracteres inválidos (tildes, espacios, @ doble). "
            f"Pueden fallar si intentas enviarles un email — revísalos antes de una campaña."
        )

    # 4. Teléfonos
    df, n_tel = _detectar_telefonos(df)
    if n_tel > 0:
        reporte["problemas"].append(
            f"{n_tel} teléfonos no tienen código de país (+1, +52, etc.). "
            f"Sin esto no puedes saber de qué país es el lead ni hacer llamadas internacionales."
        )

    # 5. Duplicados
    df, n_reales, n_journeys = _clasificar_duplicados(df)
    if n_reales > 0:
        reporte["problemas"].append(
            f"{n_reales} leads están marcados como duplicados reales — "
            f"son el mismo contacto registrado dos veces por error."
        )
    if n_journeys > 0:
        reporte["info"].append(
            f"{n_journeys} leads aparecen varias veces porque avanzaron por el funnel "
            f"(de Lead a Cita Agendada, por ejemplo). Eso es normal y esperado."
        )

    # 6. Stages
    df, n_stages = _normalizar_stages(df)
    if n_stages > 0:
        reporte["info"].append(
            f"{n_stages} stages fueron unificados al mismo vocabulario "
            f"(ej: 'Closed Won' → 'Cerrado Ganado')."
        )

    # 7. Attribution parser
    if _ATTRIBUTION_DISPONIBLE:
        df = parsear_todas_atribuciones(df)
        rep_attr = reporte_atribucion(df)
        reporte["problemas"].extend(rep_attr.get("problemas", []))
    else:
        reporte["info"].append(
            "attribution_parser no disponible — columnas de atribución no fueron expandidas."
        )

    # Resumen final
    total_problemas = len(reporte["problemas"])
    if total_problemas == 0:
        reporte["resumen"] = "✅ Los datos se ven limpios. No se encontraron problemas estructurales."
    else:
        reporte["resumen"] = (
            f"⚠️ Se encontraron {total_problemas} tipos de problemas en tus datos. "
            f"Adly los manejó automáticamente, pero deberías revisarlos para mejorar "
            f"la precisión de tu análisis."
        )

    return df, reporte


# ---------------------------------------------------------------------------
# Utilidad de diagnóstico — para /alertas y debug
# ---------------------------------------------------------------------------

def diagnostico_rapido(df: pd.DataFrame) -> str:
    """
    Versión compacta del reporte para mostrar en CLI o chat.
    No modifica el df — solo informa.
    """
    _, reporte = normalizar(df)
    lineas = [reporte["resumen"], ""]

    if reporte["problemas"]:
        lineas.append("🔴 Problemas:")
        for p in reporte["problemas"]:
            lineas.append(f"   • {p}")
        lineas.append("")

    if reporte["info"]:
        lineas.append("ℹ️  Info:")
        for i in reporte["info"]:
            lineas.append(f"   • {i}")

    return "\n".join(lineas)
