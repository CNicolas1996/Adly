# query_engine.py — Adly · Data-Buddy
# Interceptor analítico — pandas antes del LLM
# Compartido entre CLI y Web (chat.py)
#
# Lógica:
#   1. Detecta intent en lenguaje natural (conteo, agrupación, ranking, comparación)
#   2. Ejecuta pandas con el DataFrame real
#   3. Retorna resultado + advertencias de calidad de datos
#   4. El LLM interpreta el resultado — nunca adivina
#
# Agregar nuevo intent = agregar keywords en la sección correspondiente

import pandas as pd


# ─────────────────────────────────────────
# MAPEO DE COLUMNAS
# Palabras clave → columnas reales del df
# ─────────────────────────────────────────

COL_MAP = {
    "adset":    "adset",
    "campaña":  "campana",
    "campana":  "campana",
    "ad":       "ad",
    "estado":   "estado",
}

# Estados válidos del embudo — para filtros semánticos
ESTADOS_VALIDOS = {"lead", "mql", "sql", "venta", "perdido"}

# Mapeo semántico: palabra en pregunta → valor real en df["estado"]
ESTADO_MAP = {
    "lead":    "lead",
    "leads":   "lead",
    "mql":     "mql",
    "sql":     "sql",
    "venta":   "venta",
    "ventas":  "venta",
    "perdido": "perdido",
    "perdidos":"perdido",
}


# ─────────────────────────────────────────
# ADVERTENCIAS DE CALIDAD
# ─────────────────────────────────────────

def _advertencias_calidad(df: pd.DataFrame, col: str, valor=None) -> list[str]:
    """
    Detecta problemas de calidad en la columna consultada.
    Retorna lista de strings para inyectar en el contexto del LLM.
    """
    advertencias = []

    if col not in df.columns:
        return [f"ADVERTENCIA: columna '{col}' no existe en el dataset."]

    n_nulos = df[col].isna().sum()
    if n_nulos > 0:
        advertencias.append(
            f"CALIDAD: '{col}' tiene {n_nulos} valores nulos "
            f"({n_nulos/len(df)*100:.1f}%) — excluidos del análisis."
        )

    valores = df[col].dropna().unique()
    if valor:
        similares = [v for v in valores if str(valor).lower() in str(v).lower() and v != valor]
        if similares:
            advertencias.append(
                f"CALIDAD: Variantes de '{valor}' encontradas: {similares} "
                f"— pueden ser el mismo grupo con typos."
            )
    else:
        normalizados = [
            str(v).lower().replace("_", "").replace("-", "").replace(" ", "")
            for v in valores
        ]
        if len(normalizados) != len(set(normalizados)):
            advertencias.append(
                f"CALIDAD: '{col}' tiene posibles duplicados con distinto formato "
                f"(espacios, guiones, mayúsculas)."
            )

    return advertencias


# ─────────────────────────────────────────
# DETECCIÓN DE COLUMNA Y VALOR
# ─────────────────────────────────────────

def _detectar_columna(p: str, df: pd.DataFrame) -> str | None:
    """Detecta la columna principal de agrupación en la pregunta."""
    for keyword, col in COL_MAP.items():
        if keyword in p and col in df.columns:
            return col
    return None


def _detectar_estado_filtro(p: str) -> str | None:
    """
    Detecta si la pregunta pide filtrar por un estado del embudo.
    Ej: 'cuántos leads tiene el adset 35' → filtra estado=lead
    """
    for palabra, estado in ESTADO_MAP.items():
        if palabra in p:
            return estado
    return None


def _detectar_valor_en_columna(p: str, df: pd.DataFrame, col: str) -> str | None:
    """
    Busca un valor específico de la columna mencionado en la pregunta.
    Match fuzzy: 'adset 35' encuentra 'Adset_35-50'
    """
    valores_unicos = df[col].dropna().unique()
    for val in valores_unicos:
        val_str = str(val).lower()
        for palabra in p.split():
            if len(palabra) > 3 and palabra in val_str:
                return val
    return None


# ─────────────────────────────────────────
# ENGINE PRINCIPAL
# ─────────────────────────────────────────

