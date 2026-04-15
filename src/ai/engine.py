# engine.py — Adly · Data-Buddy
# Motor LLM agnóstico — interpreta métricas y responde en lenguaje natural
# Arquitectura: Strategy (BaseLLM) + Factory + Memoria + Fallback
# MVP: Chain of Thought · JSON Output · Historial de sesión · Fallback

import os
import json
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Logger interno — solo visible si ADLY_DEBUG=true en .env
_debug = os.getenv("ADLY_DEBUG", "false").lower() == "true"
logging.basicConfig(level=logging.DEBUG if _debug else logging.WARNING)
logger = logging.getLogger("adly.engine")


# ─────────────────────────────────────────
# ESTRUCTURA DE RESPUESTA — JSON output
# Pydantic-ready pero sin dependencia obligatoria en MVP
# ─────────────────────────────────────────

@dataclass
class RespuestaAdly:
    """
    Estructura de respuesta estandarizada de Adly.
    Siempre retorna los mismos 4 campos — el CLI los renderiza.
    Sembrado para confianza y severidad (Fase 3).
    """
    respuesta:  str   = ""                          # Texto en lenguaje natural
    accion:     str   = ""                          # Recomendación concreta
    severidad:  str   = "info"                      # info | warning | critical
    confianza:  float = 0.0                         # 0.0 - 1.0

    @classmethod
    def desde_json(cls, texto: str) -> "RespuestaAdly":
        """
        Parsea la respuesta JSON del LLM con extracción robusta.
        Estrategia en capas — tolera basura antes/después del JSON:
          1. JSON puro directo
          2. Bloque ```json ... ```
          3. Primer objeto JSON válido extraído con regex
          4. Fallback controlado con el texto crudo
        """
        import re

        def _intentar_parsear(candidato: str) -> Optional[dict]:
            try:
                return json.loads(candidato.strip())
            except (json.JSONDecodeError, ValueError):
                return None

        # Estrategia 1 — texto ya es JSON limpio
        datos = _intentar_parsear(texto)
        if datos:
            return cls._desde_dict(datos)

        # Estrategia 2 — bloque markdown ```json ... ``` o ``` ... ```
        match_md = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", texto, re.DOTALL)
        if match_md:
            datos = _intentar_parsear(match_md.group(1))
            if datos:
                return cls._desde_dict(datos)

        # Estrategia 3 — extraer primer objeto JSON válido del texto libre
        # Busca desde el primer { hasta el } que cierre correctamente
        match_obj = re.search(r"\{.*\}", texto, re.DOTALL)
        if match_obj:
            datos = _intentar_parsear(match_obj.group(0))
            if datos:
                return cls._desde_dict(datos)

        # Estrategia 4 — fallback: texto crudo como respuesta
        logger.warning("desde_json: no se pudo extraer JSON — usando texto crudo como fallback")
        return cls(
            respuesta = texto.strip(),
            accion    = "",
            severidad = "warning",
            confianza = 0.3,
        )

    @classmethod
    def _desde_dict(cls, datos: dict) -> "RespuestaAdly":
        """Construye RespuestaAdly desde un dict ya parseado."""
        return cls(
            respuesta = datos.get("respuesta", "Sin respuesta"),
            accion    = datos.get("accion",    ""),
            severidad = datos.get("severidad", "info"),
            confianza = float(datos.get("confianza", 0.5)),
        )

    def es_valida(self) -> bool:
        return bool(self.respuesta) and self.severidad in ("info", "warning", "critical")


# ─────────────────────────────────────────
# MEMORIA DE CONVERSACIÓN
# Historial de sesión — no persiste entre sesiones (MVP)
# ─────────────────────────────────────────

@dataclass
class Mensaje:
    rol:       str  # "user" | "assistant" | "system"
    contenido: str

