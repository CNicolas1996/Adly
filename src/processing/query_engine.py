# query_engine.py — Adly · Data-Buddy
# v1.5 — fuzzy matching con rapidfuzz (agnóstico al schema)
#
# Arquitectura:
#   CAPA 1 — Schema Reader  : lee el df real, sin hardcodeo
#   CAPA 2 — Fuzzy Matcher  : rapidfuzz contra columnas y valores reales
#   CAPA 3 — Intent+Executor: detecta qué quiere el usuario y ejecuta pandas
#
# Dependencia: rapidfuzz>=3.0.0
# Firma pública — no cambiar:
#   ejecutar_query_analitica(pregunta: str, df: pd.DataFrame) -> str | None

import re
import unicodedata
import pandas as pd
from rapidfuzz import fuzz



# ─────────────────────────────────────────
# STOPWORDS ANALÍTICAS
# Palabras funcionales que NUNCA matchean contra valores del df
# ─────────────────────────────────────────

# Match directo de estados del embudo — antes del fuzzy, sin importar stopwords
# Estas palabras identifican estados aunque estén en la pregunta como sustantivos
ESTADO_KEYWORDS_DIRECTOS = {
    "lead": "lead", "leads": "lead",
    "mql": "mql", "mqls": "mql",
    "sql": "sql", "sqls": "sql",
    "venta": "venta", "ventas": "venta", "sale": "venta", "sales": "venta",
    "sold": "venta",
    "perdido": "perdido", "perdidos": "perdido", "lost": "perdido",
    "interesado": "lead", "interesados": "lead",
    "pendiente": "lead", "pendientes": "lead",
}

# Stopwords conversacionales — saludos y frases que NO deben disparar fuzzy match
STOPWORDS_CONVERSACIONALES = {
    "hola", "buenos", "buenas", "buen", "hi", "hello", "hey", "que tal",
    "qué tal", "gracias", "ok", "okay", "listo", "dale", "por favor",
    "disculpa", "perdona", "sabes", "sabés", "tienes", "tenés",
}

# Sinónimos semánticos — mapeo para columnas comunes
SINONIMOS_COLUMNA = {
    "revenue": "revenue", "ingresos": "revenue", "ganancias": "revenue",
    "costo": "costo_lead", "coste": "costo_lead", "gasto": "costo_lead",
    "pais": "country", "país": "country", "paises": "country", "países": "country",
    "campaña": "utm_campaign", "campana": "utm_campaign", "campaign": "utm_campaign",
    "ad": "utm_ad", "anuncio": "utm_ad",
    "adset": "utm_adset", "conjunto": "utm_adset",
    "estado": "estado", "status": "estado", "etapa": "estado",
    "lead": "lead", "leads": "lead",
    "fecha": "fecha", "date": "fecha",
}

STOPWORDS_ANALITICAS = {
    # Acciones
    "cuantos", "cuantas", "cuanto", "cuanta", "total", "suma", "promedio",
    "llegaron", "entraron", "vinieron", "captamos", "capturamos", "registraron",
    "media", "average", "cuenta", "agrupa", "agrupar", "muestra", "muestrame",
    "compara", "comparar", "ranking", "top", "mejor", "peor", "mayor", "menor",
    "desglose", "resumen", "conteo", "distribucion", "breakdown",
    # Conectores
    "por", "para", "con", "sin", "entre", "versus", "contra", "cada",
    "hay", "tiene", "tienen", "hay", "son", "fue", "fueron",
    # Temporales
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    "mes", "semana", "año", "trimestre", "hoy", "ayer",
    # Artículos y preposiciones
    "que", "los", "las", "del", "una", "uno", "este", "esta",
    # Partes de nombres de columnas compuestas — NUNCA deben matchear contra valores
    "stage", "funnel", "utm", "campaign", "adset",
}

# ─────────────────────────────────────────
# CAPA 1 — SCHEMA READER
# ─────────────────────────────────────────

