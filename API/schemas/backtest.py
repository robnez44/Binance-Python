from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

# ══════════════════════════════════════════════════════════════════════════════
#  REQUEST
#  Espejo tipado de BacktestConfig + parámetros de rango temporal.
#  Los porcentajes se reciben como número entero (2 = 2%) y el servicio
#  los convierte a decimal antes de pasarlos a BacktestConfig.  
# ══════════════════════════════════════════════════════════════════════════════
class BacktestRequest(BaseModel):
    # Rango temporal
    symbol:     str = Field("BTCUSDT", description="Par de trading, ej: BTCUSDT")
    interval:   str = Field("4h",      description="Temporalidad: 1h, 4h, 1d, etc.")
    start_time: str = Field(...,       description="Fecha inicio UTC — YYYY-MM-DD o YYYY-MM-DD HH:MM")
    end_time:   Optional[str] = Field(None, description="Fecha fin UTC (opcional, None = hasta el último candle disponible)")

    # Capital
    initial_capital: float = Field(10_000.0, gt=0,  description="Capital inicial en USDT")
    leverage:        float = Field(1.0,      ge=1.0, description="Apalancamiento (1 = sin apalancamiento)")

    # Gestion de riesgo, todos opcionales, None = desactivado
    stop_loss_pct:         Optional[float] = Field(None, description="Stop Loss en % (ej: 2 = 2%). None = desactivado")
    take_profit_pct:       Optional[float] = Field(None, description="Take Profit en % (ej: 5 = 5%). None = desactivado")
    breakeven_trigger_pct: Optional[float] = Field(None, description="Breakeven trigger en %. None = desactivado")

    # Estrategia EMA
    min_slope_pct:      float = Field(0.08, ge=0.0, description="Pendiente mínima EMA 10 en % para validar cruce")
    exit_slope_periods: int   = Field(2,    ge=1,   description="Velas consecutivas con pendiente negativa para confirmar salida")
    ema_gap_min_pct:    float = Field(0.0,  ge=0.0, description="Gap mínimo EMA10-EMA55 en % (0 = desactivado)")

    # Filtro ADX
    adx_min:           float = Field(0.0,  ge=0.0, description="ADX mínimo para confirmar tendencia (0 = desactivado)")
    adx_require_di:    bool  = Field(True,          description="Exigir +DI > -DI en la entrada")
    adx_require_rising: bool = Field(False,          description="Exigir que el ADX sea no decreciente en la entrada")

    # ATR stops dinamicos
    atr_period:        int            = Field(14,  ge=1, description="Periodo del ATR")
    atr_stop_mult:     Optional[float] = Field(1.8,      description="Multiplicador ATR para stop inicial (None = desactivado)")
    atr_trailing_mult: Optional[float] = Field(2.2,      description="Multiplicador ATR para trailing stop (None = desactivado)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "symbol": "BTCUSDT",
                "interval": "4h",
                "start_time": "2026-01-01",
                "end_time": "2026-03-01",
                "initial_capital": 10000,
                "leverage": 1,
                "min_slope_pct": 0.08,
                "exit_slope_periods": 2,
                "adx_min": 23,
                "atr_stop_mult": 1.8,
                "atr_trailing_mult": 2.2,
            }
        }
    }

# ══════════════════════════════════════════════════════════════════════════════
#  RESPONSE — espejo de Trade, BacktestConfig y BacktestResult de records.py
# ══════════════════════════════════════════════════════════════════════════════
class TradeResponse(BaseModel):
    """Espejo de backtesting.records.Trade"""
    entry_time:    datetime
    exit_time:     datetime
    side:          str
    entry_price:   float
    exit_price:    float
    quantity:      float
    pnl:           float
    return_pct:    float
    candles_held:  int
    exit_reason:   str
    equity_before: float
    equity_after:  float

class BacktestConfigResponse(BaseModel):
    """Espejo de backtesting.records.BacktestConfig"""
    initial_capital:         float
    leverage:                float
    stop_loss_pct:           Optional[float]
    take_profit_pct:         Optional[float]
    breakeven_trigger_pct:   Optional[float]
    min_slope_pct:           float
    exit_slope_periods:      int
    ema_gap_min_pct:         float
    adx_min:                 float
    adx_require_di:          bool
    adx_require_rising:      bool
    atr_period:              int
    atr_stop_mult:           Optional[float]
    atr_trailing_mult:       Optional[float]
    atr_stop_confirm_on_close: bool

class BacktestResponse(BaseModel):
    """
    Respuesta completa de un backtest.
    Espejo de backtesting.records.BacktestResult + id de MongoDB.
    Incluye todos los trades y la configuración usada.
    """
    id:            str

    # Identificadores
    symbol:        str
    interval:      str
    strategy_name: str
    start_time:    Optional[datetime]
    end_time:      Optional[datetime]
    created_at:    Optional[datetime]

    # Metricas de rendimiento
    initial_capital:      float
    final_capital:        float
    total_return_pct:     float
    max_drawdown_pct:     float

    # Metricas de trades
    total_trades:         int
    winning_trades:       int
    losing_trades:        int
    win_rate_pct:         float
    profit_factor:        float
    avg_trade_return_pct: float

    # Detalle completo
    trades: List[TradeResponse]
    config: Optional[BacktestConfigResponse]