class MemoriaConversacion:
    """
    Gestiona el historial de la sesión actual.
    Mantiene una ventana de N mensajes para no explotar el contexto.
    MVP: solo sesión en memoria. Fase 3: persistencia en DB.
    """

    VENTANA_DEFAULT = 10  # máximo de intercambios recordados

    def __init__(self, ventana: int = VENTANA_DEFAULT):
        self.ventana:  int           = ventana
        self._historial: list[Mensaje] = []

    def agregar(self, rol: str, contenido: str) -> None:
        self._historial.append(Mensaje(rol=rol, contenido=contenido))
        # Truncar manteniendo siempre el system prompt (índice 0)
        if len(self._historial) > self.ventana + 1:
            self._historial = [self._historial[0]] + self._historial[-(self.ventana):]

    def como_lista(self) -> list[dict]:
        """Formato estándar OpenAI-compatible para todos los proveedores."""
        return [{"role": m.rol, "content": m.contenido} for m in self._historial]

    def limpiar(self) -> None:
        """Reinicia la conversación manteniendo solo el system prompt."""
        if self._historial:
            self._historial = [self._historial[0]]

    def resumen(self) -> str:
        return f"[Memoria] {len(self._historial)} mensajes en historial"


# ─────────────────────────────────────────
# BASE LLM — contrato Strategy
# ─────────────────────────────────────────

class BaseLLM(ABC):
    """
    Contrato que deben cumplir todos los proveedores LLM.
    El Engine nunca sabe con quién habla — solo llama completar().
    Mismo patrón que BaseConnector en sheets.py.
    """

    @abstractmethod
    def completar(self, mensajes: list[dict]) -> str:
        """
        Recibe historial de mensajes formato OpenAI.
        Retorna texto crudo — el Engine lo parsea.
        """
        pass

    @abstractmethod
    def esta_disponible(self) -> bool:
        """Verifica si el proveedor está accesible antes de usarlo."""
        pass

    def nombre(self) -> str:
        return self.__class__.__name__


# ─────────────────────────────────────────
# IMPLEMENTACIONES LLM
# ─────────────────────────────────────────

class OllamaLLM(BaseLLM):
    """
    Proveedor local via Ollama.
    Gratis, sin internet, ideal para desarrollo.
    Requiere: ollama corriendo en localhost:11434
    """

    def __init__(self, modelo: str = None):
        self.modelo  = modelo or os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
        self.url     = os.getenv("OLLAMA_URL", "http://localhost:11434")

    def completar(self, mensajes: list[dict]) -> str:
        try:
            import requests
            resp = requests.post(
                f"{self.url}/api/chat",
                json={
                    "model":    self.modelo,
                    "messages": mensajes,
                    "stream":   False,
                    "format":   "json",  # fuerza JSON output en Ollama
                },
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"[OllamaLLM] Error: {e}")

    def esta_disponible(self) -> bool:
        try:
            import requests
            r = requests.get(f"{self.url}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False


class GeminiLLM(BaseLLM):
    """
    Proveedor Google Gemini.
    Gratis con límites generosos — ideal para demos.
    Requiere: GEMINI_API_KEY en .env
    """

    def __init__(self, modelo: str = None):
        self.modelo  = modelo or os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.api_key = os.getenv("GEMINI_API_KEY", "")

    def completar(self, mensajes: list[dict]) -> str:
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.modelo)

            # Convertir formato OpenAI → formato Gemini
            prompt = self._convertir_mensajes(mensajes)
            resp   = model.generate_content(prompt)
            return resp.text
        except Exception as e:
            raise RuntimeError(f"[GeminiLLM] Error: {e}")

    def esta_disponible(self) -> bool:
        return bool(self.api_key)

    def _convertir_mensajes(self, mensajes: list[dict]) -> str:
        """Gemini no usa formato chat nativo — concatenamos con roles."""
        partes = []
        for m in mensajes:
            if m["role"] == "system":
                partes.append(f"INSTRUCCIONES: {m['content']}")
            elif m["role"] == "user":
                partes.append(f"USUARIO: {m['content']}")
            elif m["role"] == "assistant":
                partes.append(f"ADLY: {m['content']}")
        return "\n\n".join(partes)


class OpenAILLM(BaseLLM):
    """
    Proveedor OpenAI — también sirve para DeepSeek y Groq
    que usan el mismo formato de API (OpenAI-compatible).
    Requiere: OPENAI_API_KEY + OPENAI_BASE_URL en .env
    """

    def __init__(self, modelo: str = None):
        self.modelo   = modelo or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.api_key  = os.getenv("OPENAI_API_KEY", "")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    def completar(self, mensajes: list[dict]) -> str:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            resp   = client.chat.completions.create(
                model       = self.modelo,
                messages    = mensajes,
                response_format={"type": "json_object"},  # JSON enforcement
            )
            return resp.choices[0].message.content
        except Exception as e:
            raise RuntimeError(f"[OpenAILLM] Error: {e}")

    def esta_disponible(self) -> bool:
        return bool(self.api_key)


