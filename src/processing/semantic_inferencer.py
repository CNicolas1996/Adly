"""
semantic_inferencer.py — Adly · Data-Buddy
-------------------------------------------
Capa semántica transversal. Corre UNA VEZ por dataset nuevo.
Reemplaza toda búsqueda por nombre exacto y toda lista de aliases.

Qué hace:
    CAPA 1 — Heurísticas estadísticas (0 LLM, 0 embeddings)
        Detecta tipos por contenido: email, teléfono, fecha, numérico, ID, categórico.

    CAPA 2 — Embeddings semánticos
        Mapea nombres de columna del cliente al schema canónico de Adly.
        Usa similitud coseno entre embeddings de columnas vs descripciones canónicas.
        Si confianza < threshold → fallback a ColumnMapper LLM.

    CAPA 3 — Mapeo de valores categóricos
        Para columnas de stage/estado: mapea valores del cliente al vocabulario
        canónico de Adly usando embeddings. No hay lista hardcodeada del cliente.

Resultado: SemanticSchema — fuente única de verdad para todos los módulos downstream.

Uso:
    inferencer = SemanticInferencer()          # carga modelo 1 vez, cachea
    schema = inferencer.analizar(df)           # corre las 3 capas
    df, reporte = normalizar(df, schema)       # normalizer usa schema
    calc = MetricsCalculator(schema.as_config()) # metrics usa schema

Pipeline completo:
    CSV → SemanticInferencer → SemanticSchema → normalizer → MetricsCalculator → engine
"""

import re
import logging
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("adly.semantic_inferencer")


# ===========================================================================
# VOCABULARIO CANÓNICO DE ADLY
# Este SÍ se hardcodea — es el vocabulario de Adly, no del cliente.
# Lo agnóstico es el mapeo cliente→canónico, no el canónico mismo.
# ===========================================================================

# Schema canónico — qué columna es qué en el universo de Adly
SCHEMA_CANONICO = {
    "col_email":     "email address correo electronico campo de email del contacto formato usuario arroba dominio",
    "col_phone":     "phone number telefono celular numero de contacto movil digitos numericos formato telefono",
    "col_name":      "nombre completo full name nombre del contacto persona cliente texto alfabetico",
    "col_date":      "fecha date timestamp fecha de creacion fecha de registro created_at formato fecha año mes dia",
    "col_id":        "ID identificador unico ghl_id contact_id lead_id uuid codigo alfanumerico clave primaria",
    "col_campana":   "campaign nombre de campaña publicitaria nivel mas alto agrupa adsets",
    "col_adset":     "adset ad_set conjunto de anuncios nivel intermedio dentro de campaña agrupa ads",
    "col_ad":        "ad anuncio creativo nombre del anuncio nivel mas especifico debajo del adset",
    "col_estado":    "estado stage status etapa pipeline funnel embudo estado del lead",
    "col_inversion": "costo_lead costo gasto spend inversion amount_spent dinero invertido en publicidad pauta numerico float",
    "col_valor":     "valor_venta valor de venta ingreso revenue monto ganado deal_value numerico float",
}

# Vocabulario canónico de stages de Adly
# Cada entrada: descripción semántica → etiqueta canónica
STAGES_CANONICOS = {
    "lead":              "lead nuevo prospecto inicial primer contacto recién llegó registro nuevo sin calificar entrada al funnel",
    "mql":               "MQL marketing qualified lead calificado por marketing cualificado interesado MQL",
    "sql":               "SQL sales qualified lead lead calificado por ventas listo para hablar con un vendedor",
    "lead_caliente":     "warm lead lead caliente muy interesado hot lead a punto de comprar",
    "lead_frio":         "cold lead lead frío poco interés sin respuesta fría",
    "contactado":        "contactado contacted ya se habló primer contacto realizado",
    "no_contactado":     "no contactado unreachable no responde no se pudo contactar",
    "seguimiento":       "seguimiento follow up en proceso nurturing",
    "cita_agendada":     "cita agendada appointment set reunión programada demo agendado scheduled",
    "no_se_presento":    "no show no se presentó no asistió ghost faltó a la cita",
    "venta":             "venta cerrada closed won ganado vendido cliente nuevo sale won",
    "perdido":           "perdido closed lost no compró descartado no calificó lost churned",
    "duplicado":         "duplicado duplicate registro repetido mismo contacto dos veces",
    "spam":              "spam bot lead falso inválido basura fake",
}

