# query_engine.py — Adly · Data-Buddy
# v3 — Text-to-Pandas con planner LLM + sandbox seguro
#
# Arquitectura:
#   CAPA 1 — Schema Reader  : lee el df real, sin hardcodeo
#   CAPA 2 — Planner LLM   : genera código pandas desde pregunta + schema
#   CAPA 3 — Sandbox        : exec() con namespace restringido + timeout
#   CAPA 4 — Validador      : verifica resultado antes de retornar
#   CAPA 5 — Re-prompt      : si falla, corrige con el error (máx 2 intentos)
#
# Firma pública — no cambiar:
#   ejecutar_query_analitica(pregunta: str, df: pd.DataFrame) -> str | None

import re
import json
import os
import unicodedata
import pandas as pd
import threading


# ─────────────────────────────────────────
# CAPA 1 — SCHEMA READER
# ─────────────────────────────────────────

def _leer_schema(df: pd.DataFrame) -> dict:
    schema = {"total_filas": len(df), "columnas": {}}
    for col in df.columns:
        info = {"tipo": str(df[col].dtype), "nulos": int(df[col].isna().sum())}
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            info["semantico"] = "fecha"
            try:
                info["rango"] = f"{df[col].min().date()} a {df[col].max().date()}"
            except Exception:
                pass
        elif pd.api.types.is_numeric_dtype(df[col]):
            info["semantico"] = "numerica"
            s = df[col].dropna()
            if len(s) > 0:
                info["min"]   = round(float(s.min()), 2)
                info["max"]   = round(float(s.max()), 2)
                info["media"] = round(float(s.mean()), 2)
        else:
            vals = df[col].dropna().unique()
            if any(p in col.lower() for p in ["fecha", "date", "ts", "timestamp"]):
                info["semantico"] = "fecha_str"
                info["ejemplo"]   = str(vals[0]) if len(vals) > 0 else ""
            else:
                info["semantico"] = "categorica"
                info["valores_unicos"] = [str(v) for v in vals[:15]]
                info["n_unicos"] = int(df[col].nunique())
        schema["columnas"][col] = info
    return schema


def _schema_para_prompt(schema: dict) -> str:
    lineas = [f"Dataset: {schema['total_filas']} filas\n", "Columnas disponibles:"]
    for col, info in schema["columnas"].items():
        sem = info.get("semantico", "?")
        if sem == "numerica":
            lineas.append(f"  - {col} [numerica] min={info.get('min','?')} max={info.get('max','?')} media={info.get('media','?')}")
        elif sem == "categorica":
            vals = ", ".join(info.get("valores_unicos", [])[:10])
            lineas.append(f"  - {col} [categorica, {info.get('n_unicos','?')} unicos] valores: {vals}")
        elif sem in ("fecha", "fecha_str"):
            extra = info.get("rango", info.get("ejemplo", ""))
            lineas.append(f"  - {col} [fecha] {extra}")
        else:
            lineas.append(f"  - {col} [{sem}]")
    return "\n".join(lineas)


# ─────────────────────────────────────────
# CAPA 2 — PLANNER LLM
# ─────────────────────────────────────────

_PLANNER_SYSTEM = """Eres un experto en analisis de datos con pandas. Tu trabajo es generar codigo Python/pandas que responda preguntas analiticas sobre un DataFrame llamado `df`.

REGLAS ESTRICTAS:
1. Siempre asigna el resultado final a la variable `result`
2. `result` debe ser: DataFrame, Series, numero escalar, o string
3. Solo puedes usar: df, pd, len, round, str, int, float, list, dict, sum, min, max, sorted, enumerate, zip
4. PROHIBIDO: import, open, os, sys, exec, eval, __import__, requests, cualquier I/O
5. Si la pregunta implica fechas, convierte con pd.to_datetime(..., errors='coerce')
6. Usa los valores exactos del schema para filtrar categorias
7. Para rankings, ordena descendente por la metrica principal
8. Maximo 8 lineas de codigo
9. Responde SOLO con el codigo, sin explicaciones, sin markdown, sin ```

EJEMPLOS:
Pregunta: cual campana tiene mas ventas?
result = df[df['estado'] == 'venta'].groupby('campana').size().reset_index(name='ventas').sort_values('ventas', ascending=False)

Pregunta: cual anuncio trae mas plata?
result = df.groupby('ad')['valor_venta'].sum().reset_index(name='ingreso_total').sort_values('ingreso_total', ascending=False)

Pregunta: cual anuncio convierte mejor en retargeting?
camp = df[df['campana'].str.contains('etargeting', case=False, na=False)]
result = camp[camp['estado'] == 'venta'].groupby('ad').size().reset_index(name='ventas')
totales = camp.groupby('ad').size().reset_index(name='total')
result = result.merge(totales, on='ad')
result['tasa_%'] = (result['ventas'] / result['total'] * 100).round(1)
result = result.sort_values('tasa_%', ascending=False)

Pregunta: compara costo por lead entre adsets
result = df.groupby('adset')['costo_lead'].mean().reset_index(name='cpl_promedio').sort_values('cpl_promedio')

Pregunta: como me fue en febrero vs marzo?
df['_fecha'] = pd.to_datetime(df['fecha_creacion'], errors='coerce')
feb = df[df['_fecha'].dt.month == 2]
mar = df[df['_fecha'].dt.month == 3]
result = pd.DataFrame({'mes': ['Febrero', 'Marzo'], 'leads': [len(feb), len(mar)], 'ventas': [(feb['estado'] == 'venta').sum(), (mar['estado'] == 'venta').sum()]})"""