def _leer_schema(df: pd.DataFrame) -> dict:
    schema = {"categoricas": {}, "numericas": [], "fecha": None}
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            schema["fecha"] = col
        elif pd.api.types.is_numeric_dtype(df[col]):
            schema["numericas"].append(col)
        else:
            vals = df[col].dropna().unique()[:50].tolist()
            schema["categoricas"][col] = [str(v) for v in vals]
    if not schema["fecha"]:
        for col in df.columns:
            if "fecha" in col.lower() or "date" in col.lower() or "timestamp" in col.lower():
                schema["fecha"] = col
                schema["categoricas"].pop(col, None)
                break
    return schema


# ─────────────────────────────────────────
# CAPA 2 — FUZZY MATCHER
# ─────────────────────────────────────────

def _normalizar(texto: str) -> str:
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[_\-]", " ", texto)
    return texto


def _match_columna(palabra: str, df: pd.DataFrame, umbral: int = 75):
    palabra_norm = _normalizar(palabra)
    mejor_score, mejor_col = 0, None
    for col in df.columns:
        col_norm = _normalizar(col)
        score = max(fuzz.ratio(palabra_norm, col_norm), fuzz.partial_ratio(palabra_norm, col_norm))
        if score > mejor_score:
            mejor_score, mejor_col = score, col
    return (mejor_col, mejor_score) if mejor_score >= umbral else None


def _match_valor(palabra: str, col: str, df: pd.DataFrame, umbral: int = 72):
    valores = df[col].dropna().unique()
    if len(valores) == 0:
        return None
    palabra_norm = _normalizar(palabra)
    mejor_score, mejor_val = 0, None
    for val in valores:
        val_norm = _normalizar(str(val))
        score = max(fuzz.ratio(palabra_norm, val_norm), fuzz.partial_ratio(palabra_norm, val_norm))
        if score > mejor_score:
            mejor_score, mejor_val = score, val
    return (mejor_val, mejor_score) if mejor_score >= umbral else None


def _detectar_todo(palabras: list, df: pd.DataFrame, schema: dict) -> dict:
    res = {
        "col_agrupacion": None, "col_numerica": None,
        "valor_filtro": None, "col_estado": None, "val_estado": None,
        "confirmaciones": [], "interpretaciones": [],
    }
    # Detectar columna de estado por nombre
    for col in df.columns:
        if _normalizar(col) in {"estado", "status", "etapa", "fase", "pipeline", "stage"}:
            res["col_estado"] = col
            break

    for palabra in palabras:
        if len(palabra) <= 3:
            continue

        # Skip stopwords conversacionales — saludos no deben matching
        if palabra.lower() in STOPWORDS_CONVERSACIONALES:
            continue

        # Resolver sinónimos semánticos antes del fuzzy match
        palabra_original = palabra
        palabra = SINONIMOS_COLUMNA.get(palabra.lower(), palabra)

        # Pre-match directo de estados — sin fuzzy, sin stopwords
        # "leads", "ventas", "sold" → detectados aquí antes de cualquier otra cosa
        if palabra in ESTADO_KEYWORDS_DIRECTOS and not res["val_estado"]:
            res["val_estado"] = ESTADO_KEYWORDS_DIRECTOS[palabra]
            continue

        # Match de columna
        mc = _match_columna(palabra, df, umbral=75)
        if mc:
            col_real, score = mc
            if 75 <= score < 85:
                res["confirmaciones"].append(f"columna '{col_real}' ('{palabra}'→'{col_real}', {score}%)")
                continue
            if col_real in schema["numericas"] and not res["col_numerica"]:
                res["col_numerica"] = col_real
                if score < 95:
                    res["interpretaciones"].append(f"INTERPRETACIÓN: '{palabra}' → col numérica '{col_real}' ({score}%)")
                continue
            if col_real in schema["categoricas"] and not res["col_agrupacion"]:
                res["col_agrupacion"] = col_real
                if score < 95:
                    res["interpretaciones"].append(f"INTERPRETACIÓN: '{palabra}' → columna '{col_real}' ({score}%)")
                continue
            # Columna matcheó fuerte (score >= 80) pero ya estaban ocupadas — no buscar en valores
            if score >= 80:
                continue
        # Match de valor en columnas categóricas — nunca matchear stopwords analíticas
        if palabra in STOPWORDS_ANALITICAS:
            continue
        for col in schema["categoricas"]:
            mv = _match_valor(palabra, col, df, umbral=72)
            if not mv:
                continue
            val_real, score = mv
            if 72 <= score < 83:
                res["confirmaciones"].append(f"valor '{val_real}' en '{col}' ('{palabra}'→'{val_real}', {score}%)")
                break
            if col == res["col_estado"] and not res["val_estado"]:
                res["val_estado"] = val_real
                if score < 95:
                    res["interpretaciones"].append(f"INTERPRETACIÓN: '{palabra}' → estado '{val_real}' ({score}%)")
            elif not res["valor_filtro"]:
                res["col_agrupacion"] = col
                res["valor_filtro"] = val_real
                if score < 95:
                    res["interpretaciones"].append(f"INTERPRETACIÓN: '{palabra}' → '{val_real}' en '{col}' ({score}%)")
            break
    return res