# Threshold de confianza para aceptar mapeo por embeddings
# Por debajo de esto → fallback a ColumnMapper LLM
THRESHOLD_COLUMNAS = 0.38   # bajado: nombres técnicos cortos embedean con scores menores
THRESHOLD_STAGES   = 0.35   # bajado: mql/sql son siglas técnicas

# Matching directo por nombre de columna — corre ANTES de embeddings
# Si el nombre de la columna contiene alguna de estas palabras → asignación directa
# Esto NO es hardcodeo del cliente — son patrones universales de nombres de columna
NOMBRE_DIRECTO = {
    "col_email":     ["email", "correo", "e-mail", "e_mail", "mail"],
    "col_phone":     ["phone", "telefono", "celular", "tel", "mobile", "movil", "cel"],
    "col_name":      ["nombre", "name", "full_name", "fullname", "contacto"],
    "col_date":      ["fecha", "date", "created", "timestamp", "creacion", "registro"],
    "col_id":        ["_id", "ghl_id", "contact_id", "lead_id", "uuid", "id_"],
    "col_campana":   ["campana", "campaign", "camp"],
    "col_adset":     ["adset", "ad_set", "conjunto"],
    "col_ad":        ["_ad", "ad_name", "anuncio", "creativo"],
    "col_estado":    ["estado", "stage", "status", "etapa", "funnel"],
    "col_inversion": ["costo", "cost", "spend", "inversion", "gasto", "budget", "amount"],
    "col_valor":     ["valor", "value", "revenue", "venta", "ingreso", "sale"],
}


# ===========================================================================
# SEMANTIC SCHEMA — fuente única de verdad
# ===========================================================================

@dataclass
class SemanticSchema:
    """
    Resultado del SemanticInferencer. Fuente única de verdad para:
      - ingestion_normalizer.py
      - MetricsCalculator
      - validación, alertas, análisis de formas normales

    Todos los campos son Optional[str] — None significa "no detectado".
    confidence contiene el score de cada mapeo para transparencia.
    warnings acumula casos ambiguos o de baja confianza.
    """
    # Columnas de contacto
    col_email:     Optional[str] = None
    col_phone:     Optional[str] = None
    col_name:      Optional[str] = None
    col_date:      Optional[str] = None
    col_id:        Optional[str] = None

    # Columnas de marketing
    col_campana:   Optional[str] = None
    col_adset:     Optional[str] = None
    col_ad:        Optional[str] = None
    col_estado:    Optional[str] = None
    col_inversion: Optional[str] = None
    col_valor:     Optional[str] = None

    # Mapeo de valores categóricos cliente → canónico
    # Ej: {"Closed Won": "venta", "No Show": "no_se_presento"}
    value_map_stages: dict = field(default_factory=dict)

    # Columnas de atribución detectadas semánticamente
    # Lista de nombres de columna que parecen contener atribución de anuncios
    attribution_columns: list = field(default_factory=list)

    # Metadatos de confianza
    confidence:  dict = field(default_factory=dict)   # {campo: score}
    warnings:    list = field(default_factory=list)   # mensajes de baja confianza
    fuente:      str  = "semantic_inferencer"

    def as_config(self) -> dict:
        """
        Convierte el schema al formato dict que espera MetricsCalculator(config=...).
        Compatible con el contrato existente — no rompe nada downstream.
        """
        # Inferir estado_mql/sql/venta desde value_map_stages
        estado_mql   = self._buscar_canonico("lead_caliente") or self._buscar_canonico("lead")
        estado_sql   = self._buscar_canonico("cita_agendada") or self._buscar_canonico("contactado")
        estado_venta = self._buscar_canonico("venta")

        return {
            "col_campana":   self.col_campana,
            "col_adset":     self.col_adset,
            "col_ad":        self.col_ad,
            "col_leads":     self.col_id,
            "col_estado":    self.col_estado,
            "col_inversion": self.col_inversion,
            "col_valor":     self.col_valor,
            "col_fecha":     self.col_date,
            "estado_mql":    estado_mql,
            "estado_sql":    estado_sql,
            "estado_venta":  estado_venta,
            "moneda":        "USD",   # default — override con detección futura
        }

    def _buscar_canonico(self, etiqueta_canonica: str) -> Optional[str]:
        """
        Busca en value_map_stages el valor del cliente que mapea a una etiqueta canónica.
        Retorna el primer valor encontrado o None.
        """
        for valor_cliente, canonico in self.value_map_stages.items():
            if canonico == etiqueta_canonica:
                return valor_cliente
        return None

    def resumen(self) -> str:
        """Resumen legible del schema inferido — para logs y CLI."""
        lineas = ["[SemanticSchema] Columnas detectadas:"]
        campos = [
            ("col_email",     self.col_email),
            ("col_phone",     self.col_phone),
            ("col_name",      self.col_name),
            ("col_date",      self.col_date),
            ("col_id",        self.col_id),
            ("col_campana",   self.col_campana),
            ("col_adset",     self.col_adset),
            ("col_ad",        self.col_ad),
            ("col_estado",    self.col_estado),
            ("col_inversion", self.col_inversion),
            ("col_valor",     self.col_valor),
        ]
        for nombre, valor in campos:
            conf  = self.confidence.get(nombre, 0)
            icono = "✅" if valor else "❌"
            conf_str = f" (conf: {conf:.2f})" if valor else ""
            lineas.append(f"  {icono} {nombre:16}: {valor or 'no detectado'}{conf_str}")

        if self.value_map_stages:
            lineas.append(f"\n  Stages mapeados ({len(self.value_map_stages)}):")
            for cliente, canonico in list(self.value_map_stages.items())[:8]:
                lineas.append(f"    '{cliente}' → '{canonico}'")

        if self.attribution_columns:
            lineas.append(f"\n  Columnas de atribución: {self.attribution_columns}")

        if self.warnings:
            lineas.append(f"\n  ⚠️  Advertencias ({len(self.warnings)}):")
            for w in self.warnings:
                lineas.append(f"    • {w}")

        return "\n".join(lineas)


