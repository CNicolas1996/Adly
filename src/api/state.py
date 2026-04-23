import logging
from typing import Dict, Any, List
from src.ai.engine import AdlyEngine
import pandas as pd
from collections import OrderedDict

logger = logging.getLogger("adly.api.state")

class AppState:
    MAX_SESSIONS = 50

    def __init__(self):
        # In-memory storage for MVP
        self.config: Dict[str, Any] = {
            "model": "groq", # Default, should match what's in .env or frontend
            "api_key": "",
            "data_source": "mock",
            "sheet_id": None,
            "created_at": "2026-04-01T10:00:00Z"
        }
        
        # OrderedDicts para implementar política FIFO/LRU
        self.analyses: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.messages: OrderedDict[str, List[Dict[str, Any]]] = OrderedDict()
        self.dataset_info: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        
        # Engine instances and active DataFrames
        self.engines: OrderedDict[str, AdlyEngine] = OrderedDict()
        self.dataframes: OrderedDict[str, pd.DataFrame] = OrderedDict()

    def _enforce_limits(self):
        """Purges oldest sessions if max capacity is exceeded."""
        while len(self.analyses) > self.MAX_SESSIONS:
            oldest_id, _ = self.analyses.popitem(last=False)
            self.messages.pop(oldest_id, None)
            self.dataset_info.pop(oldest_id, None)
            self.engines.pop(oldest_id, None)
            self.dataframes.pop(oldest_id, None)
            logger.info(f"Purged session {oldest_id} due to memory limits.")

    def add_analysis(self, analysis_id: str, data: Dict[str, Any], df: pd.DataFrame, engine: AdlyEngine, dataset_info: Dict[str, Any], initial_msg: Dict[str, Any]):
        self.analyses[analysis_id] = data
        self.dataframes[analysis_id] = df
        self.engines[analysis_id] = engine
        self.dataset_info[analysis_id] = dataset_info
        self.messages[analysis_id] = [initial_msg]
        self._enforce_limits()

state = AppState()

