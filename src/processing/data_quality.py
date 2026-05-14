# data_quality.py — Adly · Data-Buddy
# Detección de calidad de datos agnóstica por diseño.
#
# Principio rector:
#   ¿Esto puede variar en N formas indeterminadas? → detección dinámica.
#   Ningún nombre de columna, separador, encoding o valor de dominio
#   va hardcodeado. Las reglas cubren patrones — el LLM cubre semántica.
#
# Capas:
#   CAPA 0 — Detección de carga  : encoding, separador, header row
#   CAPA 1 — Normalización       : nulos, whitespace, columnas, case
#   CAPA 2 — Detección de errores: nulos, duplicados, email, phone,
#                                   fechas, multi-valor, case
#   CAPA 3 — Reporte             : dict, resumen comprimido, severity score
#
# Firma pública — no cambiar sin versionar:
#   DataQualityReport.from_file(path)  → DataQualityReport
#   DataQualityReport.from_df(df)      → DataQualityReport
#   report.to_summary()                → str   (<200 tokens para el LLM)
#   report.to_dict()                   → dict  (para RespuestaAdly)
#   report.severity_score()            → int   (0-100)
#   report.normalized_df               → pd.DataFrame (listo para el engine)

from __future__ import annotations

import re
import io
import logging
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

logger = logging.getLogger("adly.data_quality")


# ─────────────────────────────────────────────────────────────
# CONSTANTES — únicas cosas que NO varían por cliente
# (son parte del protocolo de Adly, no del dato del cliente)
# ─────────────────────────────────────────────────────────────

# Encodings probados en orden de probabilidad para fuentes LATAM
_ENCODINGS = ["utf-8", "utf-8-sig", "latin-1", "iso-8859-1", "cp1252", "utf-16"]

# Separadores de CSV probados por frecuencia en primera línea
_CSV_SEPARATORS = [";", ",", "\t", "|", " "]

# Pseudo-nulos — valores string que significan "vacío" pero no son NaN
_PSEUDO_NULLS = frozenset([
    "none", "null", "n/a", "na", "nil", "n.a.", "n.d.",
    "-", "--", "---", "?", ".", "undefined", "empty",
    "sin dato", "sin información", "s/d", "s/i", "no data",
])

# Separadores que pueden aparecer dentro de celdas multi-valor
# Detectados dinámicamente — esta lista solo inicializa la búsqueda
_MULTIVALUE_SEPARATORS = [" | ", "|", " / ", " ; ", " + "]

# Umbrales de severity — cuánto % de registros afectados sube el score
_SEVERITY_WEIGHTS = {
    "duplicados_clave":     30,
    "pseudo_nulos":         10,
    "email_roto":           20,
    "email_dominio_roto":   15,
    "email_multi_at":       15,
    "phone_sin_prefijo":    10,
    "stage_nulo":           15,
    "multivalue_1fn":       20,
    "case_email":            5,
    "whitespace_valores":    5,
}

# Sufijos que identifican columnas de flags generadas por Adly
# Agnóstico: cualquier columna que termine en estos sufijos es metadata interna
# NO son datos del negocio del cliente — excluir del análisis de calidad
_SUFIJOS_FLAGS_ADLY = (
    "_sospechoso", "_sin_prefijo", "_duplicado", "_valido",
    "_flag", "_raw", "_alias", "_norm", "_limpio",
)


def _es_columna_flag(col: str, dtype) -> bool:
    """
    True si la columna es un flag interno de Adly — no datos del cliente.

    Criterios (OR):
    1. dtype == bool  → siempre es un flag computado
    2. nombre termina en sufijo de flag conocido de Adly

    Agnóstico: no busca nombres específicos, busca patrones de sufijo.
    """
    if dtype == "bool":
        return True
    col_lower = col.lower()
    return any(col_lower.endswith(suf) for suf in _SUFIJOS_FLAGS_ADLY)


# ─────────────────────────────────────────────────────────────
# CAPA 0 — DETECCIÓN DE CARGA
# ─────────────────────────────────────────────────────────────

