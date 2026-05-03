from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from datetime import datetime
from io import StringIO
import threading
import re

from rich.console import Console

# Stripea tags residuales de Rich: [color(214)], [/bold], etc.
_RICH_TAG_RE = re.compile(r'\[/?[a-zA-Z][^\[\]]*\]|\[color\(\d+\)\]|\[/color\(\d+\)\]')

def _strip_rich(text: str) -> str:
    if not text:
        return text
    cleaned = _RICH_TAG_RE.sub('', text)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()

from src.api.state import state
from src.api.limiter import limiter
from src.processing.query_engine import ejecutar_query_analitica
from src.api.command_bridge import despachar_comando


# ── Parser de tablas ASCII de Rich a estructuradas ────────────────────────────

def _rich_to_table(output: str) -> list | None:
    """
    Intenta parsear una tabla ASCII de Rich a list[dict] para DataTable.
    Detecta líneas de datos entre las líneas de separadores (─).
    Retorna None si no puede parsear.
    """
    if not output:
        return None

    lineas = output.split('\n')
    datos = []
    headers = None

    for linea in lineas:
        # Saltar bordes de caja
        if any(c in linea for c in '┌┐└┘'):
            continue
        # Saltar separadores
        if '─' in linea and '│' not in linea:
            continue
        # Extraer contenido entre │
        if '│' in linea:
            contenido = linea.strip().strip('│').strip()
            if not contenido:
                continue
            # Separar columnas por 2+ espacios
            cols = [c.strip() for c in re.split(r'\s{2,}', contenido) if c.strip()]
            if not cols:
                continue
            # Primera fila válida = headers
            if headers is None:
                headers = cols
                continue
            # Línea de separación entre header y datos
            if all(c.startswith('─') or c == '' for c in cols):
                continue
            # Fila de datos
            if len(cols) >= len(headers):
                fila = {}
                for i, h in enumerate(headers):
                    fila[h] = cols[i] if i < len(cols) else '—'
                datos.append(fila)

    return datos if len(datos) > 0 and headers else None

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Lock por thread — protege el monkey-patch del console global
_console_lock = threading.Lock()


# ── capturar_cmd ─────────────────────────────────────────────────────────────
# Solución universal: intercepta el console global de commands.py/theme.py,
# ejecuta cualquier cmd_X, captura el output como string plano.
# El CLI nunca se ve afectado — el patch dura solo durante la ejecución.

def capturar_cmd(fn, *args, **kwargs) -> tuple[str | None, str | None]:
    """
    Ejecuta fn(*args, **kwargs) capturando el output de Rich como string.
    Retorna (output_str, ctx_str):
      - output_str: lo que Rich habría imprimido (texto plano)
      - ctx_str:    el return de la función (contexto para el engine)
    Ambos pueden ser None si la función no produce output o no retorna nada.
    """
    buffer  = StringIO()
    capture = Console(file=buffer, no_color=True, highlight=False,
                      markup=False, width=200)

    import interfaces.cli.commands as _cmds
    import interfaces.cli.theme    as _theme

    with _console_lock:
        # Guardar consoles originales
        orig_cmds  = _cmds.console
        orig_theme = _theme.console

        # Sustituir por el console de captura
        _cmds.console  = capture
        _theme.console = capture

        try:
            ctx = fn(*args, **kwargs)
        finally:
            # Restaurar siempre, aunque explote
            _cmds.console  = orig_cmds
            _theme.console = orig_theme

    output = _strip_rich(buffer.getvalue())
    return (output or None, ctx or None)


# ── Helpers de mensaje ────────────────────────────────────────────────────────

def _bot_msg(content: str, confidence: float = 1.0,
             freshness: str = "ahora", note: str = "",
             table=None) -> dict:
    msg = {
        "id":              f"msg_bot_{datetime.utcnow().timestamp()}",
        "role":            "bot",
        "content":         content,
        "timestamp":       datetime.utcnow().isoformat() + "Z",
        "confidence":      confidence,
        "data_freshness":  freshness,
        "confidence_note": note,
    }
    if table:
        msg["table"] = table
    return msg


