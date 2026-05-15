# command_bridge.py — Adly · Data-Buddy
# Wrappers de comandos CLI para la Web UI.
# NO tocan commands.py. Reimplementan la lógica como funciones puras
# que retornan markdown/texto plano en vez de printear con Rich.

import pandas as pd
from datetime import datetime
import unicodedata
import re
from rapidfuzz import fuzz


# ── Helpers internos ─────────────────────────────────────────────────────────

_PATRONES_ID = {"id", "telefono", "phone", "tel", "cel", "celular", "codigo", "code", "zip", "cp"}
_TIPOS_SEMANTICOS = {
    "id":        ["id", "ghl_id", "lead_id", "record_id", "uid"],
    "telefono":  ["telefono", "phone", "tel", "cel", "celular", "mobile"],
    "email":     ["email", "correo", "mail"],
    "fecha":     ["fecha", "date", "ts", "timestamp", "creacion", "cierre", "update"],
    "nombre":    ["nombre", "name", "apellido"],
    "moneda":    ["costo", "valor", "precio", "ingreso", "revenue", "spend", "cost", "cpl", "cpa"],
    "tasa":      ["tasa", "rate", "ratio", "roas", "icl", "ctr"],
    "categoria": ["estado", "status", "campana", "campaign", "adset", "ad", "fuente", "source"],
}

def _es_id_semantico(col: str) -> bool:
    return any(p in col.lower() for p in _PATRONES_ID)

def _tipo_semantico(col: str) -> str:
    col_lower = col.lower()
    for tipo, patrones in _TIPOS_SEMANTICOS.items():
        if any(p in col_lower for p in patrones):
            return tipo
    return "dato"

def _sin_datos() -> str:
    return "⚠️ Sin datos activos. Carga un dataset primero."

def _df_vacio(df) -> bool:
    return df is None or df.empty

def _md_table(headers: list, rows: list) -> str:
    """Genera tabla markdown simple."""
    sep = " | ".join(["---"] * len(headers))
    head = " | ".join(headers)
    body = "\n".join(" | ".join(str(c) for c in row) for row in rows)
    return f"| {head} |\n| {sep} |\n" + "\n".join(f"| {' | '.join(str(c) for c in row)} |" for row in rows)


def _fuzzy_col(col_input: str, df) -> str | None:
    """Encuentra la columna más cercana por fuzzy matching (umbral ≥ 70)."""
    if not col_input:
        return None

    def norm(t: str) -> str:
        t = t.lower().strip()
        t = unicodedata.normalize("NFD", t)
        t = "".join(c for c in t if unicodedata.category(c) != "Mn")
        return re.sub(r"[_\-]", " ", t)

    inp = norm(col_input)
    # Match exacto primero (rápido)
    if col_input in df.columns:
        return col_input
    mejor_score, mejor_col = 0, None
    for col in df.columns:
        score = max(fuzz.ratio(inp, norm(col)),
                    fuzz.partial_ratio(inp, norm(col)))
        if score > mejor_score:
            mejor_score, mejor_col = score, col
    return mejor_col if mejor_score >= 70 else None



# ── /ayuda ───────────────────────────────────────────────────────────────────

AYUDA_CMDS = {
    "columnas":         ("/columnas",                        "Schema con tipos semánticos"),
    "nulos":            ("/nulos",                           "Reporte de nulos por columna"),
    "outliers":         ("/outliers [col]",                  "Detección de valores extremos IQR"),
    "correlacion":      ("/correlacion",                     "Matriz de correlación de Pearson"),
    "unicos":           ("/unicos [col]",                    "Valores únicos con frecuencia"),
    "rango":            ("/rango [col]",                     "Estadísticas detalladas de columna numérica"),
    "top":              ("/top [col] [N]",                   "Top N valores más frecuentes"),
    "describe":         ("/describe",                        "Estadísticas numéricas generales"),
    "head":             ("/head [N]",                        "Primeras N filas"),
    "sample":           ("/sample [N]",                      "N filas aleatorias"),
    "cohorts":          ("/cohorts",                         "Análisis de cohortes por mes"),
    "rentabilidad":     ("/rentabilidad",                    "CAC / LTV / ROI por campaña"),
    "rfm":              ("/rfm",                             "Segmentación RFM de leads"),
    "embudo":           ("/embudo [campaña]",                "Cuello de botella del funnel"),
    "velocidad":        ("/velocidad",                       "Tiempo lead → venta por campaña"),
    "alertas":          ("/alertas",                         "Alertas de integridad del dataset"),
    "metricas":         ("/metricas",                        "Métricas por campaña"),
    "limpiar_duplicados": ("/limpiar_duplicados",            "Eliminar filas duplicadas"),
    "rellenar":         ("/rellenar [col] [estrategia]",     "Rellenar nulos"),
    "eliminar_por":     ("/eliminar_por [col] [op] [val]",   "Filtrar y eliminar filas"),
    "exportar":         ("/exportar",                        "Exportar dataset a CSV"),
    "config":           ("/config",                          "Configuración actual del engine"),
    "estado":           ("/estado",                          "Estado del engine y proveedor LLM"),
}