def detect_encoding(path: str) -> str:
    """
    Detecta el encoding del archivo probando en orden de probabilidad.
    Usa chardet como fallback si todos los candidatos fallan.
    Nunca falla — devuelve 'latin-1' como último recurso (lee todo).
    """
    # Intentar con la lista predefinida
    for enc in _ENCODINGS:
        try:
            with open(path, encoding=enc) as f:
                f.read(4096)  # leer solo el inicio — suficiente para detectar
            return enc
        except (UnicodeDecodeError, LookupError):
            continue

    # Fallback: chardet
    try:
        import chardet
        with open(path, "rb") as f:
            raw = f.read(32768)
        detected = chardet.detect(raw)
        enc = detected.get("encoding") or "latin-1"
        logger.info(f"chardet detectó encoding: {enc} (confianza: {detected.get('confidence', 0):.0%})")
        return enc
    except ImportError:
        pass

    logger.warning("No se pudo detectar encoding — usando latin-1 como fallback")
    return "latin-1"


def detect_separator(path: str, encoding: str) -> str:
    """
    Detecta el separador de CSV contando frecuencia en las primeras 5 líneas.
    El separador con mayor frecuencia consistente gana.
    Nunca falla — devuelve ',' como default estándar CSV.
    """
    try:
        with open(path, encoding=encoding, errors="replace") as f:
            lines = [f.readline() for _ in range(5)]
        lines = [l for l in lines if l.strip()]

        mejor_sep = ","
        mejor_score = 0

        for sep in _CSV_SEPARATORS:
            conteos = [l.count(sep) for l in lines]
            # Consistente = todos los conteos iguales y > 0
            if len(set(conteos)) == 1 and conteos[0] > 0:
                score = conteos[0] * 10  # consistencia perfecta tiene bonus
            else:
                score = min(conteos) if conteos else 0  # mínimo consistente

            if score > mejor_score:
                mejor_score = score
                mejor_sep = sep

        return mejor_sep
    except Exception as e:
        logger.warning(f"detect_separator falló: {e} — usando ','")
        return ","


def load_dataframe(path: str) -> tuple[pd.DataFrame, dict]:
    """
    Carga un CSV de forma agnóstica: detecta encoding y separador.
    Limpia trailing spaces en nombres de columna automáticamente.

    Retorna:
        (df, load_info) donde load_info tiene encoding, sep, shape detectados.
    """
    encoding = detect_encoding(path)
    sep      = detect_separator(path, encoding)

    df = pd.read_csv(path, encoding=encoding, sep=sep, dtype=str)

    # Limpiar trailing spaces en nombres de columna — error silencioso frecuente
    df.columns = [c.strip() for c in df.columns]

    load_info = {
        "encoding": encoding,
        "separator": sep,
        "shape": df.shape,
        "path": path,
    }
    logger.info(f"CSV cargado: {df.shape} | encoding={encoding} | sep={repr(sep)}")
    return df, load_info


# ─────────────────────────────────────────────────────────────
# CAPA 1 — NORMALIZACIÓN (determinista, cero LLM)
# ─────────────────────────────────────────────────────────────