# ─────────────────────────────────────────
# DETECCIÓN DE INTENT
# ─────────────────────────────────────────

def _detectar_intent(p: str):
    PATRONES = {
        "suma": ["cuánto gastamos", "cuanto gastamos", "total gasto", "suma de",
                 "cuánto se gastó", "cuanto se gasto", "gasto total", "total de",
                 "cuánto cuesta", "cuanto cuesta", "sumar", "suma total",
                 "sumatoria", "sumatoria de", "suma total de", "suma por",
                 "total por", "cuanto suma", "cuánto suma", "sumame", "súmame",
                 "calcula", "calcular", "calcula el", "dame el total",
                 "dame la suma", "cuánto es", "cuanto es"],
        "promedio": ["promedio", "media", "average", "avg", "en promedio", "de media"],
        "ranking": ["mejor", "peor", "top", "mayor", "menor", "más eficiente", "mas eficiente",
                    "más rentable", "mas rentable", "más convierte", "mas convierte",
                    "más vendedor", "mas vendedor", "el que más", "el que menos",
                    "con mas", "con más", "cual tiene mas", "cual tiene más",
                    "cual es el", "cuál es el", "con mayor", "con menor"],
        "comparacion": ["vs", "versus", "compara", "diferencia entre", "contra", "comparar"],
        "agrupacion": ["agrupa", "agrupar", "desglose", "desglos", "por cada", "resumen por",
                       "total de cada", "cuántos hay", "cuantos hay", "muéstrame", "muestrame",
                       "conteo de", "distribución", "distribucion", "breakdown",
                       "categorias", "categorías", "por estado", "por campaña", "por campana",
                       "por adset", "resumen de"],
        "conteo": ["cuántos", "cuantas", "cuántas", "cuantos", "cuenta", "total de",
                   "número de", "numero de", "hay en", "tenemos", "existen", "registros",
                   "llegaron", "llegaron en", "entraron", "se registraron",
                   "vinieron", "captamos", "capturamos", "tenemos en"],
    }
    for intent, kws in PATRONES.items():
        if any(k in p for k in kws):
            return intent
    return None


# ─────────────────────────────────────────
# FILTRO TEMPORAL
# ─────────────────────────────────────────

MESES_MAP = {
    "enero": 1, "january": 1, "jan": 1, "febrero": 2, "february": 2, "feb": 2,
    "marzo": 3, "march": 3, "mar": 3, "abril": 4, "april": 4, "apr": 4,
    "mayo": 5, "may": 5, "junio": 6, "june": 6, "jun": 6,
    "julio": 7, "july": 7, "jul": 7, "agosto": 8, "august": 8, "aug": 8,
    "septiembre": 9, "september": 9, "sep": 9, "octubre": 10, "october": 10, "oct": 10,
    "noviembre": 11, "november": 11, "nov": 11,
    "diciembre": 12, "december": 12, "dic": 12, "dec": 12,
}