GRUPOS = {
    "🔍 Exploración":  ["columnas", "nulos", "describe", "head", "sample", "unicos", "rango", "top"],
    "📊 Estadística":  ["outliers", "correlacion"],
    "🧹 Limpieza":     ["limpiar_duplicados", "rellenar", "eliminar_por"],
    "📈 Campañas":     ["alertas", "metricas"],
    "🧠 Modelos":      ["cohorts", "rentabilidad", "rfm", "embudo", "velocidad"],
    "⚙️ Sistema":      ["exportar", "config", "estado"],
}

def bridge_ayuda(flag: str = "") -> str:
    if flag.startswith("--"):
        nombre = flag[2:].lower()
        if nombre not in AYUDA_CMDS:
            return f"❌ Comando `{nombre}` no encontrado. Escribe `/ayuda` para ver todos."
        sintaxis, desc = AYUDA_CMDS[nombre]
        return f"**{sintaxis}**\n\n{desc}"

    lines = ["## Comandos disponibles\n"]
    for grupo, cmds in GRUPOS.items():
        lines.append(f"**{grupo}**")
        for nombre in cmds:
            if nombre in AYUDA_CMDS:
                sintaxis, desc = AYUDA_CMDS[nombre]
                lines.append(f"- `{sintaxis}` — {desc}")
        lines.append("")
    lines.append("_Tip: `/ayuda --[comando]` para detalle de un comando específico._")
    return "\n".join(lines)


# ── /columnas ────────────────────────────────────────────────────────────────

def bridge_columnas(df) -> str:
    if _df_vacio(df):
        return _sin_datos()

    total = len(df)
    rows = []
    for col in df.columns:
        dtype = str(df[col].dtype)
        nulos = int(df[col].isna().sum())
        pct   = (total - nulos) / total * 100
        sem   = _tipo_semantico(col)
        estado = "✅" if pct >= 95 else "⚠️" if pct >= 80 else "❌"
        rows.append([col, dtype, sem, nulos, f"{pct:.1f}% {estado}"])

    header = f"## Schema — {len(df.columns)} columnas · {total} filas\n"
    return header + _md_table(["Columna", "Tipo", "Semántico", "Nulos", "Completo"], rows)


# ── /nulos ───────────────────────────────────────────────────────────────────

def bridge_nulos(df) -> str:
    if _df_vacio(df):
        return _sin_datos()

    total = len(df)
    nulos = df.isna().sum()
    nulos = nulos[nulos > 0].sort_values(ascending=False)

    if nulos.empty:
        return "✅ Dataset sin valores nulos."

    rows = []
    for col, n in nulos.items():
        pct = n / total * 100
        impacto = "❌ crítico" if pct >= 30 else "⚠️ revisar" if pct >= 10 else "ok"
        rows.append([col, n, f"{pct:.1f}%", impacto])

    header = f"## Nulos — {len(nulos)} columnas afectadas\n"
    result = header + _md_table(["Columna", "Nulos", "%", "Impacto"], rows)
    result += "\n\n_Tip: `/rellenar [columna] [estrategia]` para corregir._"
    return result


# ── /describe ────────────────────────────────────────────────────────────────

def bridge_describe(df) -> str:
    if _df_vacio(df):
        return _sin_datos()

    numericas = df.select_dtypes(include="number")
    cols = [c for c in numericas.columns if not _es_id_semantico(c)]

    if not cols:
        return "⚠️ No hay columnas numéricas analizables (excluyendo IDs)."

    desc = numericas[cols].describe().round(2)
    headers = ["Stat"] + list(desc.columns)
    rows = [[idx] + [f"{v:,.2f}" for v in row] for idx, row in desc.iterrows()]

    excluidas = [c for c in numericas.columns if _es_id_semantico(c)]
    note = f"\n\n_Excluidas como ID: {', '.join(excluidas)}_" if excluidas else ""
    return f"## Describe — columnas numéricas\n" + _md_table(headers, rows) + note


# ── /head  /sample ───────────────────────────────────────────────────────────

def bridge_head(df, n: int = 5) -> dict | str:
    if _df_vacio(df):
        return _sin_datos()
    sub = df.head(n).copy()
    sub = sub.where(pd.notnull(sub), None)  # NaN → None (JSON null)
    return {
        "tipo":   "tabla",
        "tabla":  sub.to_dict(orient="records"),
        "titulo": f"Head — primeras {n} filas",
    }


def bridge_sample(df, n: int = 5) -> dict | str:
    if _df_vacio(df):
        return _sin_datos()
    sub = df.sample(min(n, len(df))).copy()
    sub = sub.where(pd.notnull(sub), None)  # NaN → None (JSON null)
    return {
        "tipo":   "tabla",
        "tabla":  sub.to_dict(orient="records"),
        "titulo": f"Sample — {n} filas aleatorias",
    }



# ── /outliers ────────────────────────────────────────────────────────────────

