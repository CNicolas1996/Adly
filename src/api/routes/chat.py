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
from src.api.command_bridge import despachar_comando, bridge_metricas
from src.processing.data_quality import DataQualityReport
from src.processing.data_cleaner import CleaningSession


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

def _build_registry(df, partes: list, analysis_id: str = "") -> dict:
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
        "/metricas":      lambda: (None, bridge_metricas(df, state.semantic_schemas.get(analysis_id), " ".join(partes[1:]) if len(partes) > 1 else "")),
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

    # ── 0. CLEANING SESSION activa — interceptar antes que todo ──────────────
    # Si hay una sesión de limpieza en curso para este analysis_id,
    # el mensaje del usuario es una opción de limpieza ("1", "2", "s", etc.)
    # Se resuelve aquí y se retorna — no llega al LLM ni a otros handlers.
    if not hasattr(state, "_cleaning_sessions"):
        state._cleaning_sessions = {}

    if analysis_id in state._cleaning_sessions:
        session: CleaningSession = state._cleaning_sessions[analysis_id]

        # ── Selección de modo pendiente ───────────────────────────────────────
        mode_pending = getattr(state, "_cleaning_mode_pending", {})
        if mode_pending.get(analysis_id):
            mode_pending.pop(analysis_id)

            if text.strip() == "1":  # Automático
                resultados = session.apply_auto()
                summary    = session.summary()
                df_final   = session.final_df
                if df_final is not None:
                    state.dataframes[analysis_id] = df_final
                    try:
                        if not hasattr(state, "_quality_reports"):
                            state._quality_reports = {}
                        state._quality_reports[analysis_id] = DataQualityReport.from_df(df_final)
                    except Exception:
                        pass
                del state._cleaning_sessions[analysis_id]
                return _save_and_return(analysis_id, _bot_msg(
                    content    = f"✅ Limpieza automática completada.\n\n{summary}",
                    confidence = 1.0,
                    note       = "Dataset actualizado — decisiones conservadoras aplicadas",
                ))

            elif text.strip() == "3":  # Mixto
                # Marcar issues críticos (>30%) como manuales en la sesión
                # Los demás se resuelven automático ahora
                issues_criticos = [
                    i for i in session._issues_pendientes if i.impacto > 30
                ]
                issues_menores  = [
                    i for i in session._issues_pendientes if i.impacto <= 30
                ]
                # Resolver menores automático
                for issue in issues_menores:
                    opcion = CleaningSession._OPCION_SEGURA.get(issue.tipo, "s")
                    if issue in session._issues_pendientes:
                        session._issues_pendientes.remove(issue)
                        session._issue_actual = issue
                        session.apply(opcion)
                # Continuar con manuales si quedan
                if session.done():
                    summary = session.summary()
                    if session.final_df is not None:
                        state.dataframes[analysis_id] = session.final_df
                    del state._cleaning_sessions[analysis_id]
                    return _save_and_return(analysis_id, _bot_msg(
                        content = f"✅ Limpieza mixta completada — sin problemas críticos.\n\n{summary}",
                        confidence = 1.0,
                    ))
                first_issue = session.next_issue()
                return _save_and_return(analysis_id, _bot_msg(
                    content = (
                        f"Problemas menores resueltos automáticamente. "
                        f"Quedan {session.progress()[1] - session.progress()[0]} problemas críticos:\n\n"
                        f"{session.render_issue(first_issue)}"
                    ),
                    confidence = 1.0,
                    note = "Modo mixto — responde con el número de opción",
                ))

            else:  # Manual (2) o cualquier otro input
                first_issue = session.next_issue()
                return _save_and_return(analysis_id, _bot_msg(
                    content = (
                        f"Modo manual activado. Vamos problema por problema.\n"
                        f"Escribe `cancelar` en cualquier momento.\n\n"
                        f"{session.render_issue(first_issue)}"
                    ),
                    confidence = 1.0,
                    note = "Sesión de limpieza manual — responde con el número de opción",
                ))

        # Cancelar sesión explícitamente
        if text.lower() in {"cancelar", "cancel", "salir", "exit", "no", "listo"}:
            summary = session.summary()
            # Aplicar df limpio al estado si hubo cambios reales
            if session.final_df is not None and len(session.decisions_log) > 0:
                state.dataframes[analysis_id] = session.final_df
            # Actualizar quality report con el df limpio
            try:
                if not hasattr(state, "_quality_reports"):
                    state._quality_reports = {}
                state._quality_reports[analysis_id] = DataQualityReport.from_df(session.final_df)
            except Exception:
                pass
            del state._cleaning_sessions[analysis_id]
            return _save_and_return(analysis_id, _bot_msg(
                content    = f"Sesión de limpieza finalizada.\n\n{summary}",
                confidence = 1.0,
                note       = "Limpieza de datos completada",
            ))

        # Aplicar la opción elegida
        issue = session.next_issue()
        if issue is None or session.done():
            # No quedan issues — cerrar sesión
            summary = session.summary()
            if session.final_df is not None:
                state.dataframes[analysis_id] = session.final_df
            # Actualizar quality report con el df limpio
            try:
                if not hasattr(state, "_quality_reports"):
                    state._quality_reports = {}
                state._quality_reports[analysis_id] = DataQualityReport.from_df(session.final_df)
            except Exception:
                pass
            del state._cleaning_sessions[analysis_id]
            return _save_and_return(analysis_id, _bot_msg(
                content    = f"✅ Todos los problemas revisados.\n\n{summary}",
                confidence = 1.0,
                note       = "Dataset actualizado",
            ))

        # Prefijo de opción — el usuario puede tipear "1", "/1", "opcion 1"
        opcion_id = text.strip().lower().replace("opcion ", "").replace("/", "").strip()

        # Opciones que requieren input adicional — teléfono con prefijo custom
        kwargs = {}
        if issue.tipo == "phone_sin_prefijo" and opcion_id == "1":
            # Si el texto tiene el prefijo incluido (ej: "1 +57"), extraerlo
            partes_tel = text.strip().split()
            if len(partes_tel) > 1 and partes_tel[1].startswith("+"):
                kwargs["prefijo_default"] = partes_tel[1]
            else:
                # Pedir el prefijo antes de continuar
                return _save_and_return(analysis_id, _bot_msg(
                    content    = "¿Qué prefijo internacional uso? (ej: `+1` para USA, `+57` para Colombia, `+52` para México)\nEscribe: `1 +57`",
                    confidence = 1.0,
                    note       = "Esperando prefijo",
                ))

        result = session.apply(opcion_id, **kwargs)

        if result is None:
            return _save_and_return(analysis_id, _bot_msg(
                content    = f"Opción no válida. Elige: {[o.id for o in issue.opciones]}",
                confidence = 1.0,
            ))

        # Actualizar df en state si cambió
        if result.filas_despues != result.filas_antes or result.columnas_nuevas:
            state.dataframes[analysis_id] = session.final_df

        # Presentar resultado + siguiente issue (si quedan)
        respuesta_parts = [session.render_result(result)]

        next_issue = session.next_issue()
        if next_issue is None or session.done():
            summary = session.summary()
            if session.final_df is not None:
                state.dataframes[analysis_id] = session.final_df
                try:
                    if not hasattr(state, "_quality_reports"):
                        state._quality_reports = {}
                    state._quality_reports[analysis_id] = DataQualityReport.from_df(session.final_df)
                except Exception:
                    pass
            del state._cleaning_sessions[analysis_id]
            respuesta_parts.append(f"\n✅ Todos los problemas revisados.\n\n{summary}")
        else:
            respuesta_parts.append(f"\n{session.render_issue(next_issue)}")

        engine.agregar_contexto_comando(
            "/alertas",
            f"Limpieza en curso. Último resultado: {result.descripcion}"
        )

        return _save_and_return(analysis_id, _bot_msg(
            content    = "\n".join(respuesta_parts),
            confidence = 1.0,
            note       = f"Limpieza interactiva — {session.progress()[0]}/{session.progress()[1]} issues",
        ))

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
        state.pending_model.pop(analysis_id, None)
        return _save_and_return(analysis_id,
            _bot_msg("Ok, cancelado. ¿En qué más puedo ayudarte?"))

    # ── API key pendiente para /modelo ───────────────────────────────────────
    if analysis_id in state.pending_model:
        from src.api.command_bridge import bridge_modelo_guardar_key
        pending = state.pending_model.pop(analysis_id)
        resultado = bridge_modelo_guardar_key(text, pending)
        if resultado.get("nuevo_modelo"):
            state.modelo_activo = resultado["nuevo_modelo"]
            engine.cambiar_llm(resultado["nuevo_modelo"])
        return _save_and_return(analysis_id, _bot_msg(
            content   = resultado["mensaje"],
            freshness = "ahora",
            note      = "Configuración de modelo",
        ))

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

        # /modelo — cambio de modelo LLM con flujo de API key
        if cmd_base == "/modelo":
            from src.api.command_bridge import bridge_modelo_status, bridge_modelo_cambiar
            nombre = partes[1].lower() if len(partes) > 1 else ""
            if not nombre:
                return _save_and_return(analysis_id, _bot_msg(
                    content   = bridge_modelo_status(state.modelo_activo),
                    freshness = "ahora",
                    note      = "Modelos disponibles",
                ))
            resultado = bridge_modelo_cambiar(nombre, state.modelo_activo)
            if resultado["necesita_key"]:
                state.pending_model[analysis_id] = resultado["pending"]
                return _save_and_return(analysis_id, _bot_msg(
                    content   = resultado["mensaje"],
                    freshness = "ahora",
                    note      = f"Configurando {resultado['pending']['label']}",
                ))
            if resultado.get("nuevo_modelo"):
                state.modelo_activo = resultado["nuevo_modelo"]
                engine.cambiar_llm(resultado["nuevo_modelo"])
            return _save_and_return(analysis_id, _bot_msg(
                content   = resultado["mensaje"],
                freshness = "ahora",
                note      = "Configuración de modelo",
            ))

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

        # /alertas — lee el DataQualityReport pre-calculado al cargar
        # Si por alguna razón no existe, lo calcula ahora (fallback)
        if cmd_base == "/alertas" and df is not None:
            try:
                # Leer desde state si existe — evita doble cálculo
                quality_reports = getattr(state, "_quality_reports", {})
                report = quality_reports.get(analysis_id)

                if report is None:
                    report = DataQualityReport.from_df(df)
                    if not hasattr(state, "_quality_reports"):
                        state._quality_reports = {}
                    state._quality_reports[analysis_id] = report
                score   = report.severity_score()
                summary = report.to_summary()

                # Si no hay problemas — solo mostrar el reporte limpio
                if score == 0:
                    engine.agregar_contexto_comando("/alertas", summary)
                    return _save_and_return(analysis_id, _bot_msg(
                        content    = f"✅ {summary}",
                        confidence = 1.0,
                        note       = "Validación de integridad del dataset",
                    ))

                # Iniciar sesión de limpieza interactiva
                session = CleaningSession.start(report)
                state._cleaning_sessions[analysis_id] = session

                nivel  = "CRÍTICO" if score >= 70 else "ALTO" if score >= 40 else "MEDIO"
                n_issues = session.progress()[1]

                # Preguntar modo antes de mostrar el primer issue
                # Guardar en state que estamos en selección de modo
                if not hasattr(state, "_cleaning_mode_pending"):
                    state._cleaning_mode_pending = {}
                state._cleaning_mode_pending[analysis_id] = True

                header = (
                    f"**Reporte de calidad — Score: {score}/100 ({nivel})**\n\n"
                    f"{summary}\n\n"
                    f"Encontré **{n_issues} problemas**. ¿Cómo quieres manejarlos?\n\n"
                    f"**[1] Automático** — Adly aplica la decisión más segura en cada problema\n"
                    f"      Sin preguntar, sin eliminar datos, siempre conservador.\n\n"
                    f"**[2] Manual** — Adly te pregunta qué hacer en cada problema\n"
                    f"      Tú decides, opción por opción.\n\n"
                    f"**[3] Mixto** — Automático para problemas menores, manual para críticos\n"
                    f"      Críticos (>30% afectados) te los pregunta. El resto los resuelve solo."
                )

                engine.agregar_contexto_comando("/alertas", summary)

                return _save_and_return(analysis_id, _bot_msg(
                    content    = header,
                    confidence = score / 100,
                    note       = "Selecciona el modo de limpieza",
                ))

            except Exception as e:
                import traceback
                print(f"[chat] Error /alertas: {e}\n{traceback.format_exc()}")
                return _save_and_return(analysis_id, _bot_msg(
                    content    = f"⚠️ Error ejecutando /alertas: {e}",
                    confidence = 0.5,
                ))

        # ── Registry universal — todos los demás comandos ─────────────────────
        if df is not None:
            registry = _build_registry(df, partes, analysis_id)
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
    print(f"[CHAT] paso 3 — query analítica con: '{text}'")
    tiene_resultado_pandas = False

    # Palabras que indican que la pregunta es seguimiento de la anterior
    _REFS_PREVIAS = {
        "ese", "esa", "eso", "esos", "esas",
        "esta", "este", "estos", "estas",
        "anterior", "arriba", "mismo", "misma",
        "el que dijiste", "la que dijiste",
        "eso que", "esa que", "por qué", "por que",
        "cómo así", "como así", "explica", "explícame",
        "y por qué", "y cómo", "qué significa",
    }
    _es_seguimiento = any(ref in text.lower() for ref in _REFS_PREVIAS)

    if df is not None:
        print(f"[CHAT] df disponible — ejecutando planner")
        resultado_pandas = ejecutar_query_analitica(text, df)
        print(f"[CHAT] resultado_pandas={resultado_pandas is not None}")
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
        else:
            # Pregunta nueva sin resultado pandas propio y no es seguimiento
            # → limpiar contexto anterior para no contaminar la respuesta del LLM
            if not _es_seguimiento:
                engine.limpiar_contexto_comando()
                print(f"[CHAT] contexto comando limpiado — pregunta nueva sin resultado pandas")

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