def ejecutar_query_analitica(pregunta: str, df: pd.DataFrame) -> str | None:
    """
    Detecta intent analítico en lenguaje natural y ejecuta pandas.

    Retorna string con resultado + advertencias de calidad para inyectar
    como contexto al LLM. Retorna None si no detecta intent analítico claro.

    Intents soportados:
      - conteo       → "cuántos leads tiene el adset 35"
      - agrupación   → "agrúpame por adset"
      - ranking      → "el ad más vendedor"
      - comparación  → "compara adset 18 vs adset 35"
    """
    p = pregunta.lower().strip()
    resultado = []

    col_detectada = _detectar_columna(p, df)
    if col_detectada is None:
        return None

    estado_filtro = _detectar_estado_filtro(p)
    valor_detectado = _detectar_valor_en_columna(p, df, col_detectada)
    col_id = "ghl_id" if "ghl_id" in df.columns else df.columns[0]

    # ── FIX #1: CONTEO con filtro de estado opcional ──────────
    # "cuántos leads tiene el adset 35" → filtra adset=X AND estado=lead
    # "cuántos registros tiene el adset 35" → solo filtra adset=X
    CONTEO = ["cuántos", "cuantos", "cuenta", "cuéntalo", "cuentalo", "total", "número", "numero"]
    if any(k in p for k in CONTEO) and valor_detectado:
        subset = df[df[col_detectada] == valor_detectado]
        advertencias = _advertencias_calidad(df, col_detectada, valor_detectado)

        if estado_filtro and "estado" in df.columns:
            # Pregunta mixta: columna + estado
            subset_estado = subset[subset["estado"] == estado_filtro]
            n_total = len(subset)
            n_estado = len(subset_estado)
            resultado.append(
                f"RESULTADO EXACTO (pandas): "
                f"'{valor_detectado}' → total registros: {n_total} | "
                f"estado='{estado_filtro}': {n_estado} "
                f"({n_estado/n_total*100:.1f}% del grupo)"
            )
        else:
            # Conteo simple
            resultado.append(
                f"RESULTADO EXACTO (pandas): "
                f"'{valor_detectado}' en '{col_detectada}' = {len(subset)} registros."
            )

        resultado += advertencias
        return "\n".join(resultado)

    # ── AGRUPACIÓN ────────────────────────────────────────────
    # "agrúpame por adset" → total + ventas + tasa por grupo
    AGRUPACION = ["agrupa", "agrupar", "desglos", "por cada", "resumen por",
                  "total de cada", "cuántos hay", "cuantos hay", "muestra"]
    if any(k in p for k in AGRUPACION) or ("por" in p and col_detectada):
        if "estado" in df.columns:
            # Si hay filtro de estado, agrupa dentro de ese estado
            if estado_filtro:
                df_filtrado = df[df["estado"] == estado_filtro]
                grupos = df_filtrado.groupby(col_detectada).size().reset_index(name=estado_filtro)
                resultado.append(
                    f"RESULTADO EXACTO (pandas) — "
                    f"conteo de '{estado_filtro}' por '{col_detectada}':"
                )
            else:
                grupos = df.groupby(col_detectada).agg(
                    total=(col_id, "count"),
                    ventas=("estado", lambda x: (x == "venta").sum()),
                    leads=("estado", lambda x: (x == "lead").sum()),
                    mql=("estado", lambda x: (x == "mql").sum()),
                ).reset_index()
                grupos["tasa_venta_%"] = (grupos["ventas"] / grupos["total"] * 100).round(1)
                resultado.append(
                    f"RESULTADO EXACTO (pandas) — agrupación completa por '{col_detectada}':"
                )
        else:
            grupos = df.groupby(col_detectada).size().reset_index(name="total")
            resultado.append(f"RESULTADO EXACTO (pandas) — agrupación por '{col_detectada}':")

        resultado.append(grupos.to_string(index=False))
        resultado += _advertencias_calidad(df, col_detectada)
        return "\n".join(resultado)

    # ── RANKING ───────────────────────────────────────────────
    # "el ad más vendedor" → ranking por ventas con volumen y tasa
    RANKING = ["mejor", "peor", "más vendedor", "mas vendedor", "mayor", "menor",
               "top", "más eficiente", "mas eficiente", "más rentable", "mas rentable",
               "más convierte", "mas convierte"]
    if any(k in p for k in RANKING) and col_detectada:
        if "estado" in df.columns:
            ventas = (
                df[df["estado"] == "venta"]
                .groupby(col_detectada)
                .size()
                .reset_index(name="ventas")
            )
            totales = df.groupby(col_detectada).size().reset_index(name="total")
            ranking = ventas.merge(totales, on=col_detectada)
            ranking["tasa_venta_%"] = (ranking["ventas"] / ranking["total"] * 100).round(1)
            ranking = ranking.sort_values("ventas", ascending=False)

            resultado.append(
                f"RESULTADO EXACTO (pandas) — ranking por ventas en '{col_detectada}':"
            )
            resultado.append(ranking.to_string(index=False))
            resultado.append(
                "NOTA ANALÍTICA: Volumen Y tasa son distintas métricas. "
                "Tasa alta con volumen bajo puede ser estadísticamente engañoso."
            )
            resultado += _advertencias_calidad(df, col_detectada)
            return "\n".join(resultado)

    # ── COMPARACIÓN ───────────────────────────────────────────
    # "compara adset 18 vs adset 35"
    COMPARACION = ["vs", "versus", "compara", "diferencia entre", "contra"]
    if any(k in p for k in COMPARACION) and col_detectada and "estado" in df.columns:
        grupos = df.groupby(col_detectada).agg(
            total=(col_id, "count"),
            ventas=("estado", lambda x: (x == "venta").sum()),
            leads=("estado", lambda x: (x == "lead").sum()),
        ).reset_index()
        grupos["tasa_venta_%"] = (grupos["ventas"] / grupos["total"] * 100).round(1)

        resultado.append(
            f"RESULTADO EXACTO (pandas) — comparación por '{col_detectada}':"
        )
        resultado.append(grupos.to_string(index=False))
        resultado += _advertencias_calidad(df, col_detectada)
        return "\n".join(resultado)

    return None
