import logging
from typing import Dict, Any, List
from src.ai.engine import AdlyEngine
import pandas as pd
from collections import OrderedDict

logger = logging.getLogger("adly.api.state")

class AppState:
    MAX_SESSIONS = 50

    def __init__(self):
        self.config: Dict[str, Any] = {
            "model": "groq",
            "api_key": "",
            "data_source": "mock",
            "sheet_id": None,
            "created_at": "2026-04-01T10:00:00Z"
        }

        self.analyses: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.messages: OrderedDict[str, List[Dict[str, Any]]] = OrderedDict()
        self.dataset_info: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.engines: OrderedDict[str, AdlyEngine] = OrderedDict()
        self.dataframes: OrderedDict[str, pd.DataFrame] = OrderedDict()
        self.normalization_reports: Dict[str, Dict] = {}
        self.pending_model: Dict[str, Dict] = {}
        self.modelo_activo: str = "groq"

        # SemanticSchema por sesión — fuente única de verdad del schema detectado.
        # Se guarda al cargar el dataset y se reutiliza en todos los comandos.
        self.semantic_schemas: OrderedDict[str, Any] = OrderedDict()

        # SemanticInferencer — instancia única, modelo cargado 1 vez al arrancar FastAPI.
        # No instanciar por request — cold start de ~3-5s por carga de torch.
        self._semantic_inferencer = None

    @property
    def semantic_inferencer(self):
        """Lazy init — carga el modelo la primera vez que se accede."""
        if self._semantic_inferencer is None:
            try:
                from src.processing.semantic_inferencer import SemanticInferencer
                logger.info("[AppState] Cargando SemanticInferencer (primera vez)...")
                self._semantic_inferencer = SemanticInferencer()
                logger.info("[AppState] SemanticInferencer listo.")
            except Exception as e:
                logger.error(f"[AppState] SemanticInferencer no disponible: {e}")
                self._semantic_inferencer = None
        return self._semantic_inferencer

    def _enforce_limits(self):
        """Purges oldest sessions if max capacity is exceeded."""
        while len(self.analyses) > self.MAX_SESSIONS:
            oldest_id, _ = self.analyses.popitem(last=False)
            self.messages.pop(oldest_id, None)
            self.dataset_info.pop(oldest_id, None)
            self.engines.pop(oldest_id, None)
            self.dataframes.pop(oldest_id, None)
            self.normalization_reports.pop(oldest_id, None)
            self.semantic_schemas.pop(oldest_id, None)
            logger.info(f"Purged session {oldest_id} due to memory limits.")

    def add_analysis(
        self,
        analysis_id: str,
        data: Dict[str, Any],
        df: pd.DataFrame,
        engine: AdlyEngine,
        dataset_info: Dict[str, Any],
        initial_msg: Dict[str, Any],
        normalization_report: Dict = None,
        semantic_schema=None,
    ):
        self.analyses[analysis_id] = data
        self.dataframes[analysis_id] = df
        self.engines[analysis_id] = engine
        self.dataset_info[analysis_id] = dataset_info
        self.messages[analysis_id] = [initial_msg]
        if normalization_report is not None:
            self.normalization_reports[analysis_id] = normalization_report
        if semantic_schema is not None:
            self.semantic_schemas[analysis_id] = semantic_schema
        self._enforce_limits()

state = AppState()