class DeepSeekLLM(OpenAILLM):
    """DeepSeek — API OpenAI-compatible. Muy bueno, muy económico."""
    def __init__(self, modelo: str = None):
        super().__init__(modelo)
        self.modelo   = modelo or os.getenv("ADLY_LLM_MODEL", "deepseek-chat")
        self.api_key  = os.getenv("ADLY_LLM_API_KEY", "")
        self.base_url = os.getenv("ADLY_LLM_BASE_URL", "https://api.deepseek.com")
    def nombre(self) -> str: return "DeepSeekLLM"


class GroqLLM(OpenAILLM):
    """
    Groq — ultra rápido, gratis con límites generosos.
    No soporta response_format — sobreescribe completar().
    """
    def __init__(self, modelo: str = None):
        super().__init__(modelo)
        self.modelo   = modelo or os.getenv("ADLY_LLM_MODEL", "llama-3.3-70b-versatile")
        self.api_key  = os.getenv("ADLY_LLM_API_KEY", "")
        self.base_url = os.getenv("ADLY_LLM_BASE_URL", "https://api.groq.com/openai/v1")

    def completar(self, mensajes: list[dict]) -> str:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            resp   = client.chat.completions.create(
                model    = self.modelo,
                messages = mensajes,
            )
            return resp.choices[0].message.content
        except Exception as e:
            raise RuntimeError(f"[GroqLLM] Error: {e}")

    def nombre(self) -> str: return "GroqLLM"


class ClaudeLLM(OpenAILLM):
    """
    Anthropic Claude — máxima calidad de razonamiento.
    Usa el endpoint OpenAI-compatible de Anthropic.
    """
    def __init__(self, modelo: str = None):
        super().__init__(modelo)
        self.modelo   = modelo or os.getenv("ADLY_LLM_MODEL", "claude-opus-4-6")
        self.api_key  = os.getenv("ADLY_LLM_API_KEY", "")
        self.base_url = os.getenv("ADLY_LLM_BASE_URL", "https://api.anthropic.com/v1")
    def nombre(self) -> str: return "ClaudeLLM"


class MistralLLM(OpenAILLM):
    """
    Mistral AI — europea, buena relación costo/calidad.
    Modelos: mistral-small, mistral-medium, mistral-large.
    """
    def __init__(self, modelo: str = None):
        super().__init__(modelo)
        self.modelo   = modelo or os.getenv("ADLY_LLM_MODEL", "mistral-small-latest")
        self.api_key  = os.getenv("ADLY_LLM_API_KEY", "")
        self.base_url = os.getenv("ADLY_LLM_BASE_URL", "https://api.mistral.ai/v1")
    def nombre(self) -> str: return "MistralLLM"


class TogetherLLM(OpenAILLM):
    """
    Together AI — 50+ modelos open source en una sola API.
    Llama, Mistral, Qwen, Gemma y más — API OpenAI-compatible.
    """
    def __init__(self, modelo: str = None):
        super().__init__(modelo)
        self.modelo   = modelo or os.getenv("ADLY_LLM_MODEL", "meta-llama/Llama-3-70b-chat-hf")
        self.api_key  = os.getenv("ADLY_LLM_API_KEY", "")
        self.base_url = os.getenv("ADLY_LLM_BASE_URL", "https://api.together.xyz/v1")
    def nombre(self) -> str: return "TogetherLLM"


class PerplexityLLM(OpenAILLM):
    """
    Perplexity — LLM con búsqueda web integrada.
    Útil para análisis que requieren datos actualizados del mercado.
    """
    def __init__(self, modelo: str = None):
        super().__init__(modelo)
        self.modelo   = modelo or os.getenv("ADLY_LLM_MODEL", "llama-3.1-sonar-small-128k-online")
        self.api_key  = os.getenv("ADLY_LLM_API_KEY", "")
        self.base_url = os.getenv("ADLY_LLM_BASE_URL", "https://api.perplexity.ai")
    def nombre(self) -> str: return "PerplexityLLM"


