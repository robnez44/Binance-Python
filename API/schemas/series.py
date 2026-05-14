from __future__ import annotations
from typing import Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel

class CandleResponse(BaseModel):
    symbol: str
    interval: str
    open_time: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    close_time: datetime
    quote_asset_volume: float
    number_of_trades: int
    taker_buy_base_asset_volume: float
    taker_buy_quote_asset_volume: float

class SegmentMetricsResponse(BaseModel):
    symbol: str
    interval: str
    start_idx: int
    end_idx: int
    length: int
    a: float
    b: float
    r2: float
    pct_slope: float
    mean_price: float
    regime: str
    start_time: datetime
    end_time: datetime
    start_price: float
    end_price: float

class EMASnapshotResponse(BaseModel):
    symbol: str
    interval: str
    timestamp: datetime
    span: int
    price: float
    ema_value: float
    abs_slope: float
    pct_slope: float
    distance: float
    distance_pct: float

class ADXSnapshotResponse(BaseModel):
    symbol: str
    interval: str
    timestamp: datetime
    plus_di: float
    minus_di: float
    dx: float
    adx: float


class SMISnapshotResponse(BaseModel):
    symbol: str
    interval: str
    timestamp: datetime
    smi: float

class SRLevelResponse(BaseModel):
    symbol: str
    interval: str
    idx: int
    timestamp: datetime
    price: float
    level_type: str
    touches: Optional[int] = 0

class SeriesDataResponse(BaseModel):
    symbol: str
    interval: str
    start_time: datetime
    end_time: datetime
    start_price: float
    end_price: float
    total_candles: int
    trends: Optional[List[SegmentMetricsResponse]] = None
    candles: Optional[List[CandleResponse]] = None
    ema_points: Optional[Dict[str, List[EMASnapshotResponse]]] = None
    adx_points: Optional[List[ADXSnapshotResponse]] = None
    smi_points: Optional[List[SMISnapshotResponse]] = None
    sr_levels: Optional[List[SRLevelResponse]] = None