def bridge_outliers(df, col: str = "") -> str:
    if _df_vacio(df):
        return _sin_datos()

    numericas = df.select_dtypes(include="number")
    # Fuzzy match si se especificó columna
    if col:
        col_real = _fuzzy_col(col, df)
        if col_real and col_real in numericas.columns:
            cols = [col_real]
        else:
            return f"⚠️ Columna `{col}` no encontrada o no es numérica."
    else:
        cols = [c for c in numericas.columns if not _es_id_semantico(c)]

    total = len(df)
    rows = []
    encontrados = 0

    for c in cols:
        serie = df[c].dropna()
        if serie.empty:
            continue
        q1  = serie.quantile(0.25)
        q3  = serie.quantile(0.75)
        iqr = q3 - q1
        lim_inf = q1 - 1.5 * iqr
        lim_sup = q3 + 1.5 * iqr
        outliers = serie[(serie < lim_inf) | (serie > lim_sup)]
        n = len(outliers)
        if n == 0:
            continue
        encontrados += 1
        pct = n / total * 100
        nivel = "❌" if pct > 5 else "⚠️"
        rows.append([c, f"{nivel} {n}", f"{pct:.1f}%",
                     f"{lim_inf:,.2f}", f"{lim_sup:,.2f}",
                     f"{serie.min():,.2f}", f"{serie.max():,.2f}"])

    if encontrados == 0:
        return f"✅ Sin outliers detectados en: {', '.join(cols)}."

    result = "## Outliers — método IQR\n"
    result += _md_table(["Columna", "Outliers", "%", "Lím. inf", "Lím. sup", "Min datos", "Max datos"], rows)
    result += "\n\n_Outlier = valor fuera de [Q1 − 1.5·IQR, Q3 + 1.5·IQR]_"
    return result


# ── /correlacion ─────────────────────────────────────────────────────────────

def bridge_correlacion(df) -> str:
    if _df_vacio(df):
        return _sin_datos()

    numericas = df.select_dtypes(include="number")
    cols = [c for c in numericas.columns if not _es_id_semantico(c)]

    if len(cols) < 2:
        return "⚠️ Se necesitan al menos 2 columnas numéricas para calcular correlación."

    corr = numericas[cols].corr().round(2)
    headers = [""] + list(corr.columns)
    rows = []
    for idx, row in corr.iterrows():
        celdas = [str(idx)]
        for c in corr.columns:
            v = row[c]
            if idx == c:
                celdas.append("1.00")
            else:
                prefix = "🟢" if v >= 0.7 else "🔴" if v <= -0.7 else "🟡" if abs(v) >= 0.4 else ""
                celdas.append(f"{prefix}{v:+.2f}")
        rows.append(celdas)

    result = "## Correlación de Pearson\n"
    result += _md_table(headers, rows)
    result += "\n\n🟢 ≥ 0.7 fuerte · 🟡 ≥ 0.4 media · 🔴 ≤ −0.7 negativa fuerte"
    return result


# ── /unicos ──────────────────────────────────────────────────────────────────

