# column_mapper.py — Adly · Data-Buddy
# Infiere el mapeo de columnas usando LLM — agnóstico a la estructura del Sheet
# Un LLM call por fuente nueva → resultado cacheado en sesión

import json
import logging
import re
from typing import Optional

logger = logging.getLogger("adly.column_mapper")


# ─────────────────────────────────────────
# SCHEMA TARGET — lo que MetricsCalculator espera
# ─────────────────────────────────────────

SCHEMA_ADLY = {
    "col_campana":   "nombre de la campaña publicitaria",
    "col_adset":     "conjunto de anuncios (adset)",
    "col_ad":        "anuncio individual (ad)",
    "col_leads":     "ID único del lead o contacto",
    "col_estado":    "estado del lead en el embudo de ventas",
    "col_inversion": "inversión o gasto en pauta (dinero)",
    "col_valor":     "valor de venta o ingreso generado",
    "col_fecha":     "fecha de creación o entrada del lead",
}

SYSTEM_PROMPT_MAPPER = """Eres un experto en análisis de datos de marketing digital.
Tu tarea es mapear columnas de un dataset desconocido al schema interno de Adly.

Recibirás:
1. Los nombres de las columnas del dataset
2. Una muestra de los primeros valores de cada columna

Debes inferir qué columna corresponde a cada campo del schema, aunque los nombres sean distintos, estén en otro idioma, o sean ambiguos.

Reglas:
- Si no puedes identificar una columna con certeza, usa null.
- Para col_estado, identifica también los valores exactos que corresponden a MQL, SQL y Venta.
- Si los valores del estado no coinciden claramente con MQL/SQL/Venta, infiere lo más cercano.
- Responde SOLO con el JSON. Sin texto antes ni después.

Schema objetivo:
{
  "col_campana":   "<nombre exacto de la columna>",
  "col_adset":     "<nombre exacto de la columna o null>",
  "col_ad":        "<nombre exacto de la columna o null>",
  "col_leads":     "<nombre exacto de la columna>",
  "col_estado":    "<nombre exacto de la columna>",
  "col_inversion": "<nombre exacto de la columna>",
  "col_valor":     "<nombre exacto de la columna o null>",
  "col_fecha":     "<nombre exacto de la columna o null>",
  "estado_mql":    "<valor exacto en los datos que representa MQL o null>",
  "estado_sql":    "<valor exacto en los datos que representa SQL o null>",
  "estado_venta":  "<valor exacto en los datos que representa Venta/Cierre o null>",
  "moneda":        "<código ISO de moneda inferido o 'USD'>"
}"""


# ─────────────────────────────────────────
# COLUMN MAPPER
# ─────────────────────────────────────────