def _llamar_planner(pregunta: str, schema_texto: str, error_previo: str = None) -> str | None:
    """Llama a Gemini para generar codigo pandas."""
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not gemini_key:
        print("[PLANNER] sin GEMINI_API_KEY")
        return None

    contenido = f"{schema_texto}\n\nPregunta: {pregunta}"
    if error_previo:
        contenido += f"\n\nINTENTO ANTERIOR FALLO: {error_previo}\nCorrige el codigo."

    try:
        import google.generativeai as genai
        genai.configure(api_key=gemini_key)
        model  = genai.GenerativeModel("gemini-2.5-flash")
        prompt = f"{_PLANNER_SYSTEM}\n\n{contenido}"
        resp   = model.generate_content(prompt)
        codigo = resp.text.strip()
        codigo = re.sub(r"```(?:python)?\s*|\s*```", "", codigo).strip()
        return codigo
    except Exception as e:
        print(f"[PLANNER] Gemini error: {type(e).__name__}: {e}")
        return None


# ─────────────────────────────────────────
# CAPA 3 — SANDBOX
# ─────────────────────────────────────────

_BUILTINS_PERMITIDOS = {
    "len": len, "round": round, "str": str, "int": int, "float": float,
    "list": list, "dict": dict, "sum": sum, "min": min, "max": max,
    "sorted": sorted, "enumerate": enumerate, "zip": zip,
    "True": True, "False": False, "None": None,
}

def _ejecutar_sandbox(codigo: str, df: pd.DataFrame, timeout_s: int = 5) -> tuple:
    namespace = {
        "__builtins__": _BUILTINS_PERMITIDOS,
        "df": df.copy(),
        "pd": pd,
        "result": None,
    }
    resultado_container = [None]
    error_container     = [None]

    def _run():
        try:
            exec(codigo, namespace)
            resultado_container[0] = namespace.get("result")
        except Exception as e:
            error_container[0] = str(e)

    hilo = threading.Thread(target=_run)
    hilo.start()
    hilo.join(timeout=timeout_s)

    if hilo.is_alive():
        return None, f"Timeout — codigo tardo mas de {timeout_s}s"

    return resultado_container[0], error_container[0]


# ─────────────────────────────────────────
# CAPA 4 — VALIDADOR
# ─────────────────────────────────────────

def _validar_resultado(result) -> tuple:
    if result is None:
        return False, "result es None"
    if isinstance(result, pd.DataFrame):
        if result.empty:
            return False, "DataFrame vacio"
        if result.select_dtypes(include="number").isna().all().all():
            return False, "DataFrame todo NaN"
        return True, "ok"
    if isinstance(result, pd.Series):
        return (False, "Serie vacia") if result.empty else (True, "ok")
    if isinstance(result, (int, float)):
        return (False, "NaN") if pd.isna(result) else (True, "ok")
    if isinstance(result, str):
        return (False, "string vacio") if not result.strip() else (True, "ok")
    return True, "ok"


# ─────────────────────────────────────────
# CAPA 5 — SERIALIZADOR
# ─────────────────────────────────────────

def _serializar_resultado(result, pregunta: str = "") -> str:
    if isinstance(result, pd.DataFrame):
        result = result.where(pd.notnull(result), None)
        filas  = len(result)
        texto  = result.to_string(index=False, max_rows=20)
        nota   = f"\n(mostrando {min(filas,20)} de {filas} filas)" if filas > 20 else ""
        return f"RESULTADO EXACTO (pandas):\n{texto}{nota}"
    if isinstance(result, pd.Series):
        return f"RESULTADO EXACTO (pandas):\n{result.dropna().to_string()}"
    if isinstance(result, (int, float)):
        return f"RESULTADO EXACTO (pandas): {result:,.2f}"
    return f"RESULTADO EXACTO (pandas): {str(result)}"


# ─────────────────────────────────────────
# PUNTO DE ENTRADA PÚBLICO
# ─────────────────────────────────────────

_SCHEMA_PATTERNS = [
    "lista de columnas", "las columnas", "columnas del", "que columnas",
    "qué columnas", "que campos", "qué campos", "schema", "esquema",
]

_CONVERSACIONAL_PATTERNS = [
    "hola", "buenos", "gracias", "como estas", "que puedes", "ayuda",
]

def ejecutar_query_analitica(pregunta: str, df: pd.DataFrame, confirmado: bool = False) -> str | None:
    p = pregunta.lower().strip()

    if any(pat in p for pat in _SCHEMA_PATTERNS):
        return None
    if any(pat in p for pat in _CONVERSACIONAL_PATTERNS):
        return None
    if len(p.split()) < 3:
        return None

    schema     = _leer_schema(df)
    schema_txt = _schema_para_prompt(schema)

    print(f"[PLANNER] pregunta: '{pregunta}'")
    print(f"[PLANNER] GEMINI_API_KEY: {bool(os.getenv('GEMINI_API_KEY','').strip())}")

    error_previo = None
    for intento in range(2):
        codigo = _llamar_planner(pregunta, schema_txt, error_previo)
        if not codigo:
            print(f"[PLANNER] intento {intento+1} — planner retornó None")
            return None

        print(f"[PLANNER] intento {intento+1} — código:\n{codigo}\n{'─'*40}")

        resultado, error = _ejecutar_sandbox(codigo, df)
        print(f"[SANDBOX] error={error} tipo={type(resultado).__name__}")

        if error:
            error_previo = error
            continue

        es_valido, razon = _validar_resultado(resultado)
        print(f"[VALIDADOR] valido={es_valido} razon={razon}")

        if not es_valido:
            error_previo = razon
            continue

        return _serializar_resultado(resultado, pregunta)

    print(f"[PLANNER] ambos intentos fallaron")
    return None