def _detectar_filtro_temporal(p: str):
    res = {"mes": None, "año": None, "periodo": None}
    for nombre, num in MESES_MAP.items():
        if nombre in p:
            res["mes"] = num
            break
    m = re.search(r"\b(202\d)\b", p)
    if m:
        res["año"] = int(m.group(1))
    if "último mes" in p or "mes pasado" in p or "mes anterior" in p:
        res["periodo"] = "mes_anterior"
    elif "esta semana" in p or "semana actual" in p:
        res["periodo"] = "semana_actual"
    elif "último trimestre" in p or "trimestre pasado" in p:
        res["periodo"] = "trimestre_anterior"
    elif "este mes" in p or "mes actual" in p:
        res["periodo"] = "mes_actual"
    elif "este año" in p or "año actual" in p:
        res["periodo"] = "año_actual"
    return res if any(v is not None for v in res.values()) else None


def _aplicar_filtro_temporal(df: pd.DataFrame, col_fecha: str, filtro: dict):
    import datetime, calendar
    df = df.copy()
    try:
        df[col_fecha] = pd.to_datetime(df[col_fecha], errors="coerce")
    except Exception:
        return df, f"(fecha no parseable en '{col_fecha}')"
    n_nat = df[col_fecha].isna().sum()
    df = df.dropna(subset=[col_fecha])
    hoy = datetime.date.today()
    if filtro.get("periodo") == "mes_anterior":
        p1 = (hoy.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
        p2 = hoy.replace(day=1) - datetime.timedelta(days=1)
        df = df[(df[col_fecha].dt.date >= p1) & (df[col_fecha].dt.date <= p2)]
        desc = f"mes anterior ({p1.strftime('%B %Y')})"
    elif filtro.get("periodo") == "mes_actual":
        df = df[df[col_fecha].dt.date >= hoy.replace(day=1)]
        desc = "mes actual"
    elif filtro.get("periodo") == "semana_actual":
        df = df[df[col_fecha].dt.date >= hoy - datetime.timedelta(days=hoy.weekday())]
        desc = "semana actual"
    elif filtro.get("periodo") == "trimestre_anterior":
        mes = hoy.month
        q = (mes - 1) // 3
        mi = q * 3 + 1 if q > 0 else 10
        ai = hoy.year if q > 0 else hoy.year - 1
        mf = mi + 2
        ini = datetime.date(ai, mi, 1)
        fin = datetime.date(ai, mf, calendar.monthrange(ai, mf)[1])
        df = df[(df[col_fecha].dt.date >= ini) & (df[col_fecha].dt.date <= fin)]
        desc = "trimestre anterior"
    elif filtro.get("periodo") == "año_actual":
        df = df[df[col_fecha].dt.year == hoy.year]
        desc = f"año {hoy.year}"
    elif filtro.get("mes") and filtro.get("año"):
        df = df[(df[col_fecha].dt.month == filtro["mes"]) & (df[col_fecha].dt.year == filtro["año"])]
        desc = f"mes {filtro['mes']}/{filtro['año']}"
    elif filtro.get("mes"):
        df = df[df[col_fecha].dt.month == filtro["mes"]]
        inv = {v: k for k, v in MESES_MAP.items() if len(k) > 4 and k.isalpha()}
        desc = inv.get(filtro["mes"], str(filtro["mes"]))
    elif filtro.get("año"):
        df = df[df[col_fecha].dt.year == filtro["año"]]
        desc = f"año {filtro['año']}"
    else:
        desc = "período no identificado"
    adv = f" (CALIDAD: {n_nat} fechas inválidas excluidas)" if n_nat > 0 else ""
    return df, desc + adv


# ─────────────────────────────────────────
# ADVERTENCIAS DE CALIDAD
# ─────────────────────────────────────────

def _advertencias_calidad(df: pd.DataFrame, col: str, interpretaciones: list = None) -> list:
    adv = list(interpretaciones or [])
    if col not in df.columns:
        return adv + [f"ADVERTENCIA: columna '{col}' no existe en el dataset."]
    n_nulos = df[col].isna().sum()
    if n_nulos > 0:
        adv.append(f"CALIDAD: '{col}' tiene {n_nulos} nulos ({n_nulos/len(df)*100:.1f}%) — excluidos.")
    if pd.api.types.is_numeric_dtype(df[col]):
        n_neg = (df[col] < 0).sum()
        if n_neg > 0:
            adv.append(f"CALIDAD: '{col}' tiene {n_neg} valores negativos (mín: {df[col].min():,.2f}) — pueden distorsionar sumas/promedios.")
    else:
        vals = df[col].dropna().unique()
        norms = [_normalizar(str(v)) for v in vals]
        if len(norms) != len(set(norms)):
            adv.append(f"CALIDAD: '{col}' tiene posibles duplicados con distinto formato.")
    return adv


# ─────────────────────────────────────────
# CAPA 3 — ENGINE PRINCIPAL
# ─────────────────────────────────────────

# Patrones de preguntas sobre schema — no deben ir al fuzzy matcher
_SCHEMA_PATTERNS = [
    "lista de columnas", "las columnas", "columnas del", "columnas de la",
    "que columnas", "qué columnas", "cuales columnas", "cuáles columnas",
    "que campos", "qué campos", "los campos", "lista de campos",
    "estructura del", "estructura de la", "schema", "esquema",
    "que tiene el dataset", "qué tiene el dataset",
]

def ejecutar_query_analitica(pregunta: str, df: pd.DataFrame, confirmado: bool = False):
    """
    Detecta intent analítico y ejecuta pandas contra el df real.
    Retorna string para inyectar al LLM, o None si no hay intent claro.
    """
    p = _normalizar(pregunta)
    palabras = p.split()

    # Preguntas sobre schema — no entrar al fuzzy, dejar que el LLM responda
    # con el schema que ya tiene en contexto
    if any(pat in p for pat in _SCHEMA_PATTERNS):
        return None

    intent = _detectar_intent(p)
    if intent is None:
        return None

    # Normalizar columnas de estado a lowercase — resuelve LEAD vs lead vs Lead
    df = df.copy()
    for col in df.columns:
        if df[col].dtype == object:
            if _normalizar(col) in {"estado", "status", "etapa", "fase", "pipeline", "stage"}:
                df[col] = df[col].str.lower().str.strip()

    schema = _leer_schema(df)
    det = _detectar_todo(palabras, df, schema)

    col_agr    = det["col_agrupacion"]
    col_num    = det["col_numerica"]
    val_filtro = det["valor_filtro"]
    col_est    = det["col_estado"]
    val_est    = det["val_estado"]
    interps    = det["interpretaciones"]

    if det["confirmaciones"]:
        lista = " y ".join(det["confirmaciones"])
        return f"CONFIRMAR: ¿quisiste decir {lista}? Responde 'sí' para confirmar."

    filtro_t = _detectar_filtro_temporal(p)
    df_f = df
    desc_t = ""

    if filtro_t and schema["fecha"]:
        df_f, desc_t = _aplicar_filtro_temporal(df, schema["fecha"], filtro_t)
        if len(df_f) == 0:
            try:
                tmp = df.copy()
                tmp[schema["fecha"]] = pd.to_datetime(tmp[schema["fecha"]], errors="coerce")
                rango = f"{tmp[schema['fecha']].min().date()} a {tmp[schema['fecha']].max().date()}"
            except Exception:
                rango = "desconocido"
            return f"RESULTADO EXACTO (pandas): No hay datos para '{desc_t}'. El dataset cubre {rango}."

    col_id = df_f.columns[0]
    pt = f" en {desc_t}" if desc_t else ""
    res = []

    # ── SUMA ──────────────────────────────────────────────────
    if intent == "suma" and col_num:
        if col_agr:
            g = df_f.groupby(col_agr)[col_num].sum().reset_index().sort_values(col_num, ascending=False)
            res.append(f"RESULTADO EXACTO (pandas) — suma de '{col_num}' por '{col_agr}'{pt}:")
            res.append(g.to_string(index=False))
            res.append(f"TOTAL GENERAL: {df_f[col_num].sum():,.2f}")
        else:
            res.append(f"RESULTADO EXACTO (pandas) — suma de '{col_num}'{pt}: {df_f[col_num].sum():,.2f} (registros: {len(df_f)}, nulos: {df_f[col_num].isna().sum()})")
        res += _advertencias_calidad(df_f, col_num, interps)
        return "\n".join(res)

    # ── PROMEDIO ──────────────────────────────────────────────
    if intent == "promedio" and col_num:
        if col_agr:
            g = df_f.groupby(col_agr)[col_num].agg(["mean","min","max","count"]).round(2).reset_index().sort_values("mean", ascending=False)
            g.columns = [col_agr, "promedio", "mínimo", "máximo", "registros"]
            res.append(f"RESULTADO EXACTO (pandas) — promedio de '{col_num}' por '{col_agr}'{pt}:")
            res.append(g.to_string(index=False))
        else:
            s = df_f[col_num].dropna()
            res.append(f"RESULTADO EXACTO (pandas) — estadísticas de '{col_num}'{pt}:")
            res.append(f"  Promedio: {s.mean():,.2f} | Mínimo: {s.min():,.2f} | Máximo: {s.max():,.2f} | Registros: {len(s)}")
        res += _advertencias_calidad(df_f, col_num, interps)
        return "\n".join(res)

    # ── RANKING ───────────────────────────────────────────────
    if intent == "ranking" and col_agr:
        if col_est and val_est:
            # Cruce col_agr × val_estado — "adset con más perdidos", "campaña con más ventas"
            filtrado = df_f[df_f[col_est] == val_est]
            totales  = df_f.groupby(col_agr).size().reset_index(name="total")
            conteo   = filtrado.groupby(col_agr).size().reset_index(name=val_est)
            ranking  = totales.merge(conteo, on=col_agr, how="left").fillna(0)
            ranking[val_est] = ranking[val_est].astype(int)
            ranking["tasa_%"] = (ranking[val_est] / ranking["total"] * 100).round(1)
            res.append(f"RESULTADO EXACTO (pandas) — ranking '{val_est}' por '{col_agr}'{pt}:")
            res.append(ranking.sort_values(val_est, ascending=False).to_string(index=False))
            res.append("NOTA ANALÍTICA: Volumen y tasa son métricas distintas. Tasa alta con volumen bajo puede ser estadísticamente engañoso.")
        elif col_est:
            # Estado detectado pero sin valor específico — ranking con desglose completo
            mv = _match_valor("venta", col_est, df_f, umbral=70)
            val_v = mv[0] if mv else None
            if val_v:
                ventas = df_f[df_f[col_est] == val_v].groupby(col_agr).size().reset_index(name="ventas")
                totales = df_f.groupby(col_agr).size().reset_index(name="total")
                ranking = ventas.merge(totales, on=col_agr, how="right").fillna(0)
                ranking["ventas"] = ranking["ventas"].astype(int)
                ranking["tasa_%"] = (ranking["ventas"] / ranking["total"] * 100).round(1)
                res.append(f"RESULTADO EXACTO (pandas) — ranking por '{val_v}' en '{col_agr}'{pt}:")
                res.append(ranking.sort_values("ventas", ascending=False).to_string(index=False))
                res.append("NOTA ANALÍTICA: Volumen y tasa son métricas distintas. Tasa alta con volumen bajo puede ser estadísticamente engañoso.")
            else:
                g = df_f.groupby(col_agr).size().reset_index(name="total").sort_values("total", ascending=False)
                res.append(f"RESULTADO EXACTO (pandas) — ranking por volumen en '{col_agr}'{pt}:")
                res.append(g.to_string(index=False))
        elif col_num:
            g = df_f.groupby(col_agr)[col_num].mean().reset_index().sort_values(col_num, ascending=False)
            res.append(f"RESULTADO EXACTO (pandas) — ranking por '{col_num}' en '{col_agr}'{pt}:")
            res.append(g.to_string(index=False))
        else:
            g = df_f.groupby(col_agr).size().reset_index(name="total").sort_values("total", ascending=False)
            res.append(f"RESULTADO EXACTO (pandas) — ranking por volumen en '{col_agr}'{pt}:")
            res.append(g.to_string(index=False))
        res += _advertencias_calidad(df_f, col_agr, interps)
        return "\n".join(res)

    # ── COMPARACION ───────────────────────────────────────────
    if intent == "comparacion" and col_agr:
        if col_est:
            estados = df_f[col_est].dropna().unique()
            agg = {"total": (col_id, "count")}
            for e in estados:
                agg[str(e)] = (col_est, lambda x, e=e: (x == e).sum())
            g = df_f.groupby(col_agr).agg(**agg).reset_index()
        else:
            g = df_f.groupby(col_agr).size().reset_index(name="total")
        res.append(f"RESULTADO EXACTO (pandas) — comparación por '{col_agr}'{pt}:")
        res.append(g.to_string(index=False))
        res += _advertencias_calidad(df_f, col_agr, interps)
        return "\n".join(res)

    # ── AGRUPACION ────────────────────────────────────────────
    if intent == "agrupacion":
        col_grp = col_agr or col_est
        if not col_grp:
            return None
        if col_est and col_grp != col_est and col_est in df_f.columns:
            estados = df_f[col_est].dropna().unique()
            agg = {"total": (col_id, "count")}
            for e in estados[:6]:
                agg[str(e)] = (col_est, lambda x, e=e: (x == e).sum())
            g = df_f.groupby(col_grp).agg(**agg).reset_index()
            mv = _match_valor("venta", col_est, df_f, umbral=70)
            if mv and str(mv[0]) in g.columns:
                g["tasa_venta_%"] = (g[str(mv[0])] / g["total"] * 100).round(1)
        else:
            g = df_f.groupby(col_grp).size().reset_index(name="total").sort_values("total", ascending=False)
        res.append(f"RESULTADO EXACTO (pandas) — agrupación por '{col_grp}'{pt}:")
        res.append(g.to_string(index=False))
        res += _advertencias_calidad(df_f, col_grp, interps)
        return "\n".join(res)

    # ── CONTEO ────────────────────────────────────────────────
    if intent == "conteo":
        if val_filtro and col_agr:
            subset = df_f[df_f[col_agr] == val_filtro]
            if val_est and col_est in df_f.columns:
                n_est = len(subset[subset[col_est] == val_est])
                n_tot = len(subset)
                res.append(
                    f"RESULTADO EXACTO (pandas): '{val_filtro}' en '{col_agr}' → total: {n_tot} | '{val_est}': {n_est} ({n_est/n_tot*100:.1f}%)"
                    if n_tot > 0 else f"'{val_filtro}' en '{col_agr}' → 0 registros"
                )
            else:
                res.append(f"RESULTADO EXACTO (pandas): '{val_filtro}' en '{col_agr}' = {len(subset)} registros{pt}.")
            res += _advertencias_calidad(df_f, col_agr, interps)
            return "\n".join(res)

        if val_est and col_est and not col_agr:
            n = len(df_f[df_f[col_est] == val_est])
            res.append(f"RESULTADO EXACTO (pandas){pt}: '{val_est}' = {n} registros ({n/len(df_f)*100:.1f}% del total)")
            res += _advertencias_calidad(df_f, col_est, interps)
            return "\n".join(res)

        if filtro_t and schema["fecha"]:
            res.append(f"RESULTADO EXACTO (pandas){pt}: {len(df_f)} registros totales")
            if col_est and col_est in df_f.columns:
                res.append(f"Desglose por {col_est}:\n{df_f[col_est].value_counts().to_string()}")
            res += (interps or [])
            return "\n".join(res)

        if col_agr:
            g = df_f.groupby(col_agr).size().reset_index(name="total").sort_values("total", ascending=False)
            res.append(f"RESULTADO EXACTO (pandas) — conteo por '{col_agr}'{pt}:")
            res.append(g.to_string(index=False))
            res += _advertencias_calidad(df_f, col_agr, interps)
            return "\n".join(res)

    return None
