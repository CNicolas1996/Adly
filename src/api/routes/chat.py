from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from datetime import datetime

from src.api.state import state
from src.api.limiter import limiter
from src.processing.query_engine import ejecutar_query_analitica

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessage(BaseModel):
    analysis_id: str
    message: str


@router.post("")
@limiter.limit("30/minute")
async def send_message(request: Request, payload: ChatMessage):
    analysis_id = payload.analysis_id
    text = payload.message

    if analysis_id not in state.engines:
        raise HTTPException(
            status_code=404,
            detail="Análisis no encontrado o el motor no fue inicializado."
        )

    engine = state.engines[analysis_id]
    df = state.dataframes.get(analysis_id)

    # Guardar mensaje del usuario
    user_msg = {
        "id": f"msg_user_{datetime.utcnow().timestamp()}",
        "role": "user",
        "content": text,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    if analysis_id not in state.messages:
        state.messages[analysis_id] = []
    state.messages[analysis_id].append(user_msg)

    # ── Comandos especiales ───────────────────────────────────
    if text.startswith("/rfm") and df is not None:
        try:
            from interfaces.cli.commands import cmd_rfm
            ctx = cmd_rfm(df)
            if ctx:
                engine.agregar_contexto_comando("/rfm", ctx)
        except Exception as e:
            print(f"Error procesando /rfm: {e}")

    if text.startswith("/cohorts") and df is not None:
        try:
            from interfaces.cli.commands import cmd_cohorts
            ctx = cmd_cohorts(df)
            if ctx:
                engine.agregar_contexto_comando("/cohorts", ctx)
        except Exception as e:
            print(f"Error procesando /cohorts: {e}")

    if text.startswith("/embudo") and df is not None:
        try:
            from interfaces.cli.commands import cmd_embudo
            partes = text.split()
            col_campana = " ".join(partes[1:]) if len(partes) > 1 else ""
            ctx = cmd_embudo(df, col_campana)
            if ctx:
                engine.agregar_contexto_comando("/embudo", ctx)
        except Exception as e:
            print(f"Error procesando /embudo: {e}")

    # ── Query analítica — pandas antes del LLM ───────────────
    if df is not None and not text.startswith("/"):
        resultado_pandas = ejecutar_query_analitica(text, df)
        if resultado_pandas:
            engine.agregar_contexto_comando("query_analitica", resultado_pandas)

    # ── LLM ──────────────────────────────────────────────────
    try:
        respuesta = engine.chat(text)

        bot_msg = {
            "id": f"msg_bot_{datetime.utcnow().timestamp()}",
            "role": "bot",
            "content": respuesta.respuesta,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "confidence": respuesta.confianza,
            "data_freshness": getattr(respuesta, "data_freshness", "ahora"),
            "confidence_note": getattr(respuesta, "confidence_note", ""),
        }

        if respuesta.tipo == "tabla" and respuesta.datos:
            bot_msg["table"] = respuesta.datos

        if respuesta.tipo == "lista" and respuesta.datos:
            list_content = "\n\n"
            for item in respuesta.datos:
                if isinstance(item, dict) and "item" in item:
                    list_content += f"- {item['item']}\n"
                else:
                    list_content += f"- {str(item)}\n"
            bot_msg["content"] += list_content

        state.messages[analysis_id].append(bot_msg)

        if analysis_id in state.analyses:
            state.analyses[analysis_id]["last_message"] = text
            state.analyses[analysis_id]["confidence"] = respuesta.confianza

        return bot_msg

    except Exception as e:
        print(f"Error in engine.chat: {e}")
        error_msg = {
            "id": f"msg_err_{datetime.utcnow().timestamp()}",
            "role": "bot",
            "content": f"Ocurrió un error al procesar tu solicitud: {str(e)}",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "confidence": 0.0,
            "data_freshness": "ahora",
            "confidence_note": "Error interno del servidor",
            "is_error": True,
        }
        state.messages[analysis_id].append(error_msg)
        return error_msg
