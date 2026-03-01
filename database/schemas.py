from typing import List, Dict
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SegmentMetrics:
    """Informacion de una tendencia identificada y saber que tan buena es la tendencia analizando su coeficiente de determinacion (r2) y su pendiente porcentual."""
    symbol: str             # "BTCUSDT"
    interval: str           # "4h", "1d"
    start_idx: int          # índice global (sobre toda la serie)
    end_idx: int            # índice global (inclusivo)
    length: int             # cantidad de velas en la subventana
    a: float                # pendiente de la recta y = a·x + b
    b: float                # intercepto
    r2: float               # coeficiente de determinación R²
    pct_slope: float        # pendiente porcentual: 100 * a / mean(y)
    mean_price: float       # precio medio del segmento
    regime: str             # 'UP' / 'DOWN' / 'SIDE'
    start_time: datetime    # fecha/hora inicio (UTC)
    end_time: datetime      # fecha/hora fin (UTC)
    start_price: float      # precio de cierre de la primera vela
    end_price: float        # precio de cierre de la última vela

@dataclass
class EMASnapshot:
    """
    Un punto de una EMA en una vela específica.
    """
    symbol: str             # "BTCUSDT"
    interval: str           # "4h", "1d"
    timestamp: datetime     # fecha/hora de la vela
    span: int               # 10, 55 o 200
    price: float            # precio de cierre del activo en esa vela
    ema_value: float        # valor de la EMA en esa vela
    abs_slope: float        # cambio absoluto vs vela anterior (USDT)
    pct_slope: float        # cambio porcentual vs vela anterior (%)
    distance: float         # precio - ema_value (positivo = precio arriba)
    distance_pct: float     # ((precio - ema_value) / ema_value) * 100

@dataclass
class AnalysisRecord:
    """
    Un documento en MongoDB.
    Representa el análisis completo de un rango temporal
    para un activo en una temporalidad específica.
    """
    symbol: str                                                             # "BTCUSDT"
    interval: str                                                           # "4h", "1d"
    start_time: datetime                                                    # inicio del rango analizado
    end_time: datetime                                                      # fin del rango analizado
    start_price: float                                                      # precio de cierre de la primera vela del rango
    end_price: float                                                        # precio de cierre de la última vela del rango
    total_candles: int                                                      # cuántas velas tiene el rango
    trends: List[SegmentMetrics]                                            # tendencias detectadas
    ema_points: Dict[str, List[EMASnapshot]] = field(default_factory=dict)  # EMAs agrupadas por span
    # ema_points = {
    #   "10":  [EMASnapshot, EMASnapshot, ...],
    #   "55":  [EMASnapshot, EMASnapshot, ...],
    #   "200": [EMASnapshot, EMASnapshot, ...],
    # }
    created_at: datetime = None