def _user_msg(text: str) -> dict:
    return {
        "id":        f"msg_user_{datetime.utcnow().timestamp()}",
        "role":      "user",
        "content":   text,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


def _save_and_return(analysis_id: str, bot: dict) -> dict:
    state.messages[analysis_id].append(bot)
    return bot


# ── Registro universal de comandos ───────────────────────────────────────────
# Agregar un comando nuevo = una línea aquí. Nada más.
#
# Formato: "/cmd": { "fn": función, "args": lambda df, partes: [...] }
# partes = text.split() — para comandos con argumentos como /embudo Campaña_X

def _build_registry(df, partes: list) -> dict:
    """
    Construye el registro de comandos con el df y partes actuales.
    Se llama en runtime para tener df y args frescos.
    """
    from interfaces.cli.commands import (
        cmd_rfm, cmd_cohorts, cmd_embudo, cmd_velocidad,
        cmd_rentabilidad, cmd_columnas, cmd_nulos, cmd_describe,
        cmd_outliers, cmd_correlacion,
        cmd_unicos, cmd_rango, cmd_top,
    )
    from src.api.command_bridge import bridge_head, bridge_sample

    col_arg  = partes[1] if len(partes) > 1 else ""
    n_arg    = int(partes[1]) if len(partes) > 1 and partes[1].isdigit() else 5
    top_col  = partes[1] if len(partes) > 1 else ""
    top_n    = int(partes[2]) if len(partes) > 2 and partes[2].isdigit() else 10
    emb_camp = " ".join(partes[1:]) if len(partes) > 1 else ""

    return {
        # Modelos
        "/rfm":           lambda: capturar_cmd(cmd_rfm,          df),
        "/cohorts":       lambda: capturar_cmd(cmd_cohorts,       df),
        "/embudo":        lambda: capturar_cmd(cmd_embudo,        df, emb_camp),
        "/velocidad":     lambda: capturar_cmd(cmd_velocidad,     df),
        "/rentabilidad":  lambda: capturar_cmd(cmd_rentabilidad,  df),
        # Exploración
        "/columnas":      lambda: capturar_cmd(cmd_columnas,      df),
        "/nulos":         lambda: capturar_cmd(cmd_nulos,         df),
        "/describe":      lambda: capturar_cmd(cmd_describe,      df),
        # /head y /sample retornan dict estructurado directamente
        "/head":          lambda: (None, bridge_head(df, n_arg)),
        "/sample":        lambda: (None, bridge_sample(df, n_arg)),
        "/outliers":      lambda: capturar_cmd(cmd_outliers,      df, col_arg),
        "/correlacion":   lambda: capturar_cmd(cmd_correlacion,   df),
        "/unicos":        lambda: capturar_cmd(cmd_unicos,        df, col_arg),
        "/rango":         lambda: capturar_cmd(cmd_rango,         df, col_arg),
        "/top":           lambda: capturar_cmd(cmd_top,           df, top_col, top_n),
    }


class ChatMessage(BaseModel):
    analysis_id: str
    message: str


@router.post("")
@limiter.limit("30/minute")
async def send_message(request: Request, payload: ChatMessage):
    analysis_id = payload.analysis_id
    text        = payload.message.strip()

    if analysis_id not in state.engines:
        raise HTTPException(
            status_code=404,
            detail="Análisis no encontrado o el motor no fue inicializado."
        )

    engine = state.engines[analysis_id]
    df     = state.dataframes.get(analysis_id)

    if analysis_id not in state.messages:
        state.messages[analysis_id] = []
    state.messages[analysis_id].append(_user_msg(text))

    if not hasattr(state, "_pending_confirms"):
        state._pending_confirms = {}
    pending_key = f"{analysis_id}_pending_query"

    # ── 1. CONFIRMAR pendiente ────────────────────────────────────────────────
    if text.lower() in {"sí", "si", "yes", "s", "ok", "confirmar"}:
        query_pendiente = state._pending_confirms.get(pending_key)
        if query_pendiente and df is not None:
            resultado = ejecutar_query_analitica(query_pendiente, df, confirmado=True)
            state._pending_confirms.pop(pending_key, None)
            if resultado:
                engine.agregar_contexto_comando("query_confirmada", resultado)
            respuesta = engine.chat(query_pendiente)
            return _save_and_return(analysis_id, _bot_msg(
                content    = respuesta.respuesta,
                confidence = respuesta.confianza,
                freshness  = getattr(respuesta, "data_freshness", "ahora"),
                note       = getattr(respuesta, "confidence_note", ""),
            ))

    if text.lower() in {"no", "cancelar", "cancel"}:
        state._pending_confirms.pop(pending_key, None)
        return _save_and_return(analysis_id,
            _bot_msg("Ok, cancelado. ¿En qué más puedo ayudarte?"))

    # ── 2. Comandos / ────────────────────────────────────────────────────────
    if text.startswith("/"):
        partes   = text.strip().split()
        cmd_base = partes[0].lower()

        # Normalizar aliases en español / con tilde
        _ALIASES = {
            "/cohortes":  "/cohorts",
            "/métricas":  "/metricas",
            "/metricas":  "/metricas",   # ya canónico pero asegura lower
            "/correlación": "/correlacion",
            "/descripción": "/describe",
        }
        cmd_base = _ALIASES.get(cmd_base, cmd_base)

        # /ayuda — manejado por el bridge (no necesita df)
        if cmd_base == "/ayuda":
            flag = partes[1] if len(partes) > 1 else ""
            from src.api.command_bridge import bridge_ayuda
            return _save_and_return(analysis_id, _bot_msg(
                content   = bridge_ayuda(flag),
                freshness = "datos locales",
                note      = "Referencia de comandos",
            ))

        # Comandos de limpieza — mutan el df, manejar por bridge
        if cmd_base in {"/limpiar_duplicados", "/rellenar", "/eliminar_por", "/exportar"}:
            try:
                resultado_bridge = despachar_comando(text, df, engine=engine)
                df_nuevo = resultado_bridge.get("df_nuevo")
                if df_nuevo is not None and df_nuevo is not df:
                    state.dataframes[analysis_id] = df_nuevo
                return _save_and_return(analysis_id, _bot_msg(
                    content   = resultado_bridge["resultado"] or "✅ Operación completada.",
                    freshness = "datos locales",
                    note      = "Resultado directo del análisis",
                ))
            except Exception as e:
                return _save_and_return(analysis_id,
                    _bot_msg(f"❌ Error ejecutando `{cmd_base}`: {e}"))

        # /config — configuración del engine (no necesita df)
        if cmd_base == "/config":
            from src.api.command_bridge import bridge_config
            return _save_and_return(analysis_id, _bot_msg(
                content   = bridge_config(),
                freshness = "datos locales",
                note      = "Configuración del engine",
            ))

        # /estado — estado runtime del engine
        if cmd_base == "/estado":
            from src.api.command_bridge import bridge_estado
            return _save_and_return(analysis_id, _bot_msg(
                content   = bridge_estado(engine),
                freshness = "datos locales",
                note      = "Estado del engine",
            ))

        # /metricas — requiere MetricsCalculator, no está en commands.py igual
        if cmd_base == "/metricas" and df is not None:
            try:
                from src.processing.metrics import MetricsCalculator, CONFIG_DEFAULT

                # Auto-detectar columna de campaña — no hardcodear "campana"
                col_campana = None
                for col in df.columns:
                    col_n = col.lower()
                    if any(p in col_n for p in ["campana", "campaign", "utm_campaign"]):
                        col_campana = col
                        break
                col_campana = col_campana or df.columns[0]

                # Construir config con la columna real detectada
                config_auto = {**CONFIG_DEFAULT, "col_campana": col_campana}
                calc    = MetricsCalculator(config=config_auto)
                metr    = calc.calcular(df, nivel="campana")
                resumen = calc.resumen_para_llm(metr, nivel="campana")
                engine.agregar_contexto_comando("/metricas", resumen)
                respuesta = engine.chat(
                    "Muéstrame las métricas por campaña: leads, MQL, CPL, CPMQL y ROAS. "
                    "Presenta los datos en formato tabla y agrega un insight por campaña."
                )
                return _save_and_return(analysis_id, _bot_msg(
                    content    = respuesta.respuesta,
                    confidence = respuesta.confianza,
                    freshness  = getattr(respuesta, "data_freshness", "ahora"),
                    note       = getattr(respuesta, "confidence_note", ""),
                ))
            except Exception as e:
                print(f"[chat] Error /metricas: {e}")
                return _save_and_return(analysis_id, _bot_msg(
                    content    = f"⚠️ Error ejecutando /metricas: {e}",
                    confidence = 0.5,
                ))

        # /alertas — requiere DataValidator
        if cmd_base == "/alertas" and df is not None:
            try:
                from src.processing.alerts import DataValidator as AlertValidator
                manager = AlertValidator(df)
                manager.validate()
                lines = []
                for a in manager.alertas:
                    icon = "❌" if a.nivel.value == "critica" else "⚠️" if a.nivel.value == "advertencia" else "✅"
                    lines.append(f"{icon} **{a.nivel.value.upper()}** — {a.mensaje}")
                    lines.append(f"   → {a.recomendacion}")
                content = "\n".join(lines) if lines else "✅ Datos en buen estado."
                return _save_and_return(analysis_id, _bot_msg(
                    content = content,
                    note    = "Validación de integridad del dataset",
                ))
            except Exception as e:
                print(f"[chat] Error /alertas: {e}")
                return _save_and_return(analysis_id, _bot_msg(
                    content    = f"⚠️ Error ejecutando /alertas: {e}",
                    confidence = 0.5,
                ))

        # ── Registry universal — todos los demás comandos ─────────────────────
        if df is not None:
            registry = _build_registry(df, partes)
            if cmd_base in registry:
                try:
                    output, ctx = registry[cmd_base]()
                except Exception as e:
                    return _save_and_return(analysis_id,
                        _bot_msg(f"❌ Error ejecutando `{cmd_base}`: {e}"))

                # El comando no produjo nada — columnas faltantes u otro error
                _AVISOS = {
                    "/rentabilidad": "⚠️ `/rentabilidad` necesita columna de **valor de venta** (`valor_venta`, `revenue`) que no está en este dataset.\n\nAlternativas disponibles: `/metricas` para CPL por campaña · `/rfm` para segmentación de leads.",
                    "/velocidad":    "⚠️ `/velocidad` necesita columna de **fecha de cierre** (`fecha_cierre`, `close_date`) que no está en este dataset.\n\nAlternativa: `/cohorts` para ver conversión por mes.",
                }
                if output is None and ctx is None:
                    msg = _AVISOS.get(cmd_base,
                        f"⚠️ `{cmd_base}` no pudo ejecutarse — columnas requeridas no detectadas.\n\nUsa `/columnas` para ver el schema del dataset activo.")
                    return _save_and_return(analysis_id, _bot_msg(
                        content    = msg,
                        confidence = 0.8,
                        note       = "Columnas requeridas no encontradas",
                    ))
                # El comando produjo output de Rich pero sin ctx — igual mostrarlo limpio
                # (ej: /velocidad con aviso de Rich — _strip_rich ya limpió los tags)
                if output and "no detectadas" in output and ctx is None:
                    msg = _AVISOS.get(cmd_base, _strip_rich(output) if output else "⚠️ Columnas requeridas no detectadas.")
                    return _save_and_return(analysis_id, _bot_msg(
                        content    = msg,
                        confidence = 0.8,
                        note       = "Columnas requeridas no encontradas",
                    ))

                # Inyectar contexto al engine si existe
                if ctx and not isinstance(ctx, dict):
                    engine.agregar_contexto_comando(cmd_base, ctx)

                # Detectar resultado estructurado tipo=tabla (bridge_head / bridge_sample)
                if isinstance(ctx, dict) and ctx.get("tipo") == "tabla":
                    return _save_and_return(analysis_id, _bot_msg(
                        content   = ctx.get("titulo", ""),
                        freshness = "datos locales",
                        note      = "Resultado directo del análisis",
                        table     = ctx["tabla"],
                    ))

                # Intentar convertir tabla ASCII a DataTable estructurada
                table_data = _rich_to_table(output) if output else None

                # Retornar output capturado de Rich como contenido del mensaje
                content = _strip_rich(output or ctx or f"✅ `{cmd_base}` ejecutado.")
                # Si hay tabla estructurada, dejar content vacío para que DataTable la muestre
                if table_data:
                    content = ""
                return _save_and_return(analysis_id, _bot_msg(
                    content   = content,
                    freshness = "datos locales",
                    note      = "Resultado directo del análisis",
                    table     = table_data,
                ))

        # Comando no reconocido
        return _save_and_return(analysis_id, _bot_msg(
            content   = f"❓ Comando `{cmd_base}` no reconocido. Escribe `/ayuda` para ver todos los comandos.",
            freshness = "ahora",
        ))

    # ── 3. Query analítica (pandas antes del LLM) ────────────────────────────
    tiene_resultado_pandas = False
    if df is not None:
        resultado_pandas = ejecutar_query_analitica(text, df)
        if resultado_pandas:
            if resultado_pandas.startswith("CONFIRMAR:"):
                state._pending_confirms[pending_key] = text
                return _save_and_return(analysis_id, _bot_msg(
                    content   = resultado_pandas,
                    freshness = "ahora",
                    note      = "Verificando interpretación antes de calcular",
                ))
            engine.agregar_contexto_comando("query_analitica", resultado_pandas)
            tiene_resultado_pandas = True

    # ── 4. LLM ───────────────────────────────────────────────────────────────
    # Si hay resultado de pandas, instruir al LLM explícitamente para formatear
    # como tabla cuando los datos lo permitan
    prompt_llm = text
    if tiene_resultado_pandas:
        prompt_llm = (
            f"{text}\n\n"
            "INSTRUCCIÓN: El resultado está en ÚLTIMO ANÁLISIS EJECUTADO. "
            "Si los datos son tabulares (agrupaciones, rankings, conteos), "
            "usa tipo=\"tabla\" con columnas y datos estructurados. "
            "Si es un valor único o respuesta simple, usa tipo=\"texto\"."
        )
    try:
        respuesta = engine.chat(prompt_llm)
        bot = _bot_msg(
            content    = respuesta.respuesta,
            confidence = respuesta.confianza,
            freshness  = getattr(respuesta, "data_freshness", "ahora"),
            note       = getattr(respuesta, "confidence_note", ""),
            table      = respuesta.datos if getattr(respuesta, "tipo", "") == "tabla" else None,
        )
        if respuesta.tipo == "lista" and respuesta.datos:
            extra = "\n\n"
            for item in respuesta.datos:
                extra += f"- {item['item']}\n" if isinstance(item, dict) and "item" in item else f"- {str(item)}\n"
            bot["content"] += extra

        if analysis_id in state.analyses:
            state.analyses[analysis_id]["last_message"] = text
            state.analyses[analysis_id]["confidence"]   = respuesta.confianza

        return _save_and_return(analysis_id, bot)

    except Exception as e:
        print(f"[chat] Error engine.chat: {e}")
        err = _bot_msg(
            content    = f"Ocurrió un error al procesar tu solicitud: {str(e)}",
            confidence = 0.0,
            note       = "Error interno del servidor",
        )
        err["is_error"] = True
        return _save_and_return(analysis_id, err)
