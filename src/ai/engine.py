# engine.py — Adly · Data-Buddy
# Motor LLM agnóstico — interpreta métricas y responde en lenguaje natural
# Arquitectura: Strategy (BaseLLM) + Factory + Memoria + Fallback
# MVP: Chain of Thought · JSON Output · Historial de sesión · Fallback

import os
import re
import json
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


def _env(key: str, default: str = "") -> str:
    """os.getenv pero trata valores vacíos como ausentes — devuelve default si la variable es '' o None."""
    val = os.getenv(key, "").strip()
    return val if val else default


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
    Siempre retorna los mismos campos — el CLI los renderiza.
    Sembrado para confianza y severidad (Fase 3).

    v2: agrega tipo, columnas y datos para soporte de tablas y listas.
    """
    respuesta:  str   = ""                          # Texto en lenguaje natural
    accion:     str   = ""                          # Recomendación concreta
    severidad:  str   = "info"                      # info | warning | critical
    confianza:  float = 0.0                         # 0.0 - 1.0

    # v2 — campos para renderizado enriquecido
    tipo:       str   = "texto"                     # texto | tabla | lista | debug
    columnas:   list  = field(default_factory=list) # headers para tipo="tabla"
    datos:      list  = field(default_factory=list) # list[dict] para tipo="tabla"

    # v3 — integridad de datos (calculados por el engine, no por el LLM)
    data_freshness:  str = ""  # "hace 5min", "hace 2h", "desconocido"
    confidence_note: str = ""  # "mock data — no usar para decisiones reales"

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

        # Estrategia 2.5 — extraer substring entre primer { y último }
        inicio = texto.find("{")
        fin    = texto.rfind("}")
        if inicio != -1 and fin != -1 and fin > inicio:
            candidato = texto[inicio:fin+1]
            datos = _intentar_parsear(candidato)
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
        """Construye RespuestaAdly desde un dict ya parseado. Incluye campos v2."""
        return cls(
            respuesta = datos.get("respuesta", "Sin respuesta"),
            accion    = datos.get("accion",    ""),
            severidad = datos.get("severidad", "info"),
            confianza = float(datos.get("confianza", 0.5)),
            # v2
            tipo      = datos.get("tipo",     "texto"),
            columnas  = datos.get("columnas", []),
            datos     = datos.get("datos",    []),
        )

    def es_valida(self) -> bool:
        return bool(self.respuesta) and self.severidad in ("info", "warning", "critical")

    def normalizar(self) -> "RespuestaAdly":
        """
        Normaliza la respuesta: detecta CSV en "respuesta" y lo convierte a tabla.
        Detecta listas en "respuesta" y lo convierte a lista estructurada.
        Esto corrige respuestas del LLM que no usan correctamente tipo/columnas/datos.

        Safety net — no reemplaza el formato correcto desde el LLM, solo corrige fallbacks.
        """
        respuesta = self.respuesta.strip()
        if not respuesta:
            return self

        lineas = [l for l in respuesta.split('\n') if l.strip()]

        # ── Detectar tabla markdown (| col | col |) ──────────────────────────
        # Patrón: línea con |...| seguida de línea con |---|...| (separador)
        if len(lineas) >= 2:
            es_tabla_md = all('|' in l for l in lineas[:3])  # primeras 3 líneas tienen |
            tiene_separador = any(re.match(r'^\|\s*-{3,}\s*\|', l) for l in lineas)

            if es_tabla_md and tiene_separador:
                # Extraer headers de la primera línea
                header_line = lineas[0].strip().strip('|')
                headers_md = [c.strip() for c in header_line.split('|') if c.strip()]

                if headers_md:
                    datos_md = []
                    for linea in lineas[1:]:
                        # Saltar línea de separador |---|---|
                        if re.match(r'^\|\s*-{3,}\s*\|', linea):
                            continue
                        contenido = linea.strip().strip('|')
                        valores = [v.strip() for v in contenido.split('|') if v.strip()]
                        if len(valores) >= len(headers_md):
                            fila = {headers_md[i]: valores[i] for i in range(len(headers_md))}
                            datos_md.append(fila)

                    if datos_md:
                        return RespuestaAdly(
                            respuesta = "Datos extraídos automáticamente",
                            accion    = self.accion,
                            severidad = self.severidad,
                            confianza = self.confianza,
                            tipo      = "tabla",
                            columnas  = headers_md,
                            datos     = datos_md,
                        )

        # ── Detectar CSV real (tabla) ─────────────────────────────────────────
        # Condición: >= 2 líneas, separador consistente en TODAS las líneas
        if len(lineas) >= 2:
            primera = lineas[0]
            separador = None
            for sep in ('|', ',', ';'):
                if sep in primera:
                    separador = sep
                    break

            if separador:
                # Validar que TODAS las líneas tengan el mismo número de separadores
                conteos = [linea.count(separador) for linea in lineas]
                es_csv_real = len(set(conteos)) == 1 and conteos[0] >= 1

                if es_csv_real:
                    columnas = [c.strip().strip('"').strip("'") for c in lineas[0].split(separador)]
                    columnas = [c for c in columnas if c]

                    if columnas:
                        datos = []
                        for linea in lineas[1:]:
                            valores = [v.strip().strip('"').strip("'") for v in linea.split(separador)]
                            while len(valores) < len(columnas):
                                valores.append("—")
                            fila = {columnas[i]: valores[i] for i in range(min(len(columnas), len(valores)))}
                            datos.append(fila)

                        if datos:
                            return RespuestaAdly(
                                respuesta = "Datos extraídos automáticamente",
                                accion    = self.accion,
                                severidad = self.severidad,
                                confianza = self.confianza,
                                tipo      = "tabla",
                                columnas  = columnas,
                                datos     = datos,
                            )

        # ── Detectar lista numerada o con viñetas ────────────────────────────
        # Patrones: "1. Item" | "1) Item" | "- Item" | "* Item"
        if re.match(r'^\d+[\.\)]\s+\w', respuesta) or re.match(r'^[-*]\s+\w', respuesta):
            items_lista = []
            for linea in lineas:
                cleaned = re.sub(r'^\d+[\.\)]\s+', '', linea.strip())
                cleaned = re.sub(r'^[-*]\s+', '', cleaned)
                if cleaned:
                    items_lista.append(cleaned)

            if items_lista:
                return RespuestaAdly(
                    respuesta = "Lista detectada automáticamente",
                    accion    = self.accion,
                    severidad = self.severidad,
                    confianza = self.confianza,
                    tipo      = "lista",
                    columnas  = [],
                    datos     = [{"item": i} for i in items_lista],
                )

        return self


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

    VENTANA_DEFAULT = 6   # máximo de intercambios recordados

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
        self.modelo  = modelo or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        # Lee ADLY_LLM_API_KEY (variable unificada) con fallback a GEMINI_API_KEY (legacy)
        self.api_key = _env("GEMINI_API_KEY") or _env("ADLY_LLM_API_KEY")

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
        self.api_key  = _env("ADLY_LLM_API_KEY")
        self.base_url = _env("ADLY_LLM_BASE_URL", "https://api.deepseek.com")
    def nombre(self) -> str: return "DeepSeekLLM"


class GroqLLM(OpenAILLM):
    """
    Groq — ultra rápido, gratis con límites generosos.
    No soporta response_format — sobreescribe completar().
    """
    def __init__(self, modelo: str = None):
        super().__init__(modelo)
        self.modelo   = modelo or os.getenv("ADLY_LLM_MODEL", "llama-3.3-70b-versatile")
        self.api_key  = _env("ADLY_LLM_API_KEY")
        self.base_url = _env("ADLY_LLM_BASE_URL", "https://api.groq.com/openai/v1")

    def completar(self, mensajes: list[dict]) -> str:
        """
        Retry con backoff exponencial para rate limit de Groq.
        Intenta hasta 3 veces antes de lanzar RuntimeError.
        """
        from openai import OpenAI
        client  = OpenAI(api_key=self.api_key, base_url=self.base_url)
        intentos = 3
        espera   = 5  # duplica en cada retry: 5s → 10s → 20s

        for intento in range(intentos):
            try:
                resp = client.chat.completions.create(
                    model    = self.modelo,
                    messages = mensajes,
                )
                return resp.choices[0].message.content

            except Exception as e:
                error_str = str(e).lower()
                es_rate_limit = any(k in error_str for k in [
                    "rate limit", "rate_limit", "429", "too many requests",
                    "tokens per minute", "requests per minute",
                ])
                if es_rate_limit and intento < intentos - 1:
                    logger.debug(
                        f"[GroqLLM] Rate limit — esperando {espera}s "
                        f"(intento {intento + 1}/{intentos})"
                    )
                    time.sleep(espera)
                    espera *= 2
                else:
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
        self.api_key  = _env("ADLY_LLM_API_KEY")
        self.base_url = _env("ADLY_LLM_BASE_URL", "https://api.anthropic.com/v1")
    def nombre(self) -> str: return "ClaudeLLM"


class MistralLLM(OpenAILLM):
    """
    Mistral AI — europea, buena relación costo/calidad.
    Modelos: mistral-small, mistral-medium, mistral-large.
    """
    def __init__(self, modelo: str = None):
        super().__init__(modelo)
        self.modelo   = modelo or os.getenv("ADLY_LLM_MODEL", "mistral-small-latest")
        self.api_key  = _env("ADLY_LLM_API_KEY")
        self.base_url = _env("ADLY_LLM_BASE_URL", "https://api.mistral.ai/v1")
    def nombre(self) -> str: return "MistralLLM"


class TogetherLLM(OpenAILLM):
    """
    Together AI — 50+ modelos open source en una sola API.
    Llama, Mistral, Qwen, Gemma y más — API OpenAI-compatible.
    """
    def __init__(self, modelo: str = None):
        super().__init__(modelo)
        self.modelo   = modelo or os.getenv("ADLY_LLM_MODEL", "meta-llama/Llama-3-70b-chat-hf")
        self.api_key  = _env("ADLY_LLM_API_KEY")
        self.base_url = _env("ADLY_LLM_BASE_URL", "https://api.together.xyz/v1")
    def nombre(self) -> str: return "TogetherLLM"


class PerplexityLLM(OpenAILLM):
    """
    Perplexity — LLM con búsqueda web integrada.
    Útil para análisis que requieren datos actualizados del mercado.
    """
    def __init__(self, modelo: str = None):
        super().__init__(modelo)
        self.modelo   = modelo or os.getenv("ADLY_LLM_MODEL", "llama-3.1-sonar-small-128k-online")
        self.api_key  = _env("ADLY_LLM_API_KEY")
        self.base_url = _env("ADLY_LLM_BASE_URL", "https://api.perplexity.ai")
    def nombre(self) -> str: return "PerplexityLLM"


class CohereLLM(OpenAILLM):
    """
    Cohere — especializado en RAG y embeddings.
    Ideal para cuando implementemos búsqueda semántica en Fase 3.
    """
    def __init__(self, modelo: str = None):
        super().__init__(modelo)
        self.modelo   = modelo or os.getenv("ADLY_LLM_MODEL", "command-r-plus")
        self.api_key  = _env("ADLY_LLM_API_KEY")
        self.base_url = _env("ADLY_LLM_BASE_URL", "https://api.cohere.com/v1")
    def nombre(self) -> str: return "CohereLLM"


class HuggingFaceLLM(OpenAILLM):
    """
    HuggingFace Inference API — miles de modelos open source.
    Endpoint OpenAI-compatible desde nov 2024.
    """
    def __init__(self, modelo: str = None):
        super().__init__(modelo)
        self.modelo   = modelo or os.getenv("ADLY_LLM_MODEL", "HuggingFaceH4/zephyr-7b-beta")
        self.api_key  = _env("ADLY_LLM_API_KEY")
        self.base_url = _env("ADLY_LLM_BASE_URL", "https://api-inference.huggingface.co/v1")
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

SYSTEM_PROMPT = """Eres Adly, analista de marketing senior. Lees datos de campañas y dices lo que importa — directo, sin rodeos, como un analista hablando con el director.