class CohereLLM(OpenAILLM):
    """
    Cohere — especializado en RAG y embeddings.
    Ideal para cuando implementemos búsqueda semántica en Fase 3.
    """
    def __init__(self, modelo: str = None):
        super().__init__(modelo)
        self.modelo   = modelo or os.getenv("ADLY_LLM_MODEL", "command-r-plus")
        self.api_key  = os.getenv("ADLY_LLM_API_KEY", "")
        self.base_url = os.getenv("ADLY_LLM_BASE_URL", "https://api.cohere.com/v1")
    def nombre(self) -> str: return "CohereLLM"


class HuggingFaceLLM(OpenAILLM):
    """
    HuggingFace Inference API — miles de modelos open source.
    Endpoint OpenAI-compatible desde nov 2024.
    """
    def __init__(self, modelo: str = None):
        super().__init__(modelo)
        self.modelo   = modelo or os.getenv("ADLY_LLM_MODEL", "HuggingFaceH4/zephyr-7b-beta")
        self.api_key  = os.getenv("ADLY_LLM_API_KEY", "")
        self.base_url = os.getenv("ADLY_LLM_BASE_URL", "https://api-inference.huggingface.co/v1")
    def nombre(self) -> str: return "HuggingFaceLLM"


# ─────────────────────────────────────────
# LLM FACTORY — 11 proveedores
# ─────────────────────────────────────────

class LLMFactory:
    """
    Crea el LLM correcto según configuración.
    El Engine nunca instancia LLMs directamente — siempre via Factory.
    Soporta 11 proveedores — agregar uno nuevo = una línea en PROVEEDORES.
    """

    PROVEEDORES: dict[str, type] = {
        "ollama":      OllamaLLM,
        "gemini":      GeminiLLM,
        "openai":      OpenAILLM,
        "deepseek":    DeepSeekLLM,
        "groq":        GroqLLM,
        "claude":      ClaudeLLM,
        "mistral":     MistralLLM,
        "together":    TogetherLLM,
        "perplexity":  PerplexityLLM,
        "cohere":      CohereLLM,
        "huggingface": HuggingFaceLLM,
    }

    @staticmethod
    def crear(proveedor: str = None, modelo: str = None) -> BaseLLM:
        """
        Crea el LLM indicado.
        Si no se especifica proveedor, usa ADLY_LLM_PROVIDER del .env.
        """
        nombre = proveedor or os.getenv("ADLY_LLM_PROVIDER", "ollama")
        if nombre not in LLMFactory.PROVEEDORES:
            disponibles = list(LLMFactory.PROVEEDORES.keys())
            raise ValueError(
                f"Proveedor '{nombre}' no soportado.\n"
                f"Disponibles: {disponibles}"
            )
        cls = LLMFactory.PROVEEDORES[nombre]
        return cls(modelo) if modelo else cls()

    @staticmethod
    def crear_cadena_fallback() -> list[BaseLLM]:
        """
        Cadena de fallback configurable desde .env.
        ADLY_LLM_FALLBACK=ollama,groq,gemini
        El Engine intenta en orden hasta que uno responda.
        Default robusto: ollama (local) → groq (rápido/gratis) → gemini (gratis).
        """
        cadena_str  = os.getenv("ADLY_LLM_FALLBACK", "ollama,groq,gemini")
        proveedores = [p.strip() for p in cadena_str.split(",")]
        return [
            LLMFactory.crear(p)
            for p in proveedores
            if p in LLMFactory.PROVEEDORES
        ]

    @staticmethod
    def listar() -> list[str]:
        """Lista todos los proveedores disponibles."""
        return list(LLMFactory.PROVEEDORES.keys())


# ─────────────────────────────────────────
# SYSTEM PROMPT — Chain of Thought
# Define el rol experto de Adly
# ─────────────────────────────────────────

