from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from src.api.state import state
import time

router = APIRouter(prefix="/api/config", tags=["config"])

class ConfigUpdate(BaseModel):
    model: str
    api_key: Optional[str] = None
    data_source: Optional[str] = None
    sheet_id: Optional[str] = None

@router.get("")
async def get_config():
    return state.config

@router.post("")
async def save_config(config: ConfigUpdate):
    state.config.update(config.dict(exclude_unset=True))
    return {"ok": True}

@router.post("/test")
async def test_connection(config: ConfigUpdate):
    # Simulate testing connection
    # Real implementation would attempt to ping the LLM provider
    time.sleep(1.0)
    return {"ok": True, "model": config.model, "latency_ms": 150}
