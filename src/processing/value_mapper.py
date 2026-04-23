# value_mapper.py — Adly · Data-Buddy
# Normaliza valores categóricos dentro de columnas
# Mismo patrón que ColumnMapper: reglas → LLM fallback → cache de sesión
# Aplica a: estados del embudo, fuentes, campañas, cualquier categórica

import json
import re
import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger("adly.value_mapper")


# ─────────────────────────────────────────
# DICCIONARIO DE SINÓNIMOS CONOCIDOS
# Por categoría semántica — extensible
# ─────────────────────────────────────────

SINONIMOS_ESTADO = {
    # lead
    "lead": "lead", "new": "lead", "nuevo": "lead", "entrada": "lead",
    "inbound": "lead", "contacto": "lead",
    # mql
    "mql": "mql", "qualified": "mql", "calificado": "mql",
    "marketing qualified": "mql", "interesado_calificado": "mql",
    # sql
    "sql": "sql", "opportunity": "sql", "oportunidad": "sql",
    "sales qualified": "sql", "en_proceso": "sql",
    # venta
    "venta": "venta", "sold": "venta", "won": "venta", "sale": "venta",
    "closed_won": "venta", "converted": "venta", "cerrado": "venta",
    "ganado": "venta", "cliente": "venta", "closed": "venta",
    # perdido
    "perdido": "perdido", "lost": "perdido", "cold": "perdido",
    "descartado": "perdido", "no_interesado": "perdido",
    "closed_lost": "perdido", "churn": "perdido",
}

SYSTEM_PROMPT_VALUE_MAPPER = """Eres un experto en análisis de datos de marketing digital.
Tu tarea es normalizar valores categóricos de una columna al vocabulario estándar de Adly.

Recibirás:
1. El nombre de la columna
2. Los valores únicos encontrados en el dataset
3. El vocabulario objetivo al que debes mapear

Debes inferir a qué valor estándar corresponde cada valor encontrado.
Si un valor no tiene equivalente claro, mapealo a null.

Reglas:
- Ignora diferencias de mayúsculas/minúsculas y espacios
- Considera sinónimos en español e inglés
- Responde SOLO con el JSON. Sin texto antes ni después.

Formato de respuesta:
{
  "<valor_original>": "<valor_normalizado o null>",
  ...
}"""


# ─────────────────────────────────────────
# VALUE MAPPER
# ─────────────────────────────────────────