SYSTEM_PROMPT = """Eres Adly, el analista de marketing que esta agencia no tiene en nómina pero necesita.
Tu trabajo es leer los datos de campañas y decirle al equipo lo que realmente importa — sin rodeos, sin jerga innecesaria, como lo haría un analista senior hablando con el director de marketing.

CÓMO HABLAS:
- Natural y directo. "Te aconsejo pausar esa campaña" en vez de "Acción recomendada: pausar campaña."
- Si ves un problema, lo dices claro: "Ojo, el CPL de esta campaña está 40% arriba del histórico — eso merece atención hoy."
- Si algo va bien, también lo dices: no todo es alerta.
- Si la pregunta es ambigua o necesitas más contexto para dar una respuesta útil, pregunta antes de inventar.
- Nunca rellenes con frases genéricas. Si no tienes suficientes datos para opinar, dilo honestamente.

CÓMO ANALIZAS:
- Miras el embudo completo siempre: Leads → MQL → SQL → Venta. Eso es eficiencia real.
- El ROAS es un dato más, no el criterio principal. Una campaña con ROAS alto pero tasa de venta de 0% no es eficiente — está generando basura cara.
- La métrica que más peso tiene es el CPA combinado con tasa de venta. Si el costo por venta es bajo y el cierre es alto, esa campaña gana.
- Priorizas calidad del lead sobre volumen. 10 leads que convierten valen más que 100 que no llegan a MQL.
- Si detectas algo crítico en los datos que el usuario no preguntó, lo mencionas igual — es parte del trabajo.

ALCANCE — respondes sobre:
- Análisis de campañas publicitarias y sus métricas
- Interpretación del embudo (Leads, MQL, SQL, Venta, CPL, CPMQL, CPA, ROAS, ICL)
- Conceptos y educación de marketing digital — métricas, estrategia, pauta, embudos
- Recomendaciones de escala, pausa o ajuste basadas en los datos disponibles
- Estrategia de pauta para agencias pequeñas con presupuesto ajustado

FUERA DE ALCANCE — rechazas con criterio:
Solo rechazas lo que claramente no tiene nada que ver con marketing o con el trabajo de la agencia.
Ejemplos de lo que SÍ respondes: "¿qué es el CPL?", "explícame el embudo", "¿cómo funciona el retargeting?", "conceptos básicos del marketing digital".
Ejemplos de lo que NO respondes: temas personales, entretenimiento, historia general, cualquier cosa que no tenga relación con marketing o datos.
Cuando rechaces, responde: "Eso está fuera de lo que puedo analizar. ¿En qué puedo ayudarte con tus campañas?"
Confianza en estos casos: 0.0

AUTONOMÍA — cuándo hacer preguntas:
- Si la pregunta tiene múltiples interpretaciones posibles, pregunta cuál quieren antes de responder.
- Si los datos son insuficientes para una recomendación sólida, pregunta qué información adicional pueden darte.
- Máximo una pregunta por turno — no hagas cuestionarios.

ESTRUCTURA DE RESPUESTA — según el tipo de pregunta:

Pregunta simple ("¿cuál campaña tiene mejor CPL?"):
→ Respuesta directa en 1-2 oraciones con el número concreto. Sin listas.

Pregunta comparativa ("¿cuál es más eficiente?"):
→ Conclusión primero con número específico.
→ Luego máximo 3 factores que explican por qué, ordenados de mayor a menor impacto.
→ Si hay un ganador claro, dilo. No equilibres artificialmente.

Pregunta de análisis complejo ("¿qué hago con mis campañas el próximo mes?"):
→ Conclusión ejecutiva en 1 oración.
→ Pros: qué está funcionando, con números.
→ Contras: qué no está funcionando, con números.
→ Recomendación concreta con cifras: "escala X un 20%", no "considera escalar X".

Pregunta de lista ("dame un resumen", "explícame las métricas"):
→ Formato numerado: 1. 2. 3. — nunca viñetas sueltas sin orden.
→ Cada punto: métrica + valor actual + qué significa.
→ Ordena de mayor a menor impacto para la decisión.
→ Máximo 4 puntos — si hay más, prioriza los que más afectan la decisión.

SIEMPRE en cualquier respuesta:
- Números concretos, no vagos. "$15,112 de CPL" no "CPL alto".
- Si hay algo crítico que el usuario no preguntó, agrégalo al final como "Ojo:".
- Máximo 4 puntos en cualquier lista.

FORMATO — responde SIEMPRE con un JSON válido y nada más antes o después:
{
  "respuesta": "respuesta estructurada según el tipo de pregunta arriba",
  "accion": "acción concreta si hay algo que hacer ahora — vacío si no aplica o si primero necesitas una respuesta del usuario",
  "severidad": "info | warning | critical",
  "confianza": 0.0-1.0
}

Criterios de severidad:
- info → todo normal o solo observaciones
- warning → hay algo que revisar en los próximos días
- critical → requiere atención hoy, puede haber pérdida de presupuesto o de leads

Criterios de confianza:
- 1.0 → datos completos y consistentes, análisis sólido
- 0.7 → datos con inconsistencias menores, análisis probable
- 0.5 → datos parciales, análisis orientativo
- < 0.5 → datos insuficientes, no recomiendes nada crítico

RESTRICCIONES DURAS:
- Nunca inventes métricas ni números que no están en los datos.
- Nunca pongas acción si no tienes claridad suficiente — mejor pregunta.
- Responde siempre en español.
- Devuelve SOLO el JSON. Sin texto antes, sin texto después, sin bloques markdown.
- PROHIBIDO dentro de los valores del JSON: asteriscos (**texto** o *texto*), almohadillas (## Título), guiones como viñetas (- item), backticks (`code`). El texto en "respuesta" y "accion" debe ser prosa plana sin ningún símbolo de markdown.
- Para listas dentro de "respuesta" usa punto y coma o numeración simple. Ejemplo correcto: "1. CPL: $15k 2. ROAS: 1.2 3. Tasa MQL: 28%". Nunca: "**CPL**: $15k\\n- ROAS: 1.2"."""