ANÁLISIS:
- Embudo siempre: Leads→MQL→SQL→Venta. ROAS es un dato más; la métrica principal es CPA+tasa de venta.
- Calidad sobre volumen. Si ves algo crítico que no te preguntaron, dilo igual. Si los datos son insuficientes, dilo honestamente.
- Fuera de alcance (temas sin relación con marketing/datos): responde "Eso está fuera de mi alcance. ¿En qué puedo ayudarte con tus campañas?" con confianza 0.0.
- Si la pregunta es ambigua, haz UNA pregunta antes de responder.

TIPOS DE RESPUESTA:
- Simple → 1-2 oraciones con número concreto.
- Comparativa → conclusión+número primero, luego máx 3 factores.
- Compleja → conclusión ejecutiva, pros con números, contras con números, recomendación con cifras exactas.
- Lista → tipo="lista", "datos":[{"item":"..."}], máx 4 items, orden por impacto.
- Tabla → tipo="tabla", "columnas":["A","B"], "datos":[{"A":"x","B":"y"}].
- Si hay ÚLTIMO ANÁLISIS EJECUTADO en el contexto: responde sobre ese, usa sus números exactos.
- Si el contexto contiene "CONFIRMAR" (pregunta de verificación de fuzzy match), IGNORA esa parte y responde directamente sobre los datosanalíticos del ÚLTIMO ANÁLISIS.

