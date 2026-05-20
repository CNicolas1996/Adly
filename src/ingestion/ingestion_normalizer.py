"""
ingestion_normalizer.py
-----------------------
Corre ANTES de que cualquier df llegue al engine o al planner.
Adly asume siempre que los datos están sucios. Este módulo lo prueba.

Qué hace:
    LIMPIEZA BÁSICA
    1. Strip de nombres de columna (espacios trailing/leading)
    2. NONE/none/null como string → NaN real
    3. Detección de emails sospechosos (flag, no eliminación)
    4. Normalización de teléfonos (detecta faltantes de prefijo)
    5. Clasificación de duplicados (real vs journey del lead)
    6. Normalización de stages (inglés/español → vocab unificado)
    7. Titulación inconsistente — valores del mismo campo en distintos casos
    8. Llama a attribution_parser para explotar celdas con pipe

    ANÁLISIS DE CALIDAD ESTRUCTURAL (Formas Normales)
    1FN — Valores atómicos: detecta celdas con múltiples valores pegados
    2FN — Dependencias parciales: ad → adset inconsistente
    3FN — Entidades mezcladas: Contacto / Evento / Atribución en una tabla
    4FN — Dependencias multivaluadas: atribución primera y segunda son hechos independientes

Filosofía:
    - Nunca elimina datos. Siempre flaggea.
    - El usuario decide qué hacer — Adly solo informa.
    - Los problemas se explican en lenguaje de negocio, no técnico.
    - Funciona con cualquier schema, no solo el de Camí.

Uso:
    from src.processing.ingestion_normalizer import normalizar

    # Sin schema (backward compat — usa heurísticas de nombre)
    df_limpio, reporte = normalizar(df)

    # Con schema del SemanticInferencer (recomendado)
    df_limpio, reporte = normalizar(df, schema=semantic_schema)

    # Solo análisis estructural sin modificar el df:
    from src.processing.ingestion_normalizer import analizar_estructura
    reporte_fn = analizar_estructura(df)
"""

import pandas as pd
import numpy as np
import re

from typing import Tuple, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.processing.semantic_inferencer import SemanticSchema

try:
    from src.ingestion.attribution_parser import parsear_todas_atribuciones, reporte_atribucion
    _ATTRIBUTION_DISPONIBLE = True
except ImportError:
    try:
        from attribution_parser import parsear_todas_atribuciones, reporte_atribucion
        _ATTRIBUTION_DISPONIBLE = True
    except ImportError:
        _ATTRIBUTION_DISPONIBLE = False


# ---------------------------------------------------------------------------
# Vocabulario de stages — solo como fallback si no hay SemanticSchema
# ---------------------------------------------------------------------------

STAGE_MAP = {
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
    "cita agendada":    "Cita Agendada",
    "contactado":       "Contactado",
    "seguimiento":      "Seguimiento",
    "cerrado ganado":   "Cerrado Ganado",
    "cerrado perdido":  "Cerrado Perdido",
    "duplicado":        "Duplicado",
}

_NULOS_STRING = {"none", "null", "n/a", "na", "-", "nan", ""}


# ===========================================================================
# HELPER
# ===========================================================================

def _encontrar_col(df: pd.DataFrame, nombre: str) -> str | None:
    """Busca columna por nombre exacto (case-insensitive). Fallback cuando no hay schema."""
    nombre_limpio = nombre.strip().lower()
    for col in df.columns:
        if col.strip().lower() == nombre_limpio:
            return col
    return None