def bridge_unicos(df, col: str = "") -> str:
    if _df_vacio(df):
        return _sin_datos()
    col_real = _fuzzy_col(col, df) if col else None
    if not col_real:
        disponibles = ", ".join(f"`{c}`" for c in df.columns)
        return f"⚠️ Especifica una columna. Ej: `/unicos estado`\n\nColumnas disponibles: {disponibles}"

    vc = df[col_real].value_counts(dropna=False)
    total = len(df)
    rows = []
    for val, cnt in vc.items():
        pct = cnt / total * 100
        bar_len = int(pct / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        rows.append([str(val) if str(val) != "nan" else "(nulo)", cnt, f"{pct:.1f}%", bar])

    return f"## Únicos — {col_real} ({len(vc)} valores)\n" + _md_table(["Valor", "Count", "%", "Distribución"], rows)


# ── /rango ───────────────────────────────────────────────────────────────────

def bridge_rango(df, col: str = "") -> str:
    if _df_vacio(df):
        return _sin_datos()

    numericas = [c for c in df.select_dtypes(include="number").columns if not _es_id_semantico(c)]
    col_real = _fuzzy_col(col, df) if col else None
    if not col_real or col_real not in df.columns:
        return f"⚠️ Especifica una columna numérica. Ej: `/rango costo_lead`\n\nNuméricas disponibles: {', '.join(f'`{c}`' for c in numericas)}"
    if col_real not in df.select_dtypes(include="number").columns:
        return f"⚠️ `{col_real}` no es numérica."

    s = df[col_real].dropna()
    q1  = s.quantile(0.25)
    q3  = s.quantile(0.75)
    iqr = q3 - q1

    stats = [
        ("count",    f"{len(s):,}",                   "Registros sin nulos"),
        ("nulos",    f"{df[col_real].isna().sum():,}",  "Valores faltantes"),
        ("min",      f"{s.min():,.2f}",                "Valor mínimo"),
        ("max",      f"{s.max():,.2f}",                "Valor máximo"),
        ("media",    f"{s.mean():,.2f}",               "Promedio"),
        ("mediana",  f"{s.median():,.2f}",             "Valor central"),
        ("std",      f"{s.std():,.2f}",                "Desviación estándar"),
        ("Q1",       f"{q1:,.2f}",                     "Percentil 25"),
        ("Q3",       f"{q3:,.2f}",                     "Percentil 75"),
        ("IQR",      f"{iqr:,.2f}",                    "Q3 − Q1"),
        ("lím. inf", f"{q1 - 1.5*iqr:,.2f}",          "Límite inferior outliers"),
        ("lím. sup", f"{q3 + 1.5*iqr:,.2f}",          "Límite superior outliers"),
    ]
    return f"## Rango — {col_real}\n" + _md_table(["Stat", "Valor", "Descripción"], stats)


# ── /top ─────────────────────────────────────────────────────────────────────

def bridge_top(df, col: str = "", n: int = 10) -> str:
    if _df_vacio(df):
        return _sin_datos()
    col_real = _fuzzy_col(col, df) if col else None
    if not col_real:
        return f"⚠️ Especifica una columna. Ej: `/top campana 5`"

    vc = df[col_real].value_counts(dropna=True).head(n)
    total = len(df)
    rows = [[i, val, cnt, f"{cnt/total*100:.1f}%"] for i, (val, cnt) in enumerate(vc.items(), 1)]
    return f"## Top {n} — {col_real}\n" + _md_table(["#", "Valor", "Count", "%"], rows)


# ── /limpiar_duplicados ──────────────────────────────────────────────────────

def bridge_limpiar_duplicados(df, engine, validator, calc) -> tuple:
    """Retorna (df_nuevo, mensaje)"""
    if _df_vacio(df):
        return df, _sin_datos()

    n_antes = len(df)
    df_limpio, _ = validator.limpiar_duplicados(df)
    n_eliminados = n_antes - len(df_limpio)

    if n_eliminados == 0:
        return df, "✅ Sin duplicados encontrados."

    try:
        metricas    = calc.calcular(df_limpio, nivel="campana")
        resumen_llm = calc.resumen_para_llm(metricas, nivel="campana")
        schema_llm  = calc.resumen_schema(df_limpio)
        if engine:
            engine.set_contexto_completo(resumen_llm, schema_llm)
            engine.limpiar_memoria()
    except Exception:
        pass

    msg = f"✅ Eliminados **{n_eliminados} duplicados** — {n_antes} → {len(df_limpio)} filas. Contexto actualizado."
    return df_limpio, msg


# ── /rellenar ────────────────────────────────────────────────────────────────

def bridge_rellenar(df, engine, validator, calc, partes: list) -> tuple:
    """Retorna (df_nuevo, mensaje)"""
    ESTRATEGIAS = {"media", "mediana", "moda", "valor"}
    if len(partes) < 3:
        return df, "⚠️ Uso: `/rellenar [columna] [estrategia]`\n\nEstrategias: `media`, `mediana`, `moda`, `valor`"

    columna    = partes[1]
    estrategia = partes[2].lower()
    valor_relleno = partes[3] if len(partes) > 3 else None

    if estrategia not in ESTRATEGIAS:
        return df, f"⚠️ Estrategia `{estrategia}` inválida. Usa: {', '.join(ESTRATEGIAS)}"

    df_nuevo, reporte = validator.rellenar_nulos(df, columna, estrategia, valor_relleno)
    if reporte.get("error"):
        return df, f"❌ {reporte['error']}"

    n = reporte.get("rellenados", 0)
    try:
        metricas    = calc.calcular(df_nuevo, nivel="campana")
        resumen_llm = calc.resumen_para_llm(metricas, nivel="campana")
        schema_llm  = calc.resumen_schema(df_nuevo)
        if engine:
            engine.set_contexto_completo(resumen_llm, schema_llm)
            engine.limpiar_memoria()
    except Exception:
        pass

    return df_nuevo, f"✅ Rellenados **{n} nulos** en `{columna}` con estrategia `{estrategia}`. Contexto actualizado."


# ── /eliminar_por ────────────────────────────────────────────────────────────

def bridge_eliminar_por(df, engine, validator, calc, partes: list) -> tuple:
    """Retorna (df_nuevo, mensaje)"""
    OPERADORES_UNARIOS  = {"isnull", "notnull"}
    OPERADORES_BINARIOS = {"==", "!=", ">", "<", ">=", "<="}

    if len(partes) < 3:
        return df, (
            "⚠️ Uso: `/eliminar_por [col] [op] ([valor])`\n\n"
            "- Unarios (sin valor): `isnull`, `notnull`\n"
            "- Binarios (con valor): `==`, `!=`, `>`, `<`, `>=`, `<=`\n\n"
            "Ej: `/eliminar_por campana isnull` · `/eliminar_por costo_lead < 0`"
        )

    columna  = partes[1]
    operador = partes[2].lower()

    if operador in OPERADORES_UNARIOS:
        valor = None
    elif operador in OPERADORES_BINARIOS:
        if len(partes) < 4:
            return df, f"⚠️ `{operador}` requiere un valor. Ej: `/eliminar_por costo_lead {operador} 0`"
        raw = partes[3]
        try:
            valor = float(raw) if "." in raw else int(raw)
        except ValueError:
            valor = raw
    else:
        return df, f"⚠️ Operador `{operador}` no reconocido. Unarios: `isnull`, `notnull` · Binarios: `== != > < >= <=`"

    df_filtrado, reporte = validator.eliminar_por_criterio(df, columna, operador, valor)

    if reporte.get("error"):
        return df, f"❌ {reporte['error']}"

    n = reporte["eliminados"]
    criterio = reporte["criterio"]

    if n == 0:
        return df, f"✅ Ninguna fila cumple `{criterio}` — sin cambios."

    try:
        metricas    = calc.calcular(df_filtrado, nivel="campana")
        resumen_llm = calc.resumen_para_llm(metricas, nivel="campana")
        schema_llm  = calc.resumen_schema(df_filtrado)
        if engine:
            engine.set_contexto_completo(resumen_llm, schema_llm)
            engine.limpiar_memoria()
    except Exception:
        pass

    n_antes = len(df)
    return df_filtrado, f"✅ Eliminadas **{n} filas** donde `{criterio}` — {n_antes} → {len(df_filtrado)} filas. Contexto actualizado."


# ── /exportar ────────────────────────────────────────────────────────────────

def bridge_exportar(df) -> str:
    if _df_vacio(df):
        return _sin_datos()
    fn = f"adly_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    try:
        df.to_csv(fn, index=False)
        return f"✅ Exportado: `{fn}` ({len(df)} filas)"
    except Exception as e:
        return f"❌ Error al exportar: {e}"


# ── /config ───────────────────────────────────────────────────────────────────

def bridge_config() -> str:
    """Muestra la configuración actual del engine (desde .env)."""
    import os
    proveedor  = os.getenv("ADLY_LLM_PROVIDER", "ollama")
    modelo     = os.getenv("ADLY_LLM_MODEL",    "—")
    base_url   = os.getenv("ADLY_LLM_BASE_URL", "—")
    api_key    = os.getenv("ADLY_LLM_API_KEY",  "")
    fuente     = os.getenv("ADLY_DATA_SOURCE",  "mock")
    sheet_id   = os.getenv("ADLY_SHEET_ID",     "—")
    fallback   = os.getenv("ADLY_LLM_FALLBACK", "ollama,groq,gemini")
    api_masked = f"{api_key[:6]}…{api_key[-4:]}" if len(api_key) > 12 else ("(no configurada)" if not api_key else api_key)

    rows = [
        ["Proveedor LLM",  proveedor],
        ["Modelo",         modelo],
        ["Base URL",       base_url],
        ["API Key",        api_masked],
        ["Fuente datos",   fuente],
        ["Sheet ID",       sheet_id],
        ["Fallback chain", fallback],
    ]
    return "## ⚙️ Configuración actual\n" + _md_table(["Parámetro", "Valor"], rows)


# ── /estado ───────────────────────────────────────────────────────────────────

def bridge_estado(engine) -> str:
    """Muestra el estado runtime del engine: LLM activo, memoria, freshness."""
    if engine is None:
        return "⚠️ Engine no inicializado."

    llm_nombre = getattr(engine.llm, "nombre", lambda: type(engine.llm).__name__)()
    modelo     = getattr(engine.llm, "modelo",    "—")
    fuente     = getattr(engine, "_fuente",        "—")
    mem_resumen = engine.memoria.resumen() if hasattr(engine, "memoria") else "—"

    # Calcular freshness desde engine
    ingested_at = getattr(engine, "_ingested_at", None)
    if ingested_at:
        delta = datetime.now() - ingested_at
        mins  = int(delta.total_seconds() / 60)
        freshness = f"hace {mins} min" if mins < 60 else f"hace {mins // 60}h {mins % 60}min"
    else:
        freshness = "sin datos cargados"

    ultimo_cmd = getattr(engine, "_ultimo_comando", "") or "—"

    rows = [
        ["LLM activo",     llm_nombre],
        ["Modelo",         modelo],
        ["Fuente datos",   fuente],
        ["Datos cargados", freshness],
        ["Último comando", ultimo_cmd],
        ["Memoria",        mem_resumen],
    ]
    return "## 🔍 Estado del engine\n" + _md_table(["Campo", "Valor"], rows)


# ── Modelos — detector de columnas faltantes ────────────────────────────────

_REQS_MODELO = {
    "/rentabilidad": {
        "requeridas": ["campana", "costo", "valor_venta", "estado"],
        "patrones": {
            "campana":     ["campana", "campaign", "utm_campaign"],
            "costo":       ["costo_lead", "cpl", "cost", "spend", "costo"],
            "valor_venta": ["valor_venta", "revenue", "valor", "ingreso", "amount"],
            "estado":      ["estado", "status", "stage", "funnel_stage"],
        },
    },
    "/cohorts": {
        "requeridas": ["fecha_entrada", "estado"],
        "patrones": {
            "fecha_entrada": ["fecha_creacion", "created", "creacion", "record_ts", "fecha_entrada"],
            "estado":        ["estado", "status", "stage", "funnel_stage"],
        },
    },
    "/rfm": {
        "requeridas": ["fecha_entrada", "estado"],
        "patrones": {
            "fecha_entrada": ["fecha_creacion", "created", "creacion", "record_ts", "fecha_entrada"],
            "estado":        ["estado", "status", "stage", "funnel_stage"],
        },
    },
    "/embudo": {
        "requeridas": ["estado"],
        "patrones": {
            "estado": ["estado", "status", "stage", "funnel_stage"],
        },
    },
    "/velocidad": {
        "requeridas": ["fecha_entrada", "fecha_cierre", "estado"],
        "patrones": {
            "fecha_entrada": ["fecha_creacion", "created", "creacion", "record_ts", "fecha_entrada"],
            "fecha_cierre":  ["fecha_cierre", "closed", "close_date", "fecha_venta"],
            "estado":        ["estado", "status", "stage", "funnel_stage"],
        },
    },
}

def _detectar_col_bridge(df, patrones: list) -> str:
    for col in df.columns:
        if any(p in col.lower() for p in patrones):
            return col
    return ""

def _cols_faltantes(df, cmd: str) -> list:
    if cmd not in _REQS_MODELO or df is None:
        return []
    reqs = _REQS_MODELO[cmd]
    faltantes = []
    for nombre in reqs["requeridas"]:
        patrones = reqs["patrones"][nombre]
        if not _detectar_col_bridge(df, patrones):
            faltantes.append(nombre)
    return faltantes

def _despachar_modelo(cmd: str, partes: list, df, engine) -> dict:
    if _df_vacio(df):
        return {"resultado": _sin_datos(), "df_nuevo": df, "es_comando": True}

    faltantes = _cols_faltantes(df, cmd)
    if faltantes:
        cols_disponibles = ", ".join(f"`{c}`" for c in df.columns)
        faltantes_str    = ", ".join(f"`{f}`" for f in faltantes)
        return {
            "resultado": (
                f"**`{cmd}`** necesita columnas que no están en el dataset actual.\n\n"
                f"**Faltan:** {faltantes_str}\n\n"
                f"**Disponibles:** {cols_disponibles}\n\n"
                f"_Tip: `/columnas` para ver el schema completo._"
            ),
            "df_nuevo": df,
            "es_comando": True,
        }

    ctx = None
    try:
        from interfaces.cli.commands import (
            cmd_rentabilidad, cmd_rfm, cmd_cohorts,
            cmd_embudo, cmd_velocidad,
        )
        if cmd == "/rentabilidad":
            ctx = cmd_rentabilidad(df)
        elif cmd == "/rfm":
            ctx = cmd_rfm(df)
        elif cmd == "/cohorts":
            ctx = cmd_cohorts(df)
        elif cmd == "/embudo":
            col_campana = " ".join(partes[1:]) if len(partes) > 1 else ""
            ctx = cmd_embudo(df, col_campana)
        elif cmd == "/velocidad":
            ctx = cmd_velocidad(df)
        elif cmd in {"/metricas", "/alertas"}:
            return {"resultado": None, "df_nuevo": df, "es_comando": False}
    except Exception as e:
        return {
            "resultado": f"Error ejecutando `{cmd}`: {e}",
            "df_nuevo": df,
            "es_comando": True,
        }

    if ctx is None:
        return {
            "resultado": (
                f"**`{cmd}`** no pudo generar resultados con el dataset actual.\n\n"
                f"Posibles causas:\n"
                f"- No hay ventas registradas en la columna de estado\n"
                f"- Los valores de estado no se reconocen (revisa con `/unicos estado`)\n"
                f"- Fechas invalidas o faltantes\n\n"
                f"_Tip: `/columnas` para ver el schema completo._"
            ),
            "df_nuevo": df,
            "es_comando": True,
        }

    if engine:
        engine.agregar_contexto_comando(cmd, ctx)

    return {"resultado": ctx, "df_nuevo": df, "es_comando": True}


# ── Dispatcher principal ─────────────────────────────────────────────────────

def despachar_comando(text: str, df, engine=None, validator=None, calc=None) -> dict:
    """
    Recibe el texto del usuario, ejecuta el comando si aplica.
    Retorna dict con:
      - 'resultado': str (markdown) — None si no es comando
      - 'df_nuevo': DataFrame — puede ser diferente si el comando mutó el df
      - 'es_comando': bool
    """
    if not text.startswith("/"):
        return {"resultado": None, "df_nuevo": df, "es_comando": False}

    partes = text.strip().split()
    cmd    = partes[0].lower()

    # ── Exploración ──────────────────────────────────────────────────────────
    if cmd == "/ayuda":
        flag = partes[1] if len(partes) > 1 else ""
        return {"resultado": bridge_ayuda(flag), "df_nuevo": df, "es_comando": True}

    if cmd == "/columnas":
        return {"resultado": bridge_columnas(df), "df_nuevo": df, "es_comando": True}

    if cmd == "/nulos":
        return {"resultado": bridge_nulos(df), "df_nuevo": df, "es_comando": True}

    if cmd == "/describe":
        return {"resultado": bridge_describe(df), "df_nuevo": df, "es_comando": True}

    if cmd == "/head":
        n = int(partes[1]) if len(partes) > 1 and partes[1].isdigit() else 5
        return {"resultado": bridge_head(df, n), "df_nuevo": df, "es_comando": True}

    if cmd == "/sample":
        n = int(partes[1]) if len(partes) > 1 and partes[1].isdigit() else 5
        return {"resultado": bridge_sample(df, n), "df_nuevo": df, "es_comando": True}

    if cmd == "/outliers":
        col = partes[1] if len(partes) > 1 else ""
        return {"resultado": bridge_outliers(df, col), "df_nuevo": df, "es_comando": True}

    if cmd == "/correlacion":
        return {"resultado": bridge_correlacion(df), "df_nuevo": df, "es_comando": True}

    if cmd == "/unicos":
        col = partes[1] if len(partes) > 1 else ""
        return {"resultado": bridge_unicos(df, col), "df_nuevo": df, "es_comando": True}

    if cmd == "/rango":
        col = partes[1] if len(partes) > 1 else ""
        return {"resultado": bridge_rango(df, col), "df_nuevo": df, "es_comando": True}

    if cmd == "/top":
        col = partes[1] if len(partes) > 1 else ""
        n   = int(partes[2]) if len(partes) > 2 and partes[2].isdigit() else 10
        return {"resultado": bridge_top(df, col, n), "df_nuevo": df, "es_comando": True}

    # ── Limpieza (mutan el df) ───────────────────────────────────────────────
    if cmd == "/limpiar_duplicados":
        if validator is None or calc is None:
            return {"resultado": "⚠️ Comando no disponible en este contexto.", "df_nuevo": df, "es_comando": True}
        df_nuevo, msg = bridge_limpiar_duplicados(df, engine, validator, calc)
        return {"resultado": msg, "df_nuevo": df_nuevo, "es_comando": True}

    if cmd == "/rellenar":
        if validator is None or calc is None:
            return {"resultado": "⚠️ Comando no disponible en este contexto.", "df_nuevo": df, "es_comando": True}
        df_nuevo, msg = bridge_rellenar(df, engine, validator, calc, partes)
        return {"resultado": msg, "df_nuevo": df_nuevo, "es_comando": True}

    if cmd == "/eliminar_por":
        if validator is None or calc is None:
            return {"resultado": "⚠️ Comando no disponible en este contexto.", "df_nuevo": df, "es_comando": True}
        df_nuevo, msg = bridge_eliminar_por(df, engine, validator, calc, partes)
        return {"resultado": msg, "df_nuevo": df_nuevo, "es_comando": True}

    if cmd == "/exportar":
        return {"resultado": bridge_exportar(df), "df_nuevo": df, "es_comando": True}

    if cmd == "/config":
        return {"resultado": bridge_config(), "df_nuevo": df, "es_comando": True}

    if cmd == "/estado":
        return {"resultado": bridge_estado(engine), "df_nuevo": df, "es_comando": True}

    # ── Modelos estadísticos ─────────────────────────────────────────────────
    if cmd in {"/rentabilidad", "/rfm", "/cohorts", "/embudo", "/velocidad", "/metricas", "/alertas"}:
        return _despachar_modelo(cmd, partes, df, engine)

    # ── Comando no reconocido ────────────────────────────────────────────────
    return {
        "resultado": f"❓ Comando `{cmd}` no reconocido. Escribe `/ayuda` para ver todos los comandos disponibles.",
        "df_nuevo": df,
        "es_comando": True,
    }


# ── /modelo ──────────────────────────────────────────────────────────────────

MODELOS_CONFIG = {
    "groq":     {"label": "Groq",     "modelo": "llama-3.3-70b-versatile", "var_env": "GROQ_API_KEY",     "url": "https://console.groq.com/keys"},
    "gemini":   {"label": "Gemini",   "modelo": "gemini-2.5-flash",        "var_env": "GEMINI_API_KEY",   "url": "https://aistudio.google.com/app/apikey"},
    "openai":   {"label": "OpenAI",   "modelo": "gpt-4o-mini",             "var_env": "OPENAI_API_KEY",   "url": "https://platform.openai.com/api-keys"},
    "deepseek": {"label": "DeepSeek", "modelo": "deepseek-chat",           "var_env": "DEEPSEEK_API_KEY", "url": "https://platform.deepseek.com/api_keys"},
    "qwen":     {"label": "Qwen",     "modelo": "qwen-turbo",              "var_env": "QWEN_API_KEY",     "url": "https://bailian.console.aliyun.com/"},
    "ollama":   {"label": "Ollama",   "modelo": "qwen2.5-coder:7b",        "var_env": None,               "url": None},
}

def bridge_modelo_status(modelo_activo: str) -> str:
    """Muestra el modelo activo y los disponibles."""
    import os
    lineas = [f"## Modelo activo: **{modelo_activo}**\n"]
    lineas.append("| Modelo | Disponible | Modelo base |")
    lineas.append("|--------|------------|-------------|")
    for key, cfg in MODELOS_CONFIG.items():
        if cfg["var_env"] is None:
            disponible = "local"
        else:
            tiene_key = bool(os.getenv(cfg["var_env"], "").strip())
            disponible = "✅" if tiene_key else "❌ sin key"
        activo = " ◀ activo" if key == modelo_activo else ""
        lineas.append(f"| `{key}` | {disponible} | {cfg['modelo']}{activo} |")
    lineas.append("\n_Usa `/modelo [nombre]` para cambiar. Ej: `/modelo gemini`_")
    return "\n".join(lineas)


def bridge_modelo_cambiar(nombre: str, modelo_activo: str) -> dict:
    """
    Inicia el cambio de modelo.
    Retorna dict con:
      - "ok": True si se puede cambiar sin key
      - "necesita_key": True si falta la API key
      - "mensaje": str para mostrar al usuario
      - "pending": dict con info del modelo pendiente (si necesita key)
    """
    import os

    nombre = nombre.lower().strip()
    if nombre not in MODELOS_CONFIG:
        nombres = ", ".join(f"`{k}`" for k in MODELOS_CONFIG)
        return {
            "ok": False,
            "necesita_key": False,
            "mensaje": f"❌ Modelo `{nombre}` no reconocido.\n\nDisponibles: {nombres}",
            "pending": None,
        }

    if nombre == modelo_activo:
        return {
            "ok": False,
            "necesita_key": False,
            "mensaje": f"✅ Ya estás usando **{MODELOS_CONFIG[nombre]['label']}**.",
            "pending": None,
        }

    cfg = MODELOS_CONFIG[nombre]

    # Ollama no necesita key
    if cfg["var_env"] is None:
        return {
            "ok": True,
            "necesita_key": False,
            "mensaje": f"✅ Cambiado a **{cfg['label']}** (`{cfg['modelo']}`). Asegúrate de tener Ollama corriendo.",
            "pending": None,
            "nuevo_modelo": nombre,
        }

    # Verificar si ya tiene key
    tiene_key = bool(os.getenv(cfg["var_env"], "").strip())
    if tiene_key:
        return {
            "ok": True,
            "necesita_key": False,
            "mensaje": f"✅ Cambiado a **{cfg['label']}** (`{cfg['modelo']}`).",
            "pending": None,
            "nuevo_modelo": nombre,
        }

    # Necesita key — iniciar flujo
    return {
        "ok": False,
        "necesita_key": True,
        "mensaje": (
            f"**{cfg['label']}** necesita una API key.\n\n"
            f"Consíguela en: {cfg['url']}\n\n"
            f"Pégala aquí y la configuro automáticamente:"
        ),
        "pending": {"modelo": nombre, "var_env": cfg["var_env"], "label": cfg["label"]},
    }


def bridge_modelo_guardar_key(api_key: str, pending: dict) -> dict:
    """
    Guarda la API key en .env y confirma el cambio de modelo.
    La key se enmascara en la respuesta.
    """
    import re

    var_env   = pending["var_env"]
    label     = pending["label"]
    modelo    = pending["modelo"]
    key_clean = api_key.strip()

    if not key_clean or len(key_clean) < 8:
        return {
            "ok": False,
            "mensaje": "❌ La key no parece válida. Inténtalo de nuevo.",
            "nuevo_modelo": None,
        }

    # Enmascarar para mostrar al usuario
    mascara = key_clean[:4] + "•" * (len(key_clean) - 8) + key_clean[-4:]

    # Guardar en .env
    try:
        env_path = ".env"
        try:
            with open(env_path, "r") as f:
                lineas = f.readlines()
        except FileNotFoundError:
            lineas = []

        # Reemplazar si existe, agregar si no
        nueva_linea = f"{var_env}={key_clean}\n"
        encontrado  = False
        for i, linea in enumerate(lineas):
            if linea.startswith(f"{var_env}="):
                lineas[i] = nueva_linea
                encontrado = True
                break
        if not encontrado:
            lineas.append(nueva_linea)

        with open(env_path, "w") as f:
            f.writelines(lineas)

        # También setear en os.environ para que tome efecto sin reiniciar
        import os
        os.environ[var_env] = key_clean

        return {
            "ok": True,
            "mensaje": f"✅ **{label}** configurado.\nKey guardada: `{mascara}`\nModelo activo cambiado a **{label}**.",
            "nuevo_modelo": modelo,
        }
    except Exception as e:
        return {
            "ok": False,
            "mensaje": f"❌ No pude guardar la key: {e}",
            "nuevo_modelo": None,
        }