def normalize_nulls(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Convierte pseudo-nulos a NaN real.
    Detecta dinámicamente qué valores son pseudo-nulos por columna.
    No asume qué columnas tienen este problema.

    Retorna (df_normalizado, reporte_por_columna).
    """
    df    = df.copy()
    reporte = {}

    for col in df.columns:
        mask = df[col].astype(str).str.strip().str.lower().isin(_PSEUDO_NULLS)
        n = mask.sum()
        if n > 0:
            reporte[col] = {"pseudo_nulos_convertidos": int(n)}
            df.loc[mask, col] = None  # NaN real

    return df, reporte


def normalize_whitespace(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Hace strip() en todos los valores string del DataFrame.
    También colapsa espacios internos múltiples a uno solo.
    No toca columnas numéricas ni fechas ya parseadas.

    Retorna (df_normalizado, reporte).
    """
    df    = df.copy()
    total = 0

    for col in df.columns:
        if df[col].dtype == object:
            antes = df[col].copy()
            # strip + colapsar espacios múltiples internos
            df[col] = df[col].apply(
                lambda x: re.sub(r" {2,}", " ", str(x).strip())
                if pd.notna(x) else x
            )
            cambiados = (df[col] != antes).sum()
            if cambiados > 0:
                total += int(cambiados)

    return df, {"valores_normalizados": total}


def normalize_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Genera alias sanitizados de nombres de columna para el sandbox del planner.
    No renombra el df — agrega un mapeo original→alias.

    El alias: lowercase, tildes removidas, espacios→underscore.
    Permite que el planner use df['ad_primera_atribucion'] o
    df['ad primera atribucion'] — ambos funcionan via rename temporal.

    Retorna (df_con_alias, mapeo).
    """
    _TILDES = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")

    mapeo = {}
    for col in df.columns:
        alias = col.lower().translate(_TILDES).replace(" ", "_").replace("-", "_")
        alias = re.sub(r"[^a-z0-9_]", "", alias)
        alias = re.sub(r"_+", "_", alias).strip("_")
        mapeo[col] = alias

    return df, mapeo


def normalize_emails(df: pd.DataFrame, col_email: str) -> tuple[pd.DataFrame, dict]:
    """
    Normaliza emails a lowercase y hace strip.
    Solo aplica si la columna existe — agnóstico a su nombre.
    """
    if col_email not in df.columns:
        return df, {}
    df = df.copy()
    df[col_email] = df[col_email].apply(
        lambda x: str(x).strip().lower() if pd.notna(x) else x
    )
    return df, {"col": col_email}


# ─────────────────────────────────────────────────────────────
# CAPA 2 — DETECCIÓN DE ERRORES
# ─────────────────────────────────────────────────────────────

def check_nulls(df: pd.DataFrame) -> dict:
    """
    Reporte de nulos reales por columna con porcentaje.
    Incluye clasificación de severidad por columna.
    """
    total   = len(df)
    reporte = {}
    for col in df.columns:
        n = int(df[col].isna().sum())
        if n > 0:
            pct = round(n / total * 100, 1)
            reporte[col] = {
                "nulos": n,
                "pct": pct,
                "severidad": "critical" if pct > 30 else "warning" if pct > 10 else "info",
            }
    return reporte


def check_duplicates(df: pd.DataFrame, claves: list[str] = None) -> dict:
    """
    Detecta duplicados exactos y por clave(s) configurable.
    Si claves=None, intenta detectar columna de email automáticamente.
    Agnóstico — funciona con cualquier columna como clave.
    """
    reporte = {
        "duplicados_exactos": int(df.duplicated(keep=False).sum()),
        "por_clave": {},
    }

    # Auto-detectar columna email si no se pasan claves
    if claves is None:
        claves = _detectar_cols_email(df)

    for clave in claves:
        if clave not in df.columns:
            continue
        filas_dup = int(df.duplicated(subset=[clave], keep=False).sum())
        claves_dup = int(df[df.duplicated(subset=[clave], keep=False)][clave].nunique())
        if filas_dup > 0:
            reporte["por_clave"][clave] = {
                "filas_afectadas": filas_dup,
                "valores_duplicados": claves_dup,
                "pct": round(filas_dup / len(df) * 100, 1),
            }

    return reporte


def check_email(df: pd.DataFrame) -> dict:
    """
    Detecta errores en columnas de email.
    Auto-detecta columnas semánticas de email — no asume nombre 'correo'.
    Detecta:
      - RFC 5321: caracteres inválidos en parte local
      - Multi-@: más de un arroba
      - Dominio sin TLD: @gmailcom, @outlookcom
      - Uppercase: no normalizado
      - Espacios: no stripped
    """
    cols_email = _detectar_cols_email(df)
    if not cols_email:
        return {}

    reporte = {}
    for col in cols_email:
        serie  = df[col].dropna().astype(str)
        total  = len(serie)
        if total == 0:
            continue

        multi_at       = serie.apply(lambda x: x.count("@") > 1)
        dominio_roto   = serie.apply(_dominio_roto)
        local_invalido = serie.apply(_local_invalido_rfc5321)
        uppercase      = serie.apply(lambda x: any(c.isupper() for c in x))
        con_espacios   = serie.apply(lambda x: x != x.strip())

        reporte[col] = {
            "multi_at":       int(multi_at.sum()),
            "dominio_roto":   int(dominio_roto.sum()),
            "local_invalido": int(local_invalido.sum()),
            "uppercase":      int(uppercase.sum()),
            "con_espacios":   int(con_espacios.sum()),
            "total_revisados": total,
            # Ejemplos de rotos para el reporte
            "ejemplos_rotos": serie[
                multi_at | dominio_roto | local_invalido
            ].head(5).tolist(),
        }

    return reporte


def check_phone(df: pd.DataFrame) -> dict:
    """
    Detecta problemas en columnas de teléfono.
    Auto-detecta columnas semánticas de teléfono.
    Detecta: sin prefijo +, con letras, muy cortos/largos.
    """
    cols_phone = _detectar_cols_phone(df)
    if not cols_phone:
        return {}

    reporte = {}
    for col in cols_phone:
        serie = df[col].dropna().astype(str).str.strip()
        total = len(serie)
        if total == 0:
            continue

        sin_prefijo  = (~serie.str.startswith("+")).sum()
        con_letras   = serie.apply(lambda x: bool(re.search(r"[a-zA-Z]", x))).sum()
        muy_corto    = (serie.str.replace(r"[^\d]", "", regex=True).str.len() < 7).sum()
        muy_largo    = (serie.str.replace(r"[^\d]", "", regex=True).str.len() > 15).sum()

        reporte[col] = {
            "sin_prefijo_internacional": int(sin_prefijo),
            "con_letras":  int(con_letras),
            "muy_corto":   int(muy_corto),
            "muy_largo":   int(muy_largo),
            "total_revisados": total,
            "pct_sin_prefijo": round(sin_prefijo / total * 100, 1) if total else 0,
        }

    return reporte


def check_dates(df: pd.DataFrame) -> dict:
    """
    Detecta columnas de fecha y verifica:
      - Formatos mixtos dentro de la misma columna
      - Fechas no parseables
      - Fechas fuera de rango razonable (configurable)
    """
    cols_fecha = _detectar_cols_fecha(df)
    if not cols_fecha:
        return {}

    reporte = {}
    for col in cols_fecha:
        serie = df[col].dropna().astype(str)
        total = len(serie)
        if total == 0:
            continue

        # Intentar parsear — format=mixed para no generar warnings de dateutil
        try:
            parsed = pd.to_datetime(serie, errors="coerce", format="mixed")
        except TypeError:
            parsed = pd.to_datetime(serie, errors="coerce")
        no_parse  = int(parsed.isna().sum())

        # Rango razonable — heurística: entre 2015 y 5 años en el futuro
        desde = pd.Timestamp("2015-01-01")
        hasta = pd.Timestamp.now() + pd.DateOffset(years=5)
        fuera_rango = int(((parsed < desde) | (parsed > hasta)).sum())

        # Detectar diversidad de formatos
        patrones = {
            r"^\d{4}-\d{2}-\d{2}":  "YYYY-MM-DD",
            r"^\d{2}/\d{2}/\d{4}":  "DD/MM/YYYY",
            r"^\d{2}-\d{2}-\d{4}":  "MM-DD-YYYY",
            r"^\d{4}/\d{2}/\d{2}":  "YYYY/MM/DD",
        }
        formatos_detectados = {}
        for pat, nombre in patrones.items():
            n = serie.str.match(pat).sum()
            if n > 0:
                formatos_detectados[nombre] = int(n)

        reporte[col] = {
            "no_parseables":  no_parse,
            "fuera_de_rango": fuera_rango,
            "formatos":       formatos_detectados,
            "formatos_mixtos": len(formatos_detectados) > 1,
            "total_revisados": total,
        }

    return reporte


def check_multivalue(df: pd.DataFrame) -> dict:
    """
    Detecta columnas con múltiples valores en una celda (violación 1FN).
    Detecta el separador dinámicamente por columna — no asume '|'.
    Reporta: columna, separador detectado, cantidad de celdas, ejemplos.
    """
    reporte = {}

    for col in df.columns:
        serie = df[col].dropna().astype(str)
        if len(serie) == 0:
            continue

        for sep in _MULTIVALUE_SEPARATORS:
            n = serie.apply(lambda x: sep in x).sum()
            if n > 0:
                # Cuántos valores promedio por celda
                afectadas = serie[serie.apply(lambda x: sep in x)]
                avg_vals  = afectadas.apply(lambda x: len(x.split(sep))).mean()

                reporte[col] = {
                    "separador":      repr(sep),
                    "celdas_afectadas": int(n),
                    "pct": round(n / len(serie) * 100, 1),
                    "valores_promedio_por_celda": round(float(avg_vals), 1),
                    "ejemplos": afectadas.head(3).tolist(),
                    "violacion": "1FN",
                }
                break  # un separador por columna es suficiente

    return reporte


def check_case(df: pd.DataFrame) -> dict:
    """
    Detecta inconsistencia de case en columnas categóricas.
    Si el mismo valor aparece en >=2 variantes de case → reportar.
    Útil para detectar 'Hilda Pomares' vs 'HILDA POMARES' vs 'hilda pomares'.
    """
    reporte = {}

    for col in df.columns:
        serie = df[col].dropna().astype(str)
        n_unicos = serie.nunique()

        # Solo tiene sentido en columnas categóricas (pocos únicos)
        if n_unicos > 200 or n_unicos == 0:
            continue

        # Agrupar por lowercase y contar variantes
        grupos = serie.groupby(serie.str.lower().str.strip()).apply(
            lambda g: g.unique().tolist()
        )
        con_variantes = {k: v for k, v in grupos.items() if len(v) > 1}

        if con_variantes:
            # Cuántos registros están afectados
            vals_inconsistentes = set(
                v for variants in con_variantes.values() for v in variants
            )
            afectados = serie.isin(vals_inconsistentes).sum()

            reporte[col] = {
                "valores_con_variantes_de_case": len(con_variantes),
                "filas_afectadas": int(afectados),
                "ejemplos": dict(list(con_variantes.items())[:5]),
            }

    return reporte


def check_normal_forms(df: pd.DataFrame, multivalue_report: dict) -> dict:
    """
    Detecta violaciones de formas normales detectables sin conocer el schema.

    1FN — ya detectado por check_multivalue (múltiples valores en celda).
    2FN — columnas que parecen depender de un subconjunto de otra columna.
         Heurística: si col A y col B tienen el mismo patrón semántico
         (ej: 'ad primera' y 'ad set primera') probablemente violan 2FN.
    3FN — solo detecta el caso más obvio: columnas que son derivadas
         directas de otra (mismo contenido >90% de las veces).
    """
    reporte = {"1FN": [], "2FN": [], "3FN": []}

    # 1FN — desde multivalue_report
    for col, info in multivalue_report.items():
        reporte["1FN"].append({
            "columna": col,
            "descripcion": f"{info['celdas_afectadas']} celdas con sep={info['separador']}",
        })

    # 2FN — detectar pares de columnas con nombres similares
    # Patrón: misma raíz semántica con sufijo (primera/segunda, 1/2, a/b)
    cols = df.columns.tolist()
    sufijos_pares = [
        ("primera", "segunda"), ("1", "2"), ("a", "b"),
        ("_1", "_2"), ("primera atribucion", "segunda atribucion"),
    ]
    for i, col_a in enumerate(cols):
        for col_b in cols[i+1:]:
            for suf_a, suf_b in sufijos_pares:
                if col_a.lower().endswith(suf_a) and col_b.lower().endswith(suf_b):
                    raiz_a = col_a.lower()[:-len(suf_a)].strip()
                    raiz_b = col_b.lower()[:-len(suf_b)].strip()
                    if raiz_a == raiz_b and raiz_a:
                        reporte["2FN"].append({
                            "columnas": [col_a, col_b],
                            "descripcion": (
                                f"'{col_a}' y '{col_b}' sugieren atribución múltiple. "
                                f"Candidato a tabla separada: "
                                f"lead_atribuciones(lead_id, valor, orden)"
                            ),
                        })

    # 3FN — columna casi idéntica a otra (>90% correlación de valores únicos)
    # Solo para columnas con pocos únicos (categóricas)
    cat_cols = [c for c in cols if df[c].nunique() < 50]
    for i, col_a in enumerate(cat_cols):
        for col_b in cat_cols[i+1:]:
            try:
                overlap = df[[col_a, col_b]].dropna()
                if len(overlap) < 10:
                    continue
                # Si cuando A toma valor X, B siempre toma el mismo valor
                determinismo = overlap.groupby(col_a)[col_b].nunique()
                if (determinismo == 1).mean() > 0.9 and overlap[col_b].nunique() > 1:
                    reporte["3FN"].append({
                        "columnas": [col_a, col_b],
                        "descripcion": (
                            f"'{col_b}' parece ser determinada funcionalmente por '{col_a}'. "
                            f"Posible violación 3FN."
                        ),
                    })
            except Exception:
                continue

    # Limpiar listas vacías
    return {k: v for k, v in reporte.items() if v}


# ─────────────────────────────────────────────────────────────
# CAPA 3 — REPORTE
# ─────────────────────────────────────────────────────────────

@dataclass
class DataQualityReport:
    """
    Reporte completo de calidad de datos.
    Inmutable después de construido — se genera una vez al cargar el df.
    """
    total_filas:      int
    total_columnas:   int
    load_info:        dict  = field(default_factory=dict)
    col_alias:        dict  = field(default_factory=dict)  # original→alias sanitizado
    nulls:            dict  = field(default_factory=dict)
    duplicates:       dict  = field(default_factory=dict)
    emails:           dict  = field(default_factory=dict)
    phones:           dict  = field(default_factory=dict)
    dates:            dict  = field(default_factory=dict)
    multivalue:       dict  = field(default_factory=dict)
    case_issues:      dict  = field(default_factory=dict)
    normal_forms:     dict  = field(default_factory=dict)
    normalized_df:    object = field(default=None, repr=False)  # pd.DataFrame

    @classmethod
    def from_file(cls, path: str) -> "DataQualityReport":
        """Carga un CSV y genera el reporte completo."""
        df, load_info = load_dataframe(path)
        return cls._build(df, load_info)

    @classmethod
    def from_df(cls, df: pd.DataFrame) -> "DataQualityReport":
        """Genera el reporte desde un DataFrame ya cargado."""
        return cls._build(df.copy(), {})

    @classmethod
    def _build(cls, df: pd.DataFrame, load_info: dict) -> "DataQualityReport":
        """Pipeline completo de normalización + detección."""

        # Separar columnas de flags de Adly — son metadata interna, no datos del cliente
        cols_datos = [col for col in df.columns if not _es_columna_flag(col, str(df[col].dtype))]
        cols_flags = [col for col in df.columns if col not in cols_datos]
        df_datos   = df[cols_datos].copy()

        if cols_flags:
            logger.info(f"Columnas de flags excluidas del análisis: {cols_flags}")

        # Capa 1 — Normalización sobre datos del cliente únicamente
        df_datos, _ = normalize_nulls(df_datos)
        df_datos, _ = normalize_whitespace(df_datos)
        _, col_alias = normalize_columns(df_datos)

        for col_email in _detectar_cols_email(df_datos):
            df_datos, _ = normalize_emails(df_datos, col_email)

        # Capa 2 — Detección
        nulls        = check_nulls(df_datos)
        duplicates   = check_duplicates(df_datos)
        emails       = check_email(df_datos)
        phones       = check_phone(df_datos)
        dates        = check_dates(df_datos)
        multivalue   = check_multivalue(df_datos)
        case_issues  = check_case(df_datos)
        normal_forms = check_normal_forms(df_datos, multivalue)

        # Reconstruir df final: datos normalizados + flags originales preservados
        df_final = df_datos.copy()
        for col in cols_flags:
            df_final[col] = df[col].values

        return cls(
            total_filas     = len(df_final),
            total_columnas  = len(cols_datos),
            load_info       = load_info,
            col_alias       = col_alias,
            nulls           = nulls,
            duplicates      = duplicates,
            emails          = emails,
            phones          = phones,
            dates           = dates,
            multivalue      = multivalue,
            case_issues     = case_issues,
            normal_forms    = normal_forms,
            normalized_df   = df_final,
        )

    def severity_score(self) -> int:
        """
        Score de severidad 0-100.
        Pondera los problemas encontrados según su impacto en análisis.
        0 = datos limpios. 100 = datos inutilizables.
        """
        score = 0
        n     = max(self.total_filas, 1)

        # Duplicados por clave
        for _, info in self.duplicates.get("por_clave", {}).items():
            score += min(info["pct"] / 100 * _SEVERITY_WEIGHTS["duplicados_clave"], _SEVERITY_WEIGHTS["duplicados_clave"])

        # Nulos críticos
        for col, info in self.nulls.items():
            if info["severidad"] == "critical":
                score += 5
            elif info["severidad"] == "warning":
                score += 2

        # Emails rotos
        for col, info in self.emails.items():
            rotos = info["multi_at"] + info["dominio_roto"] + info["local_invalido"]
            pct   = rotos / max(info["total_revisados"], 1) * 100
            score += min(pct / 100 * _SEVERITY_WEIGHTS["email_roto"], _SEVERITY_WEIGHTS["email_roto"])

        # Teléfonos sin prefijo
        for col, info in self.phones.items():
            score += min(info["pct_sin_prefijo"] / 100 * _SEVERITY_WEIGHTS["phone_sin_prefijo"], _SEVERITY_WEIGHTS["phone_sin_prefijo"])

        # Violaciones 1FN
        if self.multivalue:
            score += min(len(self.multivalue) * 5, _SEVERITY_WEIGHTS["multivalue_1fn"])

        # Violaciones 2FN
        if self.normal_forms.get("2FN"):
            score += min(len(self.normal_forms["2FN"]) * 3, 15)

        return min(int(score), 100)

    def to_summary(self) -> str:
        """
        Resumen comprimido para el LLM (<200 tokens).
        Solo incluye lo que tiene problemas — no repite lo que está limpio.
        """
        partes = [f"CALIDAD DE DATOS ({self.total_filas} filas):"]
        score  = self.severity_score()
        nivel  = "CRÍTICO" if score >= 70 else "ALTO" if score >= 40 else "MEDIO" if score >= 20 else "BAJO"
        partes.append(f"Score: {score}/100 ({nivel})")

        # Duplicados
        for clave, info in self.duplicates.get("por_clave", {}).items():
            partes.append(f"· Duplicados por {clave}: {info['filas_afectadas']} filas ({info['pct']}%)")

        # Nulos
        nulos_crit = {c: i for c, i in self.nulls.items() if i["severidad"] in ("critical", "warning")}
        if nulos_crit:
            items = [f"{c}:{i['pct']}%" for c, i in list(nulos_crit.items())[:4]]
            partes.append(f"· Nulos: {', '.join(items)}")

        # Emails
        for col, info in self.emails.items():
            rotos = info["multi_at"] + info["dominio_roto"] + info["local_invalido"]
            if rotos > 0:
                partes.append(f"· Emails rotos ({col}): {rotos}")

        # Teléfonos
        for col, info in self.phones.items():
            if info["sin_prefijo_internacional"] > 0:
                partes.append(f"· Teléfonos sin prefijo: {info['sin_prefijo_internacional']}")

        # 1FN
        if self.multivalue:
            cols_1fn = list(self.multivalue.keys())
            partes.append(f"· Violación 1FN: {', '.join(cols_1fn)} (celdas multi-valor)")

        # 2FN
        if self.normal_forms.get("2FN"):
            partes.append(f"· Violación 2FN: {len(self.normal_forms['2FN'])} par(es) de columnas dependientes")

        # Stage nulos
        if "stage" in self.nulls or "stage " in self.nulls:
            col = "stage" if "stage" in self.nulls else "stage "
            partes.append(f"· Stage sin clasificar: {self.nulls[col]['nulos']} registros")

        return "\n".join(partes)

    def to_dict(self) -> dict:
        """Serializa el reporte completo a dict — para RespuestaAdly."""
        return {
            "total_filas":    self.total_filas,
            "total_columnas": self.total_columnas,
            "score":          self.severity_score(),
            "load_info":      self.load_info,
            "col_alias":      self.col_alias,
            "nulls":          self.nulls,
            "duplicates":     self.duplicates,
            "emails":         self.emails,
            "phones":         self.phones,
            "dates":          self.dates,
            "multivalue":     self.multivalue,
            "case_issues":    self.case_issues,
            "normal_forms":   self.normal_forms,
        }

    def __str__(self) -> str:
        return self.to_summary()


# ─────────────────────────────────────────────────────────────
# HELPERS — DETECCIÓN SEMÁNTICA DE COLUMNAS (agnóstica)
# Infiere el tipo de columna por nombre + muestra de valores.
# Nunca asume 'correo', 'telefono', 'stage' — detecta por patrón.
# ─────────────────────────────────────────────────────────────

def _detectar_cols_email(df: pd.DataFrame) -> list[str]:
    """
    Detecta columnas de email por:
    1. Nombre de columna contiene 'mail', 'email', 'correo', 'e-mail'
    2. Al menos 50% de valores no-nulos contienen '@'
    """
    candidatas = []
    for col in df.columns:
        nombre_ok = any(p in col.lower() for p in ["mail", "email", "correo", "e-mail"])
        if nombre_ok:
            candidatas.append(col)
            continue
        # Fallback por contenido
        vals = df[col].dropna().astype(str).head(50)
        if len(vals) > 0 and vals.str.contains("@").mean() > 0.5:
            candidatas.append(col)
    return candidatas


def _detectar_cols_phone(df: pd.DataFrame) -> list[str]:
    """
    Detecta columnas de teléfono por nombre o contenido.
    """
    candidatas = []
    for col in df.columns:
        nombre_ok = any(p in col.lower() for p in ["phone", "tel", "telefono", "celular", "móvil", "movil", "fono"])
        if nombre_ok:
            candidatas.append(col)
            continue
        # Fallback: valores mayormente numéricos con posible '+'
        vals = df[col].dropna().astype(str).str.strip().head(50)
        if len(vals) > 0:
            es_tel = vals.str.replace(r"[\s\+\-\(\)]", "", regex=True).str.isnumeric().mean()
            if es_tel > 0.7 and vals.str.len().mean() > 7:
                candidatas.append(col)
    return candidatas


def _detectar_cols_fecha(df: pd.DataFrame) -> list[str]:
    """
    Detecta columnas de fecha por nombre o parseabilidad.
    """
    candidatas = []
    patrones_nombre = ["fecha", "date", "ts", "timestamp", "created", "updated", "creacion", "registro"]
    for col in df.columns:
        nombre_ok = any(p in col.lower() for p in patrones_nombre)
        if nombre_ok:
            candidatas.append(col)
            continue
        # Fallback: intentar parsear sample
        vals = df[col].dropna().astype(str).head(20)
        if len(vals) >= 5:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    parsed = pd.to_datetime(vals, errors="coerce", format="mixed")
                except TypeError:
                    parsed = pd.to_datetime(vals, errors="coerce")
            if parsed.notna().mean() > 0.7:
                candidatas.append(col)
    return candidatas


def _dominio_roto(correo: str) -> bool:
    """True si el dominio no tiene punto (falta TLD)."""
    partes = correo.split("@")
    if len(partes) != 2:
        return False
    dom = partes[-1]  # último @ gana en caso de multi-@
    return "." not in dom or len(dom.split(".")[-1]) < 2


def _local_invalido_rfc5321(correo: str) -> bool:
    """True si la parte local del email tiene caracteres no permitidos por RFC 5321."""
    partes = correo.split("@")
    if len(partes) < 2:
        return True
    local = partes[0]
    # RFC 5321 parte local: letras, números y . _ % + - (sin tildes, sin espacios)
    return bool(re.search(r"[^a-zA-Z0-9._%+\-]", local))
