from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from API.schemas.backtest import BacktestConfigResponse

class SaveStrategyRequest(BaseModel):
    name: Optional[str] = Field(None, description="Nombre para la estrategia guardada")
    description: Optional[str] = Field(None, description="Descripción opcional")
    symbol: Optional[str] = Field(None, description="Símbolo al que apliuca, ej: EURUSDT")
    interval: Optional[str] = Field(None, description="Intervalo asociado, ej: 4h")
    config: BacktestConfigResponse

class StrategyRecordResponse(BaseModel):
    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    symbol: Optional[str] = None
    interval: Optional[str] = None
    config: BacktestConfigResponse
    created_at: Optional[datetime] = None