# ===========================================================================
# SEMANTIC INFERENCER
# ===========================================================================

class SemanticInferencer:
    """
    Infiere semántica de cualquier DataFrame sin asumir nombres de columna.

    El modelo de embeddings se carga UNA VEZ y se cachea en la instancia.
    Para FastAPI: instanciar en state.py al arrancar, no por request.

    Uso:
        # En state.py (1 vez al arrancar):
        inferencer = SemanticInferencer()

        # Por cada dataset nuevo:
        schema = inferencer.analizar(df)
    """

    _MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

    def __init__(self):
        self._model        = None   # cargado lazy en primer uso
        self._vocab_embeds = {}     # cache de embeddings del vocabulario canónico
        # NOTA: si cambias SCHEMA_CANONICO o STAGES_CANONICOS,
        # instancia un SemanticInferencer nuevo para que recalcule el cache

    def _cargar_modelo(self):
        """Carga el modelo de embeddings. Solo corre la primera vez."""
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Cargando modelo de embeddings: {self._MODEL_NAME}")
            self._model = SentenceTransformer(self._MODEL_NAME)
            logger.info("Modelo cargado OK")
        except Exception as e:
            raise RuntimeError(
                f"[SemanticInferencer] No se pudo cargar el modelo de embeddings: {e}\n"
                f"Verifica que sentence-transformers esté instalado correctamente."
            )

    def _embed(self, textos: list[str]) -> np.ndarray:
        """Genera embeddings para una lista de textos."""
        self._cargar_modelo()
        return self._model.encode(textos, convert_to_numpy=True, show_progress_bar=False)

    def _similitud_coseno(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """
        Similitud coseno entre un vector a y una matriz b.
        a: (dim,) — embedding de una columna
        b: (n, dim) — embeddings del vocabulario canónico
        Retorna: (n,) — score por cada entrada del vocabulario
        """
        a_norm = a / (np.linalg.norm(a) + 1e-9)
        b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-9)
        return b_norm @ a_norm

    # ── CAPA 1 — Heurísticas estadísticas ──────────────────────────────────

    def _detectar_tipos_estadisticos(self, df: pd.DataFrame) -> dict[str, str]:
        """
        Detecta el tipo semántico de cada columna por su contenido.
        Sin LLM, sin embeddings — solo heurísticas sobre los datos.

        Retorna dict {nombre_columna: tipo_detectado}
        Tipos: "email" | "phone" | "date" | "numeric_id" | "numeric" | "categorical" | "text"
        """
        _EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')
        _PHONE_RE = re.compile(r'^\+?[\d\s\-\(\)]{7,20}$')

        tipos = {}
        for col in df.columns:
            serie = df[col].dropna()
            if len(serie) == 0:
                tipos[col] = "empty"
                continue

            n_total = len(serie)

            # ── Numérico ──────────────────────────────────────────────────
            if pd.api.types.is_numeric_dtype(serie.dtype):
                n_unicos = serie.nunique()
                if n_unicos / n_total > 0.95 and n_unicos > 20:
                    tipos[col] = "numeric_id"
                else:
                    tipos[col] = "numeric"
                continue

            # ── Datetime ya parseado ──────────────────────────────────────
            if pd.api.types.is_datetime64_any_dtype(serie.dtype):
                tipos[col] = "date"
                continue

            # ── String — detectar por contenido ──────────────────────────
            muestra = serie.astype(str).head(min(50, n_total))

            # Email
            n_email = muestra.apply(lambda x: bool(_EMAIL_RE.match(x.strip()))).sum()
            if n_email / len(muestra) >= 0.70:
                tipos[col] = "email"
                continue

            # Teléfono
            n_phone = muestra.apply(lambda x: bool(_PHONE_RE.match(x.strip()))).sum()
            if n_phone / len(muestra) >= 0.70:
                tipos[col] = "phone"
                continue

            # Fecha como string
            try:
                parsed = pd.to_datetime(muestra, errors="coerce")
                if parsed.notna().sum() / len(muestra) >= 0.70:
                    tipos[col] = "date"
                    continue
            except Exception:
                pass

            # ID string (uuid, códigos únicos)
            n_unicos = serie.nunique()
            if n_unicos / n_total > 0.95 and n_unicos > 20:
                tipos[col] = "string_id"
                continue

            # Categórico vs texto libre
            if n_unicos <= 50:
                tipos[col] = "categorical"
            else:
                tipos[col] = "text"

        return tipos

    # ── CAPA 2 — Mapeo semántico de columnas ───────────────────────────────

    def _mapear_columnas(
        self,
        df: pd.DataFrame,
        tipos: dict[str, str]
    ) -> tuple[dict[str, Optional[str]], dict[str, float]]:
        """
        Mapea columnas del cliente al schema canónico de Adly via embeddings.

        Estrategia:
          1. Embed nombres de columna + muestra de valores del cliente
          2. Embed descripciones canónicas de Adly (cacheado)
          3. Similitud coseno → asignar columna con mayor score si > threshold
          4. Cada columna canónica solo puede tener UN ganador

        Retorna:
          mapeo:      {campo_canonico: nombre_columna_cliente}
          confianza:  {campo_canonico: score}
        """
        # Pre-filtros por tipo estadístico — solo casos muy claros
        # Relajados intencionalmente: mejor falso positivo que perder columna válida
        FILTROS_TIPO = {
            "col_email":     {"email"},
            "col_phone":     {"phone", "numeric"},   # telefono puede ser int64
            "col_date":      {"date"},
            "col_id":        {"numeric_id", "string_id", "text", "categorical"},
            "col_inversion": {"numeric"},
            "col_valor":     {"numeric"},
            "col_name":      {"text", "categorical", "string_id"},  # nombre no es numerico
            # campana/adset/ad/estado: sin filtro — el embedding decide
        }

        # Construir texto representativo por columna
        # Nombre repetido 3 veces = más peso semántico en el embedding
        # Ej: "campana campana campana: AI_AUTOMATION, WhatsApp"
        textos_columnas = {}
        for col in df.columns:
            muestra = df[col].dropna().astype(str).head(5).tolist()
            muestra_str = ", ".join(muestra[:3]) if muestra else ""
            textos_columnas[col] = f"{col} {col} {col}: {muestra_str}"

        cols_lista   = list(textos_columnas.keys())
        textos_lista = list(textos_columnas.values())

        # ── Paso 0: matching directo por nombre de columna ────────────────
        # Corre ANTES de embeddings — si el nombre contiene un patrón conocido
        # se asigna directamente con confianza 0.99 y se reserva la columna.
        mapeo_directo    = {}
        asignadas_previas = set()
        for campo, patrones in NOMBRE_DIRECTO.items():
            for col in cols_lista:
                col_lower = col.lower()
                if any(p in col_lower for p in patrones):
                    if col not in asignadas_previas and campo not in mapeo_directo:
                        mapeo_directo[campo]  = col
                        asignadas_previas.add(col)
                        break

        # Embeddings de columnas del cliente
        embeds_cols = self._embed(textos_lista)

        # Embeddings del vocabulario canónico (cacheados)
        campos_canonicos = list(SCHEMA_CANONICO.keys())
        descs_canonicas  = list(SCHEMA_CANONICO.values())

        if "schema_canonico" not in self._vocab_embeds:
            self._vocab_embeds["schema_canonico"] = self._embed(descs_canonicas)
        embeds_canonico = self._vocab_embeds["schema_canonico"]

        # Matriz de similitud: (n_columnas_cliente, n_campos_canonicos)
        scores = np.array([
            self._similitud_coseno(embeds_cols[i], embeds_canonico)
            for i in range(len(cols_lista))
        ])
        # scores[i][j] = similitud entre columna i del cliente y campo canónico j

        # Inicializar con los mapeos directos ya encontrados
        mapeo     = {campo: mapeo_directo.get(campo) for campo in campos_canonicos}
        confianza = {campo: (0.99 if mapeo_directo.get(campo) else 0.0) for campo in campos_canonicos}
        asignadas = set(asignadas_previas)  # columnas ya reservadas por matching directo

        # Asignar de mayor a menor score global (greedy)
        # Esto evita que dos campos canónicos compitan por la misma columna
        pares = []
        for j, campo in enumerate(campos_canonicos):
            for i, col in enumerate(cols_lista):
                pares.append((scores[i][j], campo, col, j, i))

        pares.sort(reverse=True)

        for score, campo, col, j, i in pares:
            if mapeo[campo] is not None:
                continue  # campo ya asignado
            if col in asignadas:
                continue  # columna ya usada

            # Filtro por tipo estadístico si aplica
            tipos_permitidos = FILTROS_TIPO.get(campo)
            if tipos_permitidos and tipos.get(col) not in tipos_permitidos:
                continue

            if score >= THRESHOLD_COLUMNAS:
                mapeo[campo]     = col
                confianza[campo] = float(score)
                asignadas.add(col)

        return mapeo, confianza

    # ── CAPA 3 — Mapeo de valores categóricos ──────────────────────────────

    def _mapear_stages(
        self,
        df: pd.DataFrame,
        col_estado: Optional[str]
    ) -> dict[str, str]:
        """
        Mapea valores únicos del cliente en la columna de estado al vocabulario
        canónico de Adly via embeddings.

        Sin lista hardcodeada del cliente. El embedding decide si "Closed Won"
        es "venta" y si "No Show" es "no_se_presento".

        Retorna:
            {valor_cliente: etiqueta_canonica}
            Solo incluye mapeos con score > THRESHOLD_STAGES.
        """
        if col_estado is None or col_estado not in df.columns:
            return {}

        valores_cliente = (
            df[col_estado]
            .dropna()
            .astype(str)
            .str.strip()
            .unique()
            .tolist()
        )

        if not valores_cliente:
            return {}

        # ── Paso 0: matching directo de stages por nombre exacto/contenido ──
        # Siglas como mql/sql/lead no embedean bien — se mapean directo
        STAGE_DIRECTO = {
            "lead":            "lead",
            "leads":           "lead",
            "mql":             "mql",
            "sql":             "sql",
            "venta":           "venta",
            "ventas":          "venta",
            "won":             "venta",
            "closed won":      "venta",
            "perdido":         "perdido",
            "lost":            "perdido",
            "closed lost":     "perdido",
            "duplicado":       "duplicado",
            "duplicate":       "duplicado",
            "spam":            "spam",
            "no show":         "no_se_presento",
            "no se presento":  "no_se_presento",
            "appointment set": "cita_agendada",
            "cita agendada":   "cita_agendada",
            "follow up":       "seguimiento",
            "seguimiento":     "seguimiento",
            "contactado":      "contactado",
            "contacted":       "contactado",
            "warm lead":       "lead_caliente",
            "hot lead":        "lead_caliente",
            "cold lead":       "lead_frio",
        }
        value_map_directo = {}
        valores_pendientes = []
        for valor in valores_cliente:
            clave = valor.lower().strip()
            if clave in STAGE_DIRECTO:
                value_map_directo[valor] = STAGE_DIRECTO[clave]
            else:
                valores_pendientes.append(valor)

        # Si todos mapearon directo, retornar ya
        if not valores_pendientes:
            return value_map_directo

        # Solo embedear los que no mapearon directo
        valores_cliente = valores_pendientes

        # Embeddings de valores del cliente
        embeds_valores = self._embed(valores_cliente)

        # Embeddings del vocabulario canónico de stages (cacheados)
        etiquetas_canonicas = list(STAGES_CANONICOS.keys())
        descs_canonicas     = list(STAGES_CANONICOS.values())

        if "stages_canonicos" not in self._vocab_embeds:
            self._vocab_embeds["stages_canonicos"] = self._embed(descs_canonicas)
        embeds_stages = self._vocab_embeds["stages_canonicos"]

        value_map = {}
        for i, valor in enumerate(valores_cliente):
            scores = self._similitud_coseno(embeds_valores[i], embeds_stages)
            mejor_idx   = int(np.argmax(scores))
            mejor_score = float(scores[mejor_idx])

            if mejor_score >= THRESHOLD_STAGES:
                value_map[valor] = etiquetas_canonicas[mejor_idx]
            else:
                logger.debug(
                    f"Stage '{valor}' no mapeado (mejor score: {mejor_score:.2f} < {THRESHOLD_STAGES})"
                )

        # Merge: directo + embeddings
        value_map_directo.update(value_map)
        return value_map_directo


    # ── Detección de columnas de atribución ────────────────────────────────

    def _detectar_atribucion(
        self,
        df: pd.DataFrame,
        col_ad: Optional[str]
    ) -> list[str]:
        """
        Detecta columnas que parecen contener atribución de anuncios.
        Busca columnas relacionadas semánticamente con "anuncio" o "atribución"
        que no sean la columna principal de ad.

        Retorna lista de nombres de columna candidatas.
        """
        candidatos_texto = [
            f"{col}: {df[col].dropna().astype(str).head(3).tolist()}"
            for col in df.columns
            if col != col_ad
        ]
        if not candidatos_texto:
            return []

        desc_atribucion = [
            "columna de atribución de anuncio o ad o campaña que originó el lead",
            "columna de segunda atribución o último anuncio que tocó al lead",
        ]

        embeds_cols  = self._embed(candidatos_texto)
        embeds_attr  = self._embed(desc_atribucion)

        cols_lista = [col for col in df.columns if col != col_ad]
        atribucion = []

        for i, col in enumerate(cols_lista):
            scores = self._similitud_coseno(embeds_cols[i], embeds_attr)
            if float(np.max(scores)) >= THRESHOLD_COLUMNAS:
                atribucion.append(col)

        return atribucion

    # ── MÉTODO PRINCIPAL ───────────────────────────────────────────────────

    def analizar(self, df: pd.DataFrame, cache_key: str = None) -> SemanticSchema:
        """
        Corre las 3 capas de inferencia y retorna un SemanticSchema completo.

        Args:
            df:        DataFrame con los datos del cliente (ya con columnas stripeadas)
            cache_key: clave opcional para cachear el schema (ej: sheet_id o csv_path)

        Returns:
            SemanticSchema — fuente única de verdad para el pipeline downstream
        """
        schema   = SemanticSchema()
        warnings = []

        print(f"\n[SemanticInferencer] Analizando dataset: {len(df)} filas · {len(df.columns)} columnas")

        # ── Capa 1 — tipos estadísticos ──────────────────────────────────
        print(f"[SemanticInferencer] Capa 1: detectando tipos estadísticos...")
        tipos = self._detectar_tipos_estadisticos(df)
        logger.debug(f"Tipos detectados: {tipos}")

        # ── Capa 2 — mapeo semántico de columnas ─────────────────────────
        print(f"[SemanticInferencer] Capa 2: mapeando columnas con embeddings...")
        try:
            mapeo, confianza = self._mapear_columnas(df, tipos)
        except Exception as e:
            warnings.append(f"Capa 2 falló ({e}) — usando fallback a ColumnMapper LLM")
            mapeo, confianza = self._fallback_column_mapper(df)

        # Asignar al schema
        schema.col_email     = mapeo.get("col_email")
        schema.col_phone     = mapeo.get("col_phone")
        schema.col_name      = mapeo.get("col_name")
        schema.col_date      = mapeo.get("col_date")
        schema.col_id        = mapeo.get("col_id")
        schema.col_campana   = mapeo.get("col_campana")
        schema.col_adset     = mapeo.get("col_adset")
        schema.col_ad        = mapeo.get("col_ad")
        schema.col_estado    = mapeo.get("col_estado")
        schema.col_inversion = mapeo.get("col_inversion")
        schema.col_valor     = mapeo.get("col_valor")
        schema.confidence    = confianza

        # Advertencias por baja confianza en campos críticos
        CRITICOS = ["col_campana", "col_estado", "col_id"]
        for campo in CRITICOS:
            if mapeo.get(campo) is None:
                warnings.append(
                    f"No se detectó '{campo}' con confianza suficiente. "
                    f"Algunos análisis estarán limitados."
                )

        # ── Capa 3 — mapeo de stages ─────────────────────────────────────
        if schema.col_estado:
            print(f"[SemanticInferencer] Capa 3: mapeando stages en '{schema.col_estado}'...")
            try:
                schema.value_map_stages = self._mapear_stages(df, schema.col_estado)
                n_mapeados = len(schema.value_map_stages)
                n_total    = df[schema.col_estado].dropna().nunique()
                if n_mapeados < n_total:
                    warnings.append(
                        f"{n_total - n_mapeados} stages no pudieron mapearse al vocabulario "
                        f"canónico de Adly. Se analizarán como 'otros'."
                    )
            except Exception as e:
                warnings.append(f"Mapeo de stages falló ({e}) — stages sin normalizar")
        else:
            warnings.append("No se detectó columna de estado/stage — análisis de embudo no disponible.")

        # ── Columnas de atribución ────────────────────────────────────────
        schema.attribution_columns = self._detectar_atribucion(df, schema.col_ad)

        schema.warnings = warnings

        print(schema.resumen())
        return schema

    def _fallback_column_mapper(self, df) -> tuple[dict, dict]:
        """
        Fallback al ColumnMapper LLM existente cuando los embeddings fallan.
        Convierte el resultado del ColumnMapper al formato interno de SemanticInferencer.
        """
        try:
            from src.processing.column_mapper import ColumnMapper
            mapper  = ColumnMapper()
            config  = mapper.mapear(df)
            mapeo   = {
                "col_email":     None,
                "col_phone":     None,
                "col_name":      None,
                "col_date":      config.get("col_fecha"),
                "col_id":        config.get("col_leads"),
                "col_campana":   config.get("col_campana"),
                "col_adset":     config.get("col_adset"),
                "col_ad":        config.get("col_ad"),
                "col_estado":    config.get("col_estado"),
                "col_inversion": config.get("col_inversion"),
                "col_valor":     config.get("col_valor"),
            }
            confianza = {k: 0.5 for k in mapeo}  # confianza media — viene de LLM
            return mapeo, confianza
        except Exception as e:
            logger.error(f"Fallback ColumnMapper también falló: {e}")
            # Retorna schema vacío — el normalizer y metrics manejan None
            mapeo     = {k: None for k in SCHEMA_CANONICO}
            confianza = {k: 0.0  for k in SCHEMA_CANONICO}
            return mapeo, confianza


# ===========================================================================
# MAIN — test rápido con CSV de prueba
# ===========================================================================

if __name__ == "__main__":
    import sys
    import os
    sys.path.append(".")

    csv_path = sys.argv[1] if len(sys.argv) > 1 else "data/raw/mock_ghl.csv"

    if not os.path.exists(csv_path):
        print(f"No se encontró: {csv_path}")
        sys.exit(1)

    print(f"\n>> Probando SemanticInferencer con: {csv_path}\n")

    df = pd.read_csv(csv_path)
    df.columns = [c.strip() for c in df.columns]

    inferencer = SemanticInferencer()
    schema     = inferencer.analizar(df)

    print("\n>> Config para MetricsCalculator:")
    import json
    print(json.dumps(schema.as_config(), indent=2))