class ColumnMapper:
    """
    Infiere el mapeo de columnas usando LLM.
    Un LLM call por fuente nueva — el resultado se cachea en self.cache.

    Uso:
        mapper = ColumnMapper(llm_provider="groq")
        config = mapper.mapear(df)
        calc   = MetricsCalculator(config=config)
    """

    def __init__(self, llm_provider: str = None):
        self._llm_provider = llm_provider or "groq"
        self._llm          = None
        self.cache: dict[str, dict] = {}   # key: hash del header, val: config

    def _llm_call(self, prompt_usuario: str) -> str:
        """Llama al LLM con un mensaje único — sin historial, sin contexto de sesión."""
        if self._llm is None:
            from src.ai.engine import LLMFactory
            self._llm = LLMFactory.crear(self._llm_provider)

        mensajes = [
            {"role": "system",    "content": SYSTEM_PROMPT_MAPPER},
            {"role": "user",      "content": prompt_usuario},
        ]
        return self._llm.completar(mensajes)

    def _construir_prompt(self, df) -> str:
        """
        Arma el prompt con header + muestra de valores por columna.
        Limpia la muestra antes de pasarla al LLM:
          - Excluye nulos y strings vacíos
          - Para columnas categóricas: deduplica por lowercase (evita LEAD/lead como dos valores)
          - Excluye valores de ruido conocidos (n/a, none, null, -)
        """
        import pandas as pd

        RUIDO = {"n/a", "na", "none", "null", "-", "", "nan", "undefined"}

        lineas = ["COLUMNAS Y MUESTRA DE VALORES:\n"]
        for col in df.columns:
            serie = df[col].dropna()

            if serie.empty:
                lineas.append(f'  "{col}": []')
                continue

            # Columnas categóricas — limpiar ruido y deduplicar por lowercase
            if serie.dtype == object:
                vistos = set()
                muestra_limpia = []
                for v in serie:
                    v_str = str(v).strip()
                    v_key = v_str.lower()
                    if v_key in RUIDO:
                        continue
                    if v_key not in vistos:
                        vistos.add(v_key)
                        muestra_limpia.append(v_str)
                    if len(muestra_limpia) >= 6:
                        break
                muestra = muestra_limpia
            else:
                # Numéricas y fechas — muestra normal
                muestra = serie.head(5).tolist()

            lineas.append(f'  "{col}": {muestra}')

        return "\n".join(lineas)

    def _parsear_config(self, texto: str) -> Optional[dict]:
        """Extrae el JSON de la respuesta del LLM."""
        # Estrategia 1 — JSON limpio
        try:
            return json.loads(texto.strip())
        except (json.JSONDecodeError, ValueError):
            pass

        # Estrategia 2 — bloque markdown
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", texto, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except (json.JSONDecodeError, ValueError):
                pass

        # Estrategia 3 — primer objeto JSON en el texto
        match = re.search(r"\{.*\}", texto, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except (json.JSONDecodeError, ValueError):
                pass

        return None

    def _fallback_keyword(self, df) -> dict:
        """Mapeo por palabras clave — úsalo si el LLM falla."""
        def buscar(palabras: list) -> Optional[str]:
            for col in df.columns:
                if any(kw in col.lower() for kw in palabras):
                    return col
            return None

        return {
            "col_campana":   buscar(["campa", "campaign", "campaign_name"]) or df.columns[0],
            "col_adset":     buscar(["adset", "ad_set", "conjunto"]),
            "col_ad":        buscar(["_ad", "anuncio", "creative"]),
            "col_leads":     buscar(["id", "lead_id", "contact"]),
            "col_estado":    buscar(["estado", "status", "stage", "etapa", "funnel"]),
            "col_inversion": buscar(["costo", "cost", "spend", "inversion", "gasto"]),
            "col_valor":     buscar(["valor", "value", "revenue", "venta", "ingreso"]),
            "col_fecha":     buscar(["fecha", "date", "created", "timestamp", "ts"]),
            "estado_mql":    "mql",
            "estado_sql":    "sql",
            "estado_venta":  "venta",
            "moneda":        "USD",
        }

    def mapear(self, df, cache_key: str = None) -> dict:
        """
        Infiere la config de columnas para el DataFrame dado.

        Args:
            df:        DataFrame con las columnas a mapear
            cache_key: clave opcional para cachear (ej: sheet_id)

        Returns:
            dict compatible con MetricsCalculator(config=...)
        """
        # Generar cache key desde el header si no se provee
        if cache_key is None:
            cache_key = str(sorted(df.columns.tolist()))

        if cache_key in self.cache:
            logger.info(f"ColumnMapper: usando config cacheada para {cache_key}")
            return self.cache[cache_key]

        print(f"\n[ColumnMapper] Inferiendo estructura de columnas con LLM...")

        try:
            prompt  = self._construir_prompt(df)
            raw     = self._llm_call(prompt)
            config  = self._parsear_config(raw)

            if config is None:
                raise ValueError("LLM no retornó JSON válido")

            # Normalizar nulos
            for key, val in config.items():
                if val in ("null", "None", "", "N/A"):
                    config[key] = None

            # Asegurar moneda por defecto
            if not config.get("moneda"):
                config["moneda"] = "USD"

            self.cache[cache_key] = config

            print(f"[ColumnMapper] Mapeo inferido:")
            for k, v in config.items():
                icono = "OK" if v else "--"
                print(f"  [{icono}]  {k:18} : {v}")

            return config

        except Exception as e:
            logger.warning(f"ColumnMapper: LLM falló ({e}), usando keyword fallback")
            print(f"[ColumnMapper] LLM no disponible — usando detección por palabras clave")
            config = self._fallback_keyword(df)
            self.cache[cache_key] = config
            return config