SIEMPRE: números concretos ("$15,112" no "CPL alto"). Agrega "Ojo:" si hay algo crítico no preguntado.

FORMATO — devuelve SOLO este JSON, sin texto antes ni después, sin markdown:
{"respuesta":"...","accion":"...","severidad":"info|warning|critical","confianza":0.0,"tipo":"texto|tabla|lista","columnas":[],"datos":[]}

Severidad: info=normal, warning=revisar esta semana, critical=atención hoy/pérdida de presupuesto.
Confianza: 1.0=datos sólidos, 0.7=inconsistencias menores, 0.5=parcial, <0.5=no recomiendes nada crítico.
Prohibido en valores JSON: asteriscos, almohadillas, backticks. Solo prosa plana."""


# ─────────────────────────────────────────
# ADLY ENGINE — orquestador principal
# ─────────────────────────────────────────

class AdlyEngine:
    """
    Cerebro de Adly. Orquesta LLM + Memoria + Contexto + Fallback.
    No lee datos, no calcula métricas — solo interpreta y responde.

    Uso básico:
        engine = AdlyEngine()
        engine.set_contexto(resumen_metricas)
        respuesta = engine.chat("¿cuál campaña tiene mejor CPL?")

    Uso completo (v2):
        engine.set_contexto_completo(resumen_metricas, resumen_schema)
        respuesta = engine.chat("dame todas las columnas del CSV")
    """

    def __init__(
        self,
        llm:      BaseLLM       = None,
        fallback: list[BaseLLM] = None,
        ventana:  int           = 6,
    ):
        # LLM principal — si no se pasa, usa Factory con .env
        self.llm      = llm or LLMFactory.crear()

        # Cadena de fallback — si no se pasa, usa .env
        self.fallback = fallback or LLMFactory.crear_cadena_fallback()

        # Memoria de conversación
        self.memoria  = MemoriaConversacion(ventana=ventana)

        # Contexto de datos — se actualiza con set_contexto() o set_contexto_completo()
        self._contexto_datos:  str = ""
        self._contexto_schema: str = ""  # v2 — schema del CSV raw

        # v3 — integridad de datos
        self._ingested_at: object = None  # datetime de la última carga
        self._fuente:      str    = ""    # "mock" | "sheets" | "csv"

        # v3 — contexto del último comando CLI ejecutado
        self._ultimo_comando: str = ""   # nombre del comando: "/rfm", "/cohorts"
        self._ultimo_resumen: str = ""   # resultado denso del último comando

        # Inicializar memoria con system prompt
        self.memoria.agregar("system", SYSTEM_PROMPT)

        logger.debug(f"Iniciado con {self.llm.nombre()}")
        if self.fallback:
            nombres = [l.nombre() for l in self.fallback]
            logger.debug(f"Fallback: {nombres}")

    def set_contexto(self, resumen_metricas: str, fuente: str = "desconocido") -> None:
        """
        Inyecta el contexto de métricas derivadas.
        Llamar cada vez que los datos se actualicen.
        Backward compatible — no requiere schema.

        v2 — el contexto va en el system prompt (índice 0 de memoria),
        no en cada mensaje de usuario. Así el historial no crece con datos
        duplicados en cada turno — los mensajes solo llevan la pregunta.
        """
        self._contexto_datos = resumen_metricas
        self._ingested_at    = __import__("datetime").datetime.now()
        self._fuente         = fuente
        self._actualizar_system_prompt()
        logger.debug(f"Contexto métricas actualizado — {len(resumen_metricas)} chars")

    def set_contexto_completo(self, resumen_metricas: str, resumen_schema: str, fuente: str = "desconocido") -> None:
        """
        v2 — Inyecta tanto métricas derivadas como schema del CSV raw.
        Permite al LLM responder sobre columnas específicas del dataset original.

        v3 — contexto va en system prompt, no en cada mensaje de usuario.

        Args:
            resumen_metricas: output de MetricsCalculator.resumen_para_llm()
            resumen_schema:   output de MetricsCalculator.resumen_schema(df_raw)
            fuente:           "mock" | "sheets" | "csv"
        """
        self._contexto_datos  = resumen_metricas
        self._contexto_schema = resumen_schema
        self._ingested_at     = __import__("datetime").datetime.now()
        self._fuente          = fuente
        self._actualizar_system_prompt()
        logger.debug(
            f"Contexto completo actualizado — "
            f"métricas: {len(resumen_metricas)} chars, "
            f"schema: {len(resumen_schema)} chars"
        )

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

        # Detectar saludo — respuesta hardcodeada, sin LLM, sin footer
        SALUDOS = {"hola", "hi", "hello", "buenas", "buenos", "buen", "hey",
                   "que tal", "qué tal", "gracias", "ok", "okay", "listo", "dale"}
        es_saludo = pregunta.strip().lower() in SALUDOS or len(pregunta.strip()) < 10
        if es_saludo:
            return RespuestaAdly(
                respuesta = "Listo. ¿Qué quieres analizar?",
                accion    = "",
                severidad = "info",
                confianza = 1.0,
                tipo      = "texto",
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

        # Normalizar respuesta: detecta CSV/listas en "respuesta" y convierte a tipo correcto
        respuesta = respuesta.normalizar()

        # v3 — inyectar integridad de datos calculada por el engine (no por el LLM)
        respuesta.data_freshness  = self._calcular_freshness()
        respuesta.confidence_note = self._calcular_confidence_note()
        return respuesta

    def agregar_contexto_comando(self, comando: str, resumen: str) -> None:
        """
        Registra el resultado del último comando CLI ejecutado.
        Ventana deslizante — solo el último comando es contexto activo.
        Si el usuario corre /rfm y luego /cohorts, Adly sabe del cohorts, no del rfm.
        Fase 3: esto se convierte en ContextoComando con datos estructurados.
        """
        if not resumen:
            return
        self._ultimo_comando = comando
        self._ultimo_resumen = resumen
        logger.debug(f"Último comando registrado: {comando}")

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
            f"  Contexto métricas : {'Cargado' if self._contexto_datos else 'Vacío'}",
            f"  Contexto schema   : {'Cargado' if self._contexto_schema else 'Vacío'}",
        ]
        return "\n".join(lineas)

    def recargar_llm(self) -> str:
        """
        Recarga el LLM principal y la cadena de fallback desde .env.
        Llamar después de cambiar ADLY_LLM_PROVIDER con /config.
        No reinicia la memoria — la conversación continúa.
        Retorna el nombre del nuevo LLM activo.
        """
        load_dotenv(override=True)
        self.llm      = LLMFactory.crear()
        self.fallback = LLMFactory.crear_cadena_fallback()
        nombre = self.llm.nombre()
        logger.debug(f"LLM recargado → {nombre}")
        return nombre

    # ── métodos internos ──────────────────

    def _actualizar_system_prompt(self) -> None:
        """
        Reconstruye el system prompt con el contexto de datos actual
        y lo inyecta en el índice 0 de la memoria.

        Estrategia: contexto de datos va en system prompt — no en cada
        mensaje de usuario. Así el historial de conversación no crece
        con datos duplicados en cada turno.

        Fase 3 (Queryn): reemplazar por RAG — solo secciones relevantes
        por pregunta en vez del contexto completo cada vez.
        """
        from datetime import date
        fecha_hoy = date.today().strftime("%d de %B de %Y")

        partes = [SYSTEM_PROMPT]

        if self._contexto_datos:
            partes += [
                f"\n\n{'─' * 40}",
                f"CONTEXTO TEMPORAL: Hoy es {fecha_hoy}.",
                f"DATOS ACTUALES DE CAMPAÑAS:",
                f"{'─' * 40}",
                self._contexto_datos,
                f"{'─' * 40}",
            ]

        if self._contexto_schema:
            partes += [
                f"\nSCHEMA DEL DATASET (columnas del CSV original):",
                f"{'─' * 40}",
                self._contexto_schema,
                f"{'─' * 40}",
            ]

        system_completo = "\n".join(partes)

        # Reemplazar system prompt en índice 0 de memoria
        if self.memoria._historial and self.memoria._historial[0].rol == "system":
            self.memoria._historial[0] = Mensaje(rol="system", contenido=system_completo)
        else:
            self.memoria._historial.insert(0, Mensaje(rol="system", contenido=system_completo))

        logger.debug(f"System prompt actualizado — {len(system_completo)} chars totales")

    def _calcular_freshness(self) -> str:
        """
        Calcula cuánto tiempo pasó desde la última carga de datos.
        Formato: "<texto>|<nivel>"
        Nivel: "ok" | "warning" | "critical"
          ok       → menos de 24h
          warning  → entre 24h y 48h — dato del día anterior
          critical → más de 48h — no confíes sin /refresh
        El renderer separa texto y nivel para colorear el footer.
        """
        if not self._ingested_at:
            return "desconocido|ok"
        import datetime
        delta = datetime.datetime.now() - self._ingested_at
        segundos = int(delta.total_seconds())

        if segundos < 60:
            texto = f"hace {segundos}s"
        elif segundos < 3600:
            texto = f"hace {segundos // 60}min"
        elif segundos < 86400:
            horas = segundos // 3600
            texto = f"hace {horas}h"
        else:
            dias = segundos // 86400
            texto = f"hace {dias}d"

        # Nivel de alerta según antigüedad
        UMBRAL_WARNING  = 24 * 3600   # 24 horas
        UMBRAL_CRITICAL = 48 * 3600   # 48 horas

        if segundos >= UMBRAL_CRITICAL:
            nivel = "critical"
            texto = f"{texto} — datos muy desactualizados"
        elif segundos >= UMBRAL_WARNING:
            nivel = "warning"
            texto = f"{texto} — considera /refresh"
        else:
            nivel = "ok"

        return f"{texto}|{nivel}"

    def _calcular_confidence_note(self) -> str:
        """Nota de confiabilidad basada en la fuente de datos actual."""
        notas = {
            "mock":       "mock data — no usar para decisiones reales",
            "sheets":     "datos de Google Sheets",
            "csv":        "datos de CSV local",
            "desconocido": "fuente desconocida",
        }
        return notas.get(self._fuente, f"fuente: {self._fuente}")

    def _construir_mensaje(self, pregunta: str) -> str:
        """
        Arma el mensaje del usuario — limpio, solo pregunta + resultado pandas.

        El contexto de datos (métricas + schema) ya está en el system prompt
        via _actualizar_system_prompt(). No se repite aquí — eso causaba que
        el historial creciera con datos duplicados en cada turno.

        Solo se inyecta el último resultado de comando/pandas si existe,
        porque es contexto específico del turno actual, no global.

        Fase 3 (Queryn/RAG): _construir_mensaje recibirá solo las secciones
        del contexto relevantes para esta pregunta específica.
        """
        partes = []

        # Último resultado pandas/comando — contexto del turno actual
        if self._ultimo_resumen:
            partes += [
                f"ÚLTIMO ANÁLISIS EJECUTADO ({self._ultimo_comando.upper()}):",
                f"{'─' * 40}",
                self._ultimo_resumen,
                f"{'─' * 40}",
                "El usuario puede hacer preguntas sobre este análisis.",
                "",
            ]

        partes.append(f"PREGUNTA: {pregunta}")

        return "\n".join(partes)

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
            except Exception as e:
                error_str = str(e).lower()
                es_rate_limit = any(k in error_str for k in [
                    "rate limit", "rate_limit", "429", "too many requests",
                ])
                if es_rate_limit:
                    logger.warning(f"{llm.nombre()} rate limit agotado — pasando al siguiente")
                else:
                    logger.warning(f"{llm.nombre()} fallo: {e}")
                time.sleep(1)

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
    schema   = calc.resumen_schema(df)

    # 2. Iniciar engine con contexto completo
    engine = AdlyEngine()
    engine.set_contexto_completo(resumen, schema)
    print(engine.estado())

    # 3. Simular conversación
    preguntas = [
        "¿Cuál campaña tiene el mejor CPL?",
        "¿Qué columnas tiene el dataset?",
        "¿Y por qué crees que esa es más eficiente?",
        "¿Qué campaña pausarías primero?",
    ]

    print("\n" + "="*50)
    print("  SIMULACIÓN DE CONVERSACIÓN")
    print("="*50)

    for pregunta in preguntas:
        print(f"\nUsuario: {pregunta}")
        respuesta = engine.chat(pregunta)
        print(f"\nAdly [{respuesta.severidad.upper()}] (confianza: {respuesta.confianza:.0%}) tipo={respuesta.tipo}")
        print(f"  {respuesta.respuesta}")
        if respuesta.accion:
            print(f"  → {respuesta.accion}")
        if respuesta.tipo == "tabla" and respuesta.datos:
            print(f"  [tabla] columnas={respuesta.columnas} filas={len(respuesta.datos)}")
        print("─" * 50)