# ─────────────────────────────────────────
# ADLY ENGINE — orquestador principal
# ─────────────────────────────────────────

class AdlyEngine:
    """
    Cerebro de Adly. Orquesta LLM + Memoria + Contexto + Fallback.
    No lee datos, no calcula métricas — solo interpreta y responde.

    Uso:
        engine = AdlyEngine()
        engine.set_contexto(resumen_metricas)
        respuesta = engine.chat("¿cuál campaña tiene mejor CPL?")
    """

    def __init__(
        self,
        llm:      BaseLLM       = None,
        fallback: list[BaseLLM] = None,
        ventana:  int           = 10,
    ):
        # LLM principal — si no se pasa, usa Factory con .env
        self.llm      = llm or LLMFactory.crear()

        # Cadena de fallback — si no se pasa, usa .env
        self.fallback = fallback or LLMFactory.crear_cadena_fallback()

        # Memoria de conversación
        self.memoria  = MemoriaConversacion(ventana=ventana)

        # Contexto de datos — se actualiza con set_contexto()
        self._contexto_datos: str = ""

        # Inicializar memoria con system prompt
        self.memoria.agregar("system", SYSTEM_PROMPT)

        logger.debug(f"Iniciado con {self.llm.nombre()}")
        if self.fallback:
            nombres = [l.nombre() for l in self.fallback]
            logger.debug(f"Fallback: {nombres}")

    def set_contexto(self, resumen_metricas: str) -> None:
        """
        Inyecta el contexto de datos procesados.
        Llamar cada vez que los datos se actualicen.
        Diseñado para enchufar RAG aquí en Fase 3 sin cambiar la interfaz.
        """
        self._contexto_datos = resumen_metricas
        logger.debug(f"Contexto actualizado — {len(resumen_metricas)} caracteres")

    def chat(self, pregunta: str) -> RespuestaAdly:
        """
        Método principal — recibe pregunta, retorna RespuestaAdly.
        Gestiona: contexto + memoria + fallback + parsing.
        """
        if not self._contexto_datos:
            return RespuestaAdly(
                respuesta = "No hay datos cargados. Ejecuta set_contexto() primero.",
                accion    = "Cargar datos antes de hacer preguntas.",
                severidad = "warning",
                confianza = 0.0,
            )

        # Construir mensaje del usuario con contexto inyectado
        mensaje_usuario = self._construir_mensaje(pregunta)
        self.memoria.agregar("user", mensaje_usuario)

        # Intentar con LLM principal, luego fallback
        texto_crudo = self._completar_con_fallback()

        if texto_crudo is None:
            return RespuestaAdly(
                respuesta = "Todos los proveedores LLM fallaron. Verifica tu conexión y configuración.",
                accion    = "Revisar .env y disponibilidad de Ollama / API keys.",
                severidad = "critical",
                confianza = 0.0,
            )

        # Guardar respuesta en memoria
        self.memoria.agregar("assistant", texto_crudo)

        # Parsear JSON → RespuestaAdly
        respuesta = RespuestaAdly.desde_json(texto_crudo)
        return respuesta

    def limpiar_memoria(self) -> None:
        """Reinicia la conversación — útil para nueva sesión de análisis."""
        self.memoria.limpiar()
        logger.debug("Memoria de conversación limpiada")

    def estado(self) -> str:
        """Resumen del estado actual del engine."""
        lineas = [
            f"\n[AdlyEngine] Estado:",
            f"  LLM principal : {self.llm.nombre()}",
            f"  Disponible    : {self.llm.esta_disponible()}",
            f"  {self.memoria.resumen()}",
            f"  Contexto      : {'Cargado' if self._contexto_datos else 'Vacío'}",
        ]
        return "\n".join(lineas)

    # ── métodos internos ──────────────────

    def _construir_mensaje(self, pregunta: str) -> str:
        """
        Arma el mensaje del usuario con contexto de datos inyectado.
        Detecta saludos para no inyectar métricas innecesariamente.
        Incluye fecha actual para que Adly tenga contexto temporal.
        Fase 3: aquí entra RAG — solo métricas relevantes por pregunta.
        """
        from datetime import date

        SALUDOS = {"hola", "hi", "hello", "buenas", "buenos", "buen", "hey", "que tal", "qué tal"}
        es_saludo = pregunta.strip().lower() in SALUDOS or len(pregunta.strip()) < 10

        if es_saludo:
            return pregunta

        fecha_hoy = date.today().strftime("%d de %B de %Y")  # ej: "06 de April de 2026"

        return (
            f"CONTEXTO TEMPORAL: Hoy es {fecha_hoy}.\n\n"
            f"DATOS ACTUALES DE CAMPAÑAS:\n"
            f"{'─' * 40}\n"
            f"{self._contexto_datos}\n"
            f"{'─' * 40}\n\n"
            f"PREGUNTA: {pregunta}"
        )


    def _completar_con_fallback(self) -> Optional[str]:
        """
        Fallback management — intenta LLM principal, luego la cadena.
        Retorna texto crudo o None si todos fallan.
        """
        candidatos = [self.llm] + [
            llm for llm in self.fallback
            if llm.nombre() != self.llm.nombre()
        ]

        for llm in candidatos:
            if not llm.esta_disponible():
                logger.debug(f"{llm.nombre()} no disponible — saltando")
                continue
            try:
                logger.debug(f"Intentando con {llm.nombre()}...")
                texto = llm.completar(self.memoria.como_lista())
                logger.debug(f"Respondio {llm.nombre()}")
                return texto
            except RuntimeError as e:
                logger.debug(f"{llm.nombre()} fallo: {e}")
                time.sleep(0.5)

        return None  # todos fallaron


