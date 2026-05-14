# attribution_parser.py — Adly · Data-Buddy
# Explota celdas de atribución múltiple antes de que el planner vea el df.
#
# Principio rector (agnóstico):
#   ¿La jerarquía de atribución varía en N formas? → SÍ
#   → No hardcodear "campaña/adset/creativo" ni ningún nombre de plataforma.
#   → Detectar separador por frecuencia en el dato.
#   → Nombrar partes por posición relativa (p1, p2, p3...).
#   → Opcionalmente: el usuario configura nombres en .env.
#
# Firma pública:
#   parse_attributions(df, niveles_config?)  → AttributionResult
#   result.df                                → pd.DataFrame enriquecido
#   result.columnas_nuevas                   → list[str]
#   result.resumen()                         → str (<100 tokens)
#   schema_para_planner(result)              → str (inyectable al planner)

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


# ─────────────────────────────────────────────────────────────
# CONSTANTES — solo protocolo de Adly, nunca del dominio del cliente
# ─────────────────────────────────────────────────────────────

# Separadores candidatos en orden de especificidad
_SEP_CANDIDATOS = [" | ", " / ", " ; ", " + ", "|", "/"]

# Patrones para detectar columnas de atribución — amplios, no de plataforma
_PATRON_ATRIBUCION = [
    "atribucion", "attribution", "atribución",
    "fuente", "source", "origen",
    "canal", "channel",
    "medio", "medium",
]

# Límite de partes — defensa contra datos malformados
_MAX_PARTES = 8

# Clave de .env para nombres de niveles opcionales
# Formato: ADLY_ATTRIBUTION_LEVELS=campaña,adset,creativo
_ENV_LEVELS_KEY = "ADLY_ATTRIBUTION_LEVELS"

# Pseudo-nulos a ignorar al extraer partes
_PSEUDO_NULOS = frozenset({"none", "null", "n/a", "na", "nan", "-", ""})


# ─────────────────────────────────────────────────────────────
# CONFIGURACIÓN OPCIONAL
# ─────────────────────────────────────────────────────────────

def _leer_niveles_config() -> Optional[list[str]]:
    """
    Lee nombres de niveles desde ADLY_ATTRIBUTION_LEVELS en .env.
    Si no existe → None → se usarán p1, p2, p3 (siempre correcto).
    """
    raw = os.getenv(_ENV_LEVELS_KEY, "").strip()
    if not raw:
        return None
    niveles = [n.strip() for n in raw.split(",") if n.strip()]
    return niveles or None


# ─────────────────────────────────────────────────────────────
# RESULTADO
# ─────────────────────────────────────────────────────────────

@dataclass
class AttributionResult:
    df:                object
    columnas_nuevas:   list[str] = field(default_factory=list)
    columnas_fuente:   list[str] = field(default_factory=list)
    separador:         str       = " | "
    celdas_explotadas: int       = 0
    partes_por_col:    dict      = field(default_factory=dict)
    advertencias:      list[str] = field(default_factory=list)

    def resumen(self) -> str:
        if not self.columnas_nuevas:
            return "Sin atribución múltiple detectada."
        return (
            f"Atribución explotada: sep='{self.separador}' | "
            f"Columnas nuevas: {', '.join(self.columnas_nuevas)} | "
            f"Celdas procesadas: {self.celdas_explotadas}"
        )


# ─────────────────────────────────────────────────────────────
# CAPA 1 — DETECCIÓN DE COLUMNAS
# Criterio doble: nombre semántico + verificación por contenido
# ─────────────────────────────────────────────────────────────

def _detectar_cols_atribucion(df: pd.DataFrame) -> list[str]:
    candidatas = []
    for col in df.columns:
        if not any(p in col.lower() for p in _PATRON_ATRIBUCION):
            continue
        vals = df[col].dropna().astype(str)
        if len(vals) == 0:
            continue
        for sep in _SEP_CANDIDATOS:
            if vals.apply(lambda x: sep in x).mean() > 0.05:
                candidatas.append(col)
                break
    return candidatas


# ─────────────────────────────────────────────────────────────
# CAPA 2 — DETECCIÓN DE SEPARADOR
# Por frecuencia en el dato — nunca asumido
# ─────────────────────────────────────────────────────────────

def _detectar_separador(df: pd.DataFrame, col: str) -> Optional[str]:
    vals = df[col].dropna().astype(str)
    if len(vals) == 0:
        return None
    mejor, mayor = None, 0
    for sep in _SEP_CANDIDATOS:
        n = vals.apply(lambda x: sep in x).sum()
        if n > mayor:
            mayor, mejor = n, sep
    return mejor if mayor > 0 else None


# ─────────────────────────────────────────────────────────────
# CAPA 3 — DETECCIÓN DE N_PARTES
# Por el dato real — nunca hardcodeado
# ─────────────────────────────────────────────────────────────

def _detectar_n_partes(df: pd.DataFrame, col: str, sep: str) -> int:
    vals_multi = df[col].dropna().astype(str)
    vals_multi = vals_multi[vals_multi.apply(lambda x: sep in x)]
    if len(vals_multi) == 0:
        return 1
    return min(
        int(vals_multi.apply(lambda x: len(x.split(sep))).max()),
        _MAX_PARTES,
    )