def _resolver_col(df: pd.DataFrame, schema_col: Optional[str], *fallback_nombres: str) -> Optional[str]:
    """
    Resuelve el nombre real de una columna en el df.

    Orden de prioridad:
      1. schema_col — columna detectada por SemanticInferencer (confiable)
      2. fallback_nombres — nombres hardcodeados como último recurso

    Args:
        df:              DataFrame con las columnas reales
        schema_col:      nombre detectado por SemanticInferencer (puede ser None)
        *fallback_nombres: nombres alternativos si el schema no detectó nada

    Returns:
        nombre de columna existente en df, o None si no se encuentra nada
    """
    # Primero: schema semántico
    if schema_col and schema_col in df.columns:
        return schema_col

    # Fallback: búsqueda por nombre hardcodeado (backward compat)
    for nombre in fallback_nombres:
        col = _encontrar_col(df, nombre)
        if col:
            return col

    return None


# ===========================================================================
# SECCIÓN 1 — LIMPIEZA BÁSICA
# ===========================================================================

def _limpiar_nombres_columnas(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip() for c in df.columns]
    return df


def _normalizar_nulos_string(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    total = 0
    for col in df.select_dtypes(include="object").columns:
        mask = df[col].str.strip().str.lower().isin(_NULOS_STRING)
        total += mask.sum()
        df.loc[mask, col] = np.nan
    return df, total


_EMAIL_VALIDO = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')

def _detectar_emails(df: pd.DataFrame, col_email: Optional[str] = None) -> Tuple[pd.DataFrame, int]:
    col = col_email or _encontrar_col(df, "correo") or _encontrar_col(df, "email")
    if col is None:
        return df, 0
    df[col] = df[col].str.strip()
    es_sospechoso = ~df[col].apply(
        lambda x: bool(_EMAIL_VALIDO.match(str(x))) if pd.notna(x) else False
    )
    df["email_sospechoso"] = es_sospechoso
    return df, int(es_sospechoso.sum())


def _detectar_telefonos(df: pd.DataFrame, col_phone: Optional[str] = None) -> Tuple[pd.DataFrame, int]:
    col = col_phone or _encontrar_col(df, "telefono") or _encontrar_col(df, "phone")
    if col is None:
        return df, 0
    df[col] = df[col].str.strip()
    sin_prefijo = df[col].apply(
        lambda x: not str(x).startswith("+") if pd.notna(x) else False
    )
    df["telefono_sin_prefijo"] = sin_prefijo
    return df, int(sin_prefijo.sum())


def _clasificar_duplicados(
    df: pd.DataFrame,
    col_nombre: Optional[str] = None,
    col_correo: Optional[str] = None,
    col_stage: Optional[str] = None,
) -> Tuple[pd.DataFrame, int, int]:
    """
    Clasifica duplicados como 'real' (mismo contacto dos veces) o 'journey' (avanzó en funnel).

    Cuando recibe columnas del SemanticSchema, no depende de nombres hardcodeados.
    """
    nombre_col = col_nombre or _encontrar_col(df, "nombre") or _encontrar_col(df, "name")
    correo_col = col_correo or _encontrar_col(df, "correo") or _encontrar_col(df, "email")
    stage_col  = col_stage  or _encontrar_col(df, "stage") or _encontrar_col(df, "estado")

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
            # Detectar duplicados reales por vocabulario canónico + variantes
            es_duplicado = any(
                s in {"duplicado", "duplicate", "dup", "repetido", "repeated"}
                for s in stages
            )
            if es_duplicado:
                df.loc[grupo.index, "tipo_duplicado"] = "real"
                reales += len(grupo)
            else:
                df.loc[grupo.index, "tipo_duplicado"] = "journey"
                journeys += len(grupo)

    return df, reales, journeys


def _normalizar_stages(
    df: pd.DataFrame,
    col_stage: Optional[str] = None,
    value_map: Optional[dict] = None,
) -> Tuple[pd.DataFrame, int]:
    """
    Normaliza stages al vocabulario canónico.

    Si recibe value_map del SemanticInferencer → lo usa (agnóstico real).
    Si no → cae al STAGE_MAP hardcodeado (backward compat).
    """
    col = col_stage or _encontrar_col(df, "stage") or _encontrar_col(df, "estado")
    if col is None:
        return df, 0

    if value_map:
        # Ruta semántica: mapeo exacto cliente → canónico, sin hardcodeo
        def _mapear_semantico(val):
            if pd.isna(val):
                return val
            val_str = str(val).strip()
            return value_map.get(val_str, val_str)

        original = df[col].copy()
        df[col] = df[col].apply(_mapear_semantico)
        return df, int((df[col] != original).sum())
    else:
        # Ruta fallback: STAGE_MAP hardcodeado
        def _mapear(val):
            if pd.isna(val):
                return val
            clave = str(val).strip().lower()
            return STAGE_MAP.get(clave, str(val).strip())

        original = df[col].copy()
        df[col] = df[col].apply(_mapear)
        return df, int((df[col] != original).sum())


def _normalizar_titulacion(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    """
    Detecta y corrige inconsistencias de capitalización.
    Si >60% de los valores son Title Case → normaliza a Title Case.
    Si >60% son UPPER → normaliza a UPPER.
    Si no hay mayoría clara → reporta sin cambiar.
    No toca columnas de email, teléfono, fecha o ID.
    """
    resultado = {}
    _EXCLUIR = {"correo", "telefono", "fecha", "email", "id", "url"}

    for col in df.select_dtypes(include="object").columns:
        if any(ex in col.lower() for ex in _EXCLUIR):
            continue

        vals = df[col].dropna().astype(str)
        if len(vals) == 0:
            continue

        n_total  = len(vals)
        n_title  = (vals == vals.str.title()).sum()
        n_upper  = (vals == vals.str.upper()).sum()
        n_lower  = (vals == vals.str.lower()).sum()
        n_mezcla = n_total - n_title - n_upper - n_lower

        hay_inconsistencia = (
            n_mezcla > 0 or
            (n_title > 0 and n_upper > 0 and min(n_title, n_upper) / n_total > 0.1)
        )
        if not hay_inconsistencia:
            continue

        pct_title = n_title / n_total
        pct_upper = n_upper / n_total

        if pct_title >= 0.6:
            df[col] = df[col].apply(lambda x: str(x).strip().title() if pd.notna(x) else x)
            resultado[col] = {
                "accion": "normalizado_title_case",
                "corregidos": int(n_mezcla + n_upper + n_lower),
                "mensaje": (
                    f"'{col}' tenía {n_mezcla} valores con capitalización mezclada "
                    f"(ej: 'reel ia', 'REEL IA'). "
                    f"Adly los unificó — el análisis ya no los cuenta como anuncios distintos."
                ),
            }
        elif pct_upper >= 0.6:
            df[col] = df[col].apply(lambda x: str(x).strip().upper() if pd.notna(x) else x)
            resultado[col] = {
                "accion": "normalizado_upper",
                "corregidos": int(n_mezcla + n_title + n_lower),
                "mensaje": (
                    f"'{col}' tenía capitalización inconsistente. "
                    f"Adly lo unificó en mayúsculas."
                ),
            }
        else:
            resultado[col] = {
                "accion": "reportado_sin_cambio",
                "corregidos": 0,
                "mensaje": (
                    f"'{col}' mezcla MAYÚSCULAS, minúsculas y Title Case sin mayoría clara. "
                    f"Revisa si 'Reel IA' y 'REEL IA' son el mismo anuncio o dos distintos — "
                    f"Adly no los tocó para no cometer un error."
                ),
            }

    return df, resultado


# ===========================================================================
# SECCIÓN 2 — ANÁLISIS DE FORMAS NORMALES
# ===========================================================================

def _analizar_1fn(df: pd.DataFrame) -> list[dict]:
    """
    1FN: cada celda debe tener un solo valor atómico.
    Detecta columnas con múltiples valores pegados (pipe, punto y coma).
    """
    hallazgos = []
    for col in df.select_dtypes(include="object").columns:
        mask = df[col].dropna().astype(str).str.contains(r'[|;]', regex=True)
        n = mask.sum()
        if n > 0:
            ejemplo = df[col].dropna()[mask].iloc[0]
            pct = round(n / len(df) * 100, 1)
            hallazgos.append({
                "forma": "1FN",
                "columna": col,
                "n": n,
                "pct": pct,
                "ejemplo": str(ejemplo),
                "severidad": "alta",
                "problema": (
                    f"'{col}' tiene {n} celdas ({pct}%) con múltiples valores en una sola celda. "
                    f"Ejemplo: \"{ejemplo}\". "
                    f"Esto impide saber exactamente qué campaña o anuncio generó ese lead."
                ),
                "sugerencia": (
                    f"Separar '{col}' en columnas: campaña, adset, anuncio. "
                    f"Adly hace esto automáticamente al cargar los datos."
                ),
            })
    return hallazgos


def _analizar_2fn(df: pd.DataFrame, schema=None) -> list[dict]:
    """
    2FN: cada atributo no clave debe depender de TODA la clave.
    Si el mismo nombre de anuncio aparece en múltiples adsets → dependencia parcial.

    Usa columnas del schema si están disponibles, fallback a nombres hardcodeados.
    """
    hallazgos = []

    # Construir pares desde schema semántico si existe
    if schema and schema.col_ad and schema.col_adset:
        pares_schema = [(schema.col_ad, schema.col_adset)]
    else:
        pares_schema = []

    # Pares hardcodeados como fallback
    pares_fallback = [
        ("ad primera atribucion",  "ad set primera atribucion"),
        ("ad segunda atribucion",  "ad set segunda atribucion"),
        ("primera_ad_attr",        "primera_adset_attr"),
        ("segunda_ad_attr",        "segunda_adset_attr"),
    ]

    pares_a_evaluar = pares_schema if pares_schema else [
        (c_det, c_dep)
        for c_det, c_dep in pares_fallback
        if _encontrar_col(df, c_det) and _encontrar_col(df, c_dep)
    ]

    for c_det, c_dep in pares_a_evaluar:
        # Resolver nombre real en df
        col_det = c_det if c_det in df.columns else _encontrar_col(df, c_det)
        col_dep = c_dep if c_dep in df.columns else _encontrar_col(df, c_dep)
        if col_det is None or col_dep is None:
            continue

        sub = df[[col_det, col_dep]].dropna()
        if len(sub) == 0:
            continue

        mapping        = sub.groupby(col_det)[col_dep].nunique()
        inconsistentes = mapping[mapping > 1]

        if len(inconsistentes) > 0:
            pct = round(len(inconsistentes) / len(mapping) * 100, 1)
            ejemplo_ad = inconsistentes.index[0]
            adsets = sub[sub[col_det] == ejemplo_ad][col_dep].unique()[:3].tolist()
            hallazgos.append({
                "forma": "2FN",
                "columna": f"{col_det} → {col_dep}",
                "n": int(len(inconsistentes)),
                "pct": pct,
                "severidad": "media",
                "problema": (
                    f"{len(inconsistentes)} anuncios ({pct}%) aparecen asociados a más de un adset. "
                    f"Por ejemplo, '{ejemplo_ad}' aparece en: {adsets}. "
                    f"Esto puede inflar o distorsionar métricas por adset."
                ),
                "sugerencia": (
                    f"Si el mismo creativo se usó en varios adsets, debería tener nombres distintos "
                    f"(ej: 'Reel_IA_BroadUSA' vs 'Reel_IA_Retargeting'). "
                    f"Así cada anuncio tiene identidad única."
                ),
            })

    return hallazgos


def _analizar_3fn(df: pd.DataFrame, schema=None) -> list[dict]:
    """
    3FN: ningún atributo no clave debe depender transitivamente de la clave.
    Detecta entidades mezcladas y inconsistencias de identidad del contacto.

    Usa columnas del schema si están disponibles.
    """
    hallazgos = []

    entidades = {
        "Contacto":   ["nombre", "correo", "telefono"],
        "Evento":     ["fecha", "stage", "estado"],
        "Atribución": ["ad", "adset", "campaña", "campaign", "atribucion"],
    }

    entidades_presentes = {
        ent: [c for c in df.columns if any(p in c.lower() for p in palabras)]
        for ent, palabras in entidades.items()
    }
    entidades_presentes = {k: v for k, v in entidades_presentes.items() if v}

    if len(entidades_presentes) >= 2:
        correo_col = (schema.col_email if schema else None) or _encontrar_col(df, "correo") or _encontrar_col(df, "email")
        stage_col  = (schema.col_estado if schema else None) or _encontrar_col(df, "stage") or _encontrar_col(df, "estado")

        if correo_col and stage_col and correo_col in df.columns and stage_col in df.columns:
            correo_stages = df.groupby(correo_col)[stage_col].nunique()
            multi = correo_stages[correo_stages > 1]
            if len(multi) > 0:
                hallazgos.append({
                    "forma": "3FN",
                    "columna": "tabla completa",
                    "n": len(entidades_presentes),
                    "pct": None,
                    "severidad": "informativa",
                    "problema": (
                        f"Esta tabla mezcla {len(entidades_presentes)} tipos de información: "
                        f"{', '.join(entidades_presentes.keys())}. "
                        f"{len(multi)} contactos tienen stages distintos en filas diferentes, "
                        f"confirmando que 'stage' es del evento, no del contacto."
                    ),
                    "sugerencia": (
                        f"Para análisis en Sheets esto funciona. "
                        f"Antes de migrar a base de datos real, separar en: "
                        f"tabla Contactos, tabla Eventos, tabla Atribuciones."
                    ),
                })

    correo_col = (schema.col_email if schema else None) or _encontrar_col(df, "correo") or _encontrar_col(df, "email")
    nombre_col = (schema.col_name  if schema else None) or _encontrar_col(df, "nombre") or _encontrar_col(df, "name")

    if correo_col and nombre_col and correo_col in df.columns and nombre_col in df.columns:
        multi_nombres = df.groupby(correo_col)[nombre_col].nunique()
        multi_nombres = multi_nombres[multi_nombres > 1]
        if len(multi_nombres) > 0:
            pct = round(len(multi_nombres) / df[correo_col].nunique() * 100, 1)
            hallazgos.append({
                "forma": "3FN",
                "columna": f"{correo_col} → {nombre_col}",
                "n": int(len(multi_nombres)),
                "pct": pct,
                "severidad": "alta",
                "problema": (
                    f"{len(multi_nombres)} correos ({pct}%) están asociados a más de un nombre. "
                    f"Puede ser error de captura o la misma persona con nombre escrito distinto."
                ),
                "sugerencia": (
                    f"Revisar estos contactos. El correo debería identificar unívocamente a una persona."
                ),
            })

    return hallazgos


def _analizar_4fn(df: pd.DataFrame, schema=None) -> list[dict]:
    """
    4FN: no debe haber dependencias multivaluadas independientes en la misma tabla.
    Primera y segunda atribución son hechos independientes.

    Usa attribution_columns del schema si están disponibles.
    """
    hallazgos = []

    # Si el schema detectó columnas de atribución semánticamente, usarlas
    if schema and schema.attribution_columns and len(schema.attribution_columns) >= 2:
        col_primera = schema.attribution_columns[0] if schema.attribution_columns[0] in df.columns else None
        col_segunda = schema.attribution_columns[1] if len(schema.attribution_columns) > 1 and schema.attribution_columns[1] in df.columns else None
    else:
        col_primera = _encontrar_col(df, "ad primera atribucion")
        col_segunda = _encontrar_col(df, "ad segunda atribucion")

    if col_primera is None or col_segunda is None:
        return hallazgos

    ambas   = df[[col_primera, col_segunda]].dropna()
    n_ambas = len(ambas)

    if n_ambas > 0:
        pct = round(n_ambas / len(df) * 100, 1)
        hallazgos.append({
            "forma": "4FN",
            "columna": f"{col_primera} + {col_segunda}",
            "n": n_ambas,
            "pct": pct,
            "severidad": "informativa",
            "problema": (
                f"{n_ambas} leads ({pct}%) tienen dos atribuciones en columnas separadas. "
                f"Primera y segunda atribución son hechos independientes del mismo lead — "
                f"no tienen relación entre sí y no deberían estar en la misma fila."
            ),
            "sugerencia": (
                f"En una base ideal, cada atribución sería una fila en una tabla Atribuciones "
                f"(lead_id, orden, anuncio). "
                f"Adly maneja esto expandiendo ambas columnas automáticamente."
            ),
        })

    return hallazgos


def analizar_estructura(df: pd.DataFrame, schema=None) -> dict:
    """
    Análisis completo de formas normales 1FN→4FN sin modificar el df.
    Retorna dict con hallazgos por forma + resumen ejecutivo en lenguaje de negocio.

    Args:
        df:     DataFrame ya con columnas stripeadas
        schema: SemanticSchema opcional — mejora detección en 2FN, 3FN, 4FN
    """
    df = df.copy()
    df = _limpiar_nombres_columnas(df)

    h1 = _analizar_1fn(df)
    h2 = _analizar_2fn(df, schema=schema)
    h3 = _analizar_3fn(df, schema=schema)
    h4 = _analizar_4fn(df, schema=schema)

    todos        = h1 + h2 + h3 + h4
    altas        = [h for h in todos if h["severidad"] == "alta"]
    medias       = [h for h in todos if h["severidad"] == "media"]
    informativas = [h for h in todos if h["severidad"] == "informativa"]

    if not todos:
        resumen = "✅ La estructura de los datos se ve bien. No se detectaron violaciones de normalización."
    else:
        partes = []
        if altas:
            partes.append(f"{len(altas)} problema(s) que afectan la precisión del análisis")
        if medias:
            partes.append(f"{len(medias)} inconsistencia(s) que pueden distorsionar métricas")
        if informativas:
            partes.append(f"{len(informativas)} punto(s) a tener en cuenta para cuando escales")
        resumen = (
            f"⚠️ Se encontraron: {' · '.join(partes)}. "
            f"Adly puede trabajar con estos datos, pero el análisis será más preciso si los corriges."
        )

    return {
        "total_hallazgos": len(todos),
        "por_forma": {"1FN": h1, "2FN": h2, "3FN": h3, "4FN": h4},
        "por_severidad": {"alta": altas, "media": medias, "informativa": informativas},
        "resumen": resumen,
        "problemas_negocio": [h["problema"] for h in altas + medias],
        "sugerencias":       [h["sugerencia"] for h in altas + medias],
    }


# ===========================================================================
# SECCIÓN 3 — FUNCIÓN PRINCIPAL
# ===========================================================================

def normalizar(df: pd.DataFrame, schema=None) -> Tuple[pd.DataFrame, dict]:
    """
    Pipeline completo: limpieza básica + análisis estructural 1FN→4FN.

    Args:
        df:     DataFrame crudo del cliente
        schema: SemanticSchema del SemanticInferencer (opcional pero recomendado).
                Cuando está presente, los helpers usan columnas detectadas semánticamente
                en lugar de nombres hardcodeados. Backward compatible: funciona sin schema.

    Returns:
        (df_normalizado, reporte)
        reporte contiene problemas, info, análisis de formas normales
        y todos los mensajes en lenguaje natural listos para mostrar al usuario.
    """
    df = df.copy()
    reporte = {
        "total_filas": len(df),
        "problemas":   [],
        "info":        [],
        "estructura":  {},
    }

    df = _limpiar_nombres_columnas(df)

    df, n_nulos = _normalizar_nulos_string(df)
    if n_nulos > 0:
        reporte["problemas"].append(
            f"{n_nulos} celdas tenían 'NONE' o 'null' escrito como texto — "
            f"Adly los convirtió a vacíos reales."
        )

    # Usar columnas del schema cuando están disponibles
    col_email = schema.col_email if schema else None
    col_phone = schema.col_phone if schema else None
    col_name  = schema.col_name  if schema else None
    col_estado = schema.col_estado if schema else None
    value_map  = schema.value_map_stages if schema else None

    df, n_emails = _detectar_emails(df, col_email=col_email)
    if n_emails > 0:
        reporte["problemas"].append(
            f"{n_emails} correos tienen caracteres inválidos (tildes, espacios, @ doble). "
            f"Pueden fallar si intentas enviarles un email — revísalos antes de una campaña."
        )

    df, n_tel = _detectar_telefonos(df, col_phone=col_phone)
    if n_tel > 0:
        reporte["problemas"].append(
            f"{n_tel} teléfonos no tienen código de país (+1, +52, etc.). "
            f"Sin esto no puedes saber de qué país es el lead ni hacer llamadas internacionales."
        )

    df, n_reales, n_journeys = _clasificar_duplicados(
        df,
        col_nombre=col_name,
        col_correo=col_email,
        col_stage=col_estado,
    )
    if n_reales > 0:
        reporte["problemas"].append(
            f"{n_reales} leads están marcados como duplicados reales — "
            f"son el mismo contacto registrado dos veces por error."
        )
    if n_journeys > 0:
        reporte["info"].append(
            f"{n_journeys} leads aparecen varias veces porque avanzaron por el funnel. Eso es normal."
        )

    df, n_stages = _normalizar_stages(df, col_stage=col_estado, value_map=value_map)
    if n_stages > 0:
        reporte["info"].append(
            f"{n_stages} stages unificados al vocabulario canónico de Adly."
        )

    df, variantes = _unificar_variantes_categoricas(df)
    for col, info in variantes.items():
        reporte["info"].append(info["mensaje"])

    df, titulacion = _normalizar_titulacion(df)
    for col, info in titulacion.items():
        if info["accion"] in ("normalizado_title_case", "normalizado_upper"):
            reporte["info"].append(info["mensaje"])
        elif info["accion"] == "reportado_sin_cambio":
            reporte["problemas"].append(info["mensaje"])

    if _ATTRIBUTION_DISPONIBLE:
        df = parsear_todas_atribuciones(df)
        rep_attr = reporte_atribucion(df)
        reporte["problemas"].extend(rep_attr.get("problemas", []))
    else:
        reporte["info"].append(
            "attribution_parser no disponible — columnas de atribución no fueron expandidas."
        )

    # Análisis estructural — pasa el schema para que 2FN/3FN/4FN usen columnas detectadas
    reporte["estructura"] = analizar_estructura(df, schema=schema)
    reporte["problemas"].extend(reporte["estructura"]["problemas_negocio"])

    total_problemas = len(reporte["problemas"])
    if total_problemas == 0:
        reporte["resumen"] = "✅ Los datos se ven limpios. No se encontraron problemas."
    else:
        reporte["resumen"] = (
            f"⚠️ {total_problemas} tipos de problemas detectados. "
            f"Adly los manejó donde pudo — algunos requieren tu atención."
        )

    return df, reporte


# ===========================================================================
# SECCIÓN 4 — UTILIDADES
# ===========================================================================

def diagnostico_rapido(df: pd.DataFrame, schema=None) -> str:
    """Reporte compacto para CLI/chat. No modifica el df."""
    _, reporte = normalizar(df, schema=schema)
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

    estructura = reporte.get("estructura", {})
    if estructura.get("sugerencias"):
        lineas.append("")
        lineas.append("💡 Sugerencias para cuando escales:")
        for s in estructura["sugerencias"]:
            lineas.append(f"   • {s}")

    return "\n".join(lineas)


# ===========================================================================
# SECCIÓN 5 — UNIFICACIÓN DE VARIANTES CATEGÓRICAS
# ===========================================================================

def _normalizar_clave(valor: str) -> str:
    """
    Convierte cualquier string a su forma canónica de comparación.
    Regla: lowercase + strip + reemplazar [_, -, .] por espacio + colapsar espacios múltiples.

    Ejemplos:
        "Reel_IA"   → "reel ia"
        "REEL IA"   → "reel ia"
        "reel-ia"   → "reel ia"
        "Reel  IA"  → "reel ia"
    """
    s = str(valor).strip().lower()
    s = re.sub(r"[_\-\.]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _unificar_variantes_categoricas(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    """
    Unifica variantes del mismo valor categórico en todas las columnas object.
    Sin hardcodeo — aplica la misma regla agnóstica a cualquier columna.

    Lógica:
        1. Para cada columna object, calcular la clave canónica de cada valor
        2. Agrupar valores que colapsan a la misma clave
        3. El canónico es el valor más frecuente del grupo
        4. Reemplazar todas las variantes por el canónico

    Ejemplos que resuelve:
        "Reel IA", "reel ia", "Reel_IA"  → el más frecuente (ej: "Reel IA")
        "WEBINAR IA 2026", "webinar ia 2026" → "WEBINAR IA 2026" (si es más frecuente)
        "Closed Won", "closed_won", "CLOSED WON" → el más frecuente

    No toca:
        - Columnas de email (tienen formato propio)
        - Columnas de fecha
        - Columnas con todos los valores únicos (IDs)
        - Valores NaN
    """
    resultado = {}
    _EXCLUIR = {"correo", "email", "fecha", "date", "created", "id", "url", "phone", "telefono"}

    for col in df.select_dtypes(include="object").columns:
        # Saltar columnas que no deben tocarse
        if any(ex in col.lower() for ex in _EXCLUIR):
            continue

        vals = df[col].dropna()
        if len(vals) == 0:
            continue

        # No tocar columnas donde casi todos los valores son únicos (IDs o texto libre)
        n_unicos = vals.nunique()
        if n_unicos / len(vals) > 0.95:
            continue

        # Construir mapa: clave_canónica → {valor_original: frecuencia}
        grupos: dict = {}
        for val in vals:
            clave = _normalizar_clave(val)
            if clave not in grupos:
                grupos[clave] = {}
            grupos[clave][val] = grupos[clave].get(val, 0) + 1

        # Solo procesar grupos que tienen más de una variante
        grupos_con_variantes = {
            clave: conteo
            for clave, conteo in grupos.items()
            if len(conteo) > 1
        }

        if not grupos_con_variantes:
            continue

        # Construir mapa de reemplazo: variante → canónico (el más frecuente)
        mapa_reemplazo = {}
        ejemplos = []
        for clave, conteo in grupos_con_variantes.items():
            canonico = max(conteo, key=conteo.get)
            variantes = [v for v in conteo if v != canonico]
            for variante in variantes:
                mapa_reemplazo[variante] = canonico
            if len(ejemplos) < 3:
                ejemplos.append(f"'{variantes[0]}' → '{canonico}'")

        # Aplicar reemplazos
        n_reemplazos = df[col].isin(mapa_reemplazo).sum()
        df[col] = df[col].map(lambda x: mapa_reemplazo.get(x, x) if pd.notna(x) else x)

        resultado[col] = {
            "n_grupos": len(grupos_con_variantes),
            "n_reemplazos": int(n_reemplazos),
            "mensaje": (
                f"'{col}' tenía {len(grupos_con_variantes)} valores con variantes "
                f"(mayúsculas, guiones, underscores). "
                f"Adly unificó {n_reemplazos} registros al valor más frecuente. "
                f"Ej: {' · '.join(ejemplos)}"
            ),
        }

    return df, resultado