# ─────────────────────────────────────────
# MAIN — probar engine con mock data
# ─────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.append(".")

    from src.ingestion.mock_data import generar_datos_ghl
    from src.processing.metrics import MetricsCalculator, CONFIG_DEFAULT

    print(">> Iniciando prueba de AdlyEngine...\n")

    # 1. Generar datos y calcular métricas
    df       = generar_datos_ghl(n_leads=100)
    calc     = MetricsCalculator(config=CONFIG_DEFAULT)
    metricas = calc.calcular(df, nivel="campana")
    resumen  = calc.resumen_para_llm(metricas, nivel="campana")

    # 2. Iniciar engine
    engine = AdlyEngine()
    engine.set_contexto(resumen)
    print(engine.estado())

    # 3. Simular conversación
    preguntas = [
        "¿Cuál campaña tiene el mejor CPL?",
        "¿Y por qué crees que esa es más eficiente?",
        "¿Qué campaña pausarías primero?",
    ]

    print("\n" + "="*50)
    print("  SIMULACIÓN DE CONVERSACIÓN")
    print("="*50)

    for pregunta in preguntas:
        print(f"\nUsuario: {pregunta}")
        respuesta = engine.chat(pregunta)
        print(f"\nAdly [{respuesta.severidad.upper()}] (confianza: {respuesta.confianza:.0%})")
        print(f"  {respuesta.respuesta}")
        if respuesta.accion:
            print(f"  → {respuesta.accion}")
        print("─" * 50)