# ─────────────────────────────────────────────────────────────
# CAPA 4 — NOMBRES DE PARTES
# Sin config → p1, p2, p3 (posición, siempre correcto)
# Con config → nombres que el usuario definió (opcional)
# ─────────────────────────────────────────────────────────────

def _nombres_partes(col_alias: str, n_partes: int,
                    niveles_config: Optional[list[str]]) -> list[str]:
    nombres = []
    for i in range(n_partes):
        if niveles_config and i < len(niveles_config):
            sufijo = niveles_config[i]
        else:
            sufijo = f"p{i + 1}"
        nombres.append(f"{col_alias}__{sufijo}")
    return nombres


# ─────────────────────────────────────────────────────────────
# CAPA 5 — EXPLOSIÓN
# No toca la columna original — solo agrega
# ─────────────────────────────────────────────────────────────

def _extraer_parte(valor, idx: int, sep: str) -> Optional[str]:
    if pd.isna(valor):
        return None
    s = str(valor).strip()
    if s.lower() in _PSEUDO_NULOS:
        return None
    partes = [p.strip() for p in s.split(sep)]
    if idx >= len(partes):
        return None
    v = partes[idx]
    return None if v.lower() in _PSEUDO_NULOS else v


def _explotar_columna(df: pd.DataFrame, col: str,
                      sep: str, nombres: list[str]) -> tuple[pd.DataFrame, int]:
    df    = df.copy()
    n_exp = int(df[col].dropna().astype(str).apply(lambda x: sep in x).sum())
    for i, nombre in enumerate(nombres):
        df[nombre] = df[col].apply(lambda x: _extraer_parte(x, i, sep))
    return df, n_exp


# ─────────────────────────────────────────────────────────────
# PUNTO DE ENTRADA PÚBLICO
# ─────────────────────────────────────────────────────────────

def parse_attributions(df: pd.DataFrame,
                       niveles_config: Optional[list[str]] = None) -> AttributionResult:
    """
    Detecta columnas con atribución múltiple y las explota en columnas simples.

    No asume plataforma, jerarquía, separador, ni número de partes.
    Todo se detecta del dato.

    niveles_config: nombres opcionales para las partes.
      None       → p1, p2, p3 (siempre correcto)
      ["x","y"]  → col__x, col__y (si el usuario sabe su jerarquía)
      También se lee de ADLY_ATTRIBUTION_LEVELS en .env.
    """
    if niveles_config is None:
        niveles_config = _leer_niveles_config()

    cols_atribucion = _detectar_cols_atribucion(df)
    if not cols_atribucion:
        return AttributionResult(df=df)

    columnas_nuevas  = []
    columnas_fuente  = []
    partes_por_col   = {}
    total_explotadas = 0
    advertencias     = []
    sep_global       = None

    for col in cols_atribucion:
        sep = _detectar_separador(df, col)
        if not sep:
            advertencias.append(f"'{col}': sin separador — omitida")
            continue

        if sep_global is None:
            sep_global = sep

        n_partes = _detectar_n_partes(df, col, sep)
        if n_partes <= 1:
            advertencias.append(f"'{col}': 1 sola parte — no requiere explosión")
            continue

        col_alias = re.sub(r"[^a-z0-9_]", "_", col.lower()).strip("_")
        col_alias = re.sub(r"_+", "_", col_alias)

        nombres = _nombres_partes(col_alias, n_partes, niveles_config)

        # Evitar colisiones
        nombres_unicos = []
        for nombre in nombres:
            candidato, n = nombre, 2
            while candidato in df.columns or candidato in columnas_nuevas:
                candidato = f"{nombre}_{n}"
                n += 1
            nombres_unicos.append(candidato)

        df, n_exp = _explotar_columna(df, col, sep, nombres_unicos)

        columnas_nuevas.extend(nombres_unicos)
        columnas_fuente.append(col)
        partes_por_col[col] = n_partes
        total_explotadas    += n_exp

    return AttributionResult(
        df               = df,
        columnas_nuevas  = columnas_nuevas,
        columnas_fuente  = columnas_fuente,
        separador        = sep_global or " | ",
        celdas_explotadas= total_explotadas,
        partes_por_col   = partes_por_col,
        advertencias     = advertencias,
    )


def schema_para_planner(result: AttributionResult) -> str:
    """
    Texto comprimido para el prompt del planner.
    Le dice qué columnas nuevas existen y de dónde vienen.
    <80 tokens.
    """
    if not result.columnas_nuevas:
        return ""

    lineas = ["ATRIBUCIÓN EXPLOTADA — usar estas columnas para análisis:"]
    for col_orig in result.columnas_fuente:
        alias = re.sub(r"[^a-z0-9_]", "_", col_orig.lower()).strip("_")
        alias = re.sub(r"_+", "_", alias)
        cols_de_esta = [c for c in result.columnas_nuevas if c.startswith(alias)]
        n = result.partes_por_col.get(col_orig, len(cols_de_esta))
        lineas.append(f"  '{col_orig}' → {n} partes: {', '.join(cols_de_esta)}")

    return "\n".join(lineas)