class ValueMapper:
    """
    Normaliza valores categóricos dentro de columnas de un DataFrame.
    Mismo patrón que ColumnMapper — reglas primero, LLM como fallback.

    Uso:
        mapper = ValueMapper()
        df, no_reconocidos = mapper.normalizar_estados(df, col_estado="estado")
    """

    def __init__(self, llm_provider: str = None):
        self._llm_provider = llm_provider or "groq"
        self._llm          = None
        self.cache: dict[str, dict] = {}  # key: (col, frozenset de valores), val: mapeo

    # ─────────────────────────────────────
    # MÉTODO PRINCIPAL
    # ─────────────────────────────────────

    def normalizar_estados(
        self,
        df: pd.DataFrame,
        col_estado: str,
    ) -> tuple[pd.DataFrame, list]:
        """
        Normaliza los valores de la columna de estado al vocabulario estándar.

        Retorna:
            (df_normalizado, no_reconocidos)
            - df_normalizado: DataFrame con col_estado normalizada
            - no_reconocidos: lista de (valor_original, count) que no pudieron mapearse
        """
        if col_estado not in df.columns:
            return df, []

        df = df.copy()
        valores_unicos = df[col_estado].dropna().unique().tolist()

        # Obtener mapeo (cache → reglas → LLM)
        mapeo = self._obtener_mapeo(col_estado, valores_unicos, SINONIMOS_ESTADO)

        # Aplicar normalización
        df[col_estado] = df[col_estado].map(
            lambda v: mapeo.get(self._normalizar_key(v)) if pd.notna(v) else v
        )

        # Detectar no reconocidos (quedaron como None tras el mapeo)
        mask_invalidos = df[col_estado].isna() & pd.Series(
            [pd.notna(v) for v in df[col_estado]], index=df.index
        )
        # Recalcular desde el original para saber qué valores fallaron
        no_reconocidos = [
            (v, int((df[col_estado].isna()).sum()))
            for v in valores_unicos
            if self._normalizar_key(v) not in mapeo or mapeo[self._normalizar_key(v)] is None
        ]

        return df, no_reconocidos

    def normalizar_columna(
        self,
        df: pd.DataFrame,
        col: str,
        sinonimos: dict,
    ) -> tuple[pd.DataFrame, list]:
        """
        Normaliza cualquier columna categórica con un diccionario de sinónimos dado.
        Interfaz genérica — normalizar_estados() es un wrapper sobre esto.
        """
        if col not in df.columns:
            return df, []

        df   = df.copy()
        vals = df[col].dropna().unique().tolist()
        mapeo = self._obtener_mapeo(col, vals, sinonimos)

        df[col] = df[col].map(
            lambda v: mapeo.get(self._normalizar_key(v)) if pd.notna(v) else v
        )

        no_reconocidos = [
            (v, int((df[col].isna()).sum()))
            for v in vals
            if self._normalizar_key(v) not in mapeo or mapeo[self._normalizar_key(v)] is None
        ]

        return df, no_reconocidos

    # ─────────────────────────────────────
    # MAPEO: REGLAS → LLM → CACHE
    # ─────────────────────────────────────

    def _obtener_mapeo(self, col: str, valores: list, sinonimos: dict) -> dict:
        """
        Construye el mapeo para una lista de valores.
        1. Normalización básica (lowercase + strip)
        2. Lookup en diccionario de sinónimos
        3. LLM para los que no se resolvieron
        4. Cache de sesión
        """
        cache_key = f"{col}:{frozenset(str(v) for v in valores)}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        mapeo = {}
        sin_resolver = []

        for v in valores:
            key = self._normalizar_key(v)
            if key in sinonimos:
                mapeo[key] = sinonimos[key]
            else:
                sin_resolver.append(v)

        # LLM fallback para los no resueltos por reglas
        if sin_resolver:
            mapeo_llm = self._llm_fallback(col, sin_resolver, list(set(sinonimos.values())))
            mapeo.update(mapeo_llm)

        self.cache[cache_key] = mapeo
        return mapeo

    def _normalizar_key(self, valor) -> str:
        """Normalización básica: lowercase, strip, guiones → underscore."""
        return str(valor).lower().strip().replace(" ", "_").replace("-", "_")

    def _llm_fallback(self, col: str, valores: list, vocabulario: list) -> dict:
        """Llama al LLM para resolver sinónimos no cubiertos por reglas."""
        if self._llm is None:
            try:
                from src.ai.engine import LLMFactory
                self._llm = LLMFactory.crear(self._llm_provider)
            except Exception as e:
                logger.warning(f"ValueMapper: no pudo iniciar LLM ({e})")
                return {self._normalizar_key(v): None for v in valores}

        prompt = (
            f"Columna: '{col}'\n"
            f"Valores a mapear: {valores}\n"
            f"Vocabulario objetivo: {vocabulario}\n"
            f"Mapea cada valor al vocabulario objetivo o null si no tiene equivalente."
        )
        mensajes = [
            {"role": "system", "content": SYSTEM_PROMPT_VALUE_MAPPER},
            {"role": "user",   "content": prompt},
        ]

        try:
            raw  = self._llm.completar(mensajes)
            data = self._parsear_json(raw)
            if data:
                return {self._normalizar_key(k): v for k, v in data.items()}
        except Exception as e:
            logger.warning(f"ValueMapper LLM falló: {e}")

        # Si LLM falla — todos como None
        return {self._normalizar_key(v): None for v in valores}

    def _parsear_json(self, texto: str) -> Optional[dict]:
        """Extrae JSON de la respuesta del LLM — mismo patrón que ColumnMapper."""
        try:
            return json.loads(texto.strip())
        except (json.JSONDecodeError, ValueError):
            pass
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", texto, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except (json.JSONDecodeError, ValueError):
                pass
        match = re.search(r"\{.*\}", texto, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except (json.JSONDecodeError, ValueError):
                pass
        return None
