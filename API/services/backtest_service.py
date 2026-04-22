from __future__ import annotations
from typing import Optional
import numpy as np
import pandas as pd

from backtesting.records import BacktestConfig, BacktestResult, Trade
from backtesting.strategies import build_ema_long_signals
from backtesting.simulator import run_long_backtest
from database.repository import get_candles, save_backtest_result
from API.schemas.backtest import BacktestRequest, BacktestResponse, BacktestConfigResponse, TradeResponse
from utils.utils import parse_utc

def _trade_to_response(trade: Trade) -> TradeResponse:
    """Convierte un Trade dataclass al schema de respuesta HTTP."""
    return TradeResponse(
        entry_time=trade.entry_time,
        exit_time=trade.exit_time,
        side=trade.side,
        entry_price=trade.entry_price,
        exit_price=trade.exit_price,
        quantity=trade.quantity,
        pnl=trade.pnl,
        return_pct=trade.return_pct,
        candles_held=trade.candles_held,
        exit_reason=trade.exit_reason,
        equity_before=trade.equity_before,
        equity_after=trade.equity_after,
    )

def _config_to_response(config: BacktestConfig) -> BacktestConfigResponse:
    """Convierte un BacktestConfig dataclass al schema de respuesta HTTP."""
    return BacktestConfigResponse(
        initial_capital=config.initial_capital,
        leverage=config.leverage,
        stop_loss_pct=config.stop_loss_pct,
        take_profit_pct=config.take_profit_pct,
        breakeven_trigger_pct=config.breakeven_trigger_pct,
        min_slope_pct=config.min_slope_pct,
        exit_slope_periods=config.exit_slope_periods,
        ema_gap_min_pct=config.ema_gap_min_pct,
        adx_min=config.adx_min,
        adx_require_di=config.adx_require_di,
        adx_require_rising=config.adx_require_rising,
        atr_period=config.atr_period,
        atr_stop_mult=config.atr_stop_mult,
        atr_trailing_mult=config.atr_trailing_mult,
        atr_stop_confirm_on_close=config.atr_stop_confirm_on_close,
    )

def _result_to_response(result: BacktestResult, backtest_id: str) -> BacktestResponse:
    """Convierte un BacktestResult dataclass al schema de respuesta HTTP."""
    return BacktestResponse(
        id=backtest_id,
        symbol=result.symbol,
        interval=result.interval,
        strategy_name=result.strategy_name,
        start_time=result.start_time,
        end_time=result.end_time,
        created_at=result.created_at,
        initial_capital=result.initial_capital,
        final_capital=result.final_capital,
        total_return_pct=result.total_return_pct,
        max_drawdown_pct=result.max_drawdown_pct,
        total_trades=result.total_trades,
        winning_trades=result.winning_trades,
        losing_trades=result.losing_trades,
        win_rate_pct=result.win_rate_pct,
        # profit_factor puede ser inf si no hubo perdidas, se acota para respuesta
        profit_factor=min(result.profit_factor, 999.0),
        avg_trade_return_pct=result.avg_trade_return_pct,
        trades=[_trade_to_response(t) for t in result.trades],
        config=_config_to_response(result.config) if result.config else None,
    )

async def execute_backtest(req: BacktestRequest) -> Optional[BacktestResponse]:
    """
    Orquesta la ejecución completa de un backtest:
      1. Carga candles desde MongoDB
      2. Prepara arrays numpy
      3. Construye BacktestConfig desde el request
      4. Genera señales con build_ema_long_signals
      5. Corre el simulador
      6. Guarda en MongoDB
      7. Devuelve BacktestResponse tipado

    Retorna None si no hay candles para el rango pedido.
    Los porcentajes del request vienen como entero (2 = 2%) y se convierten
    a decimal (0.02) antes de crear BacktestConfig.
    """
    # Cargar candles
    candles = await get_candles(
        symbol=req.symbol,
        interval=req.interval,
        start_time=parse_utc(req.start_time),
        end_time=parse_utc(req.end_time) if req.end_time else None,
    )

    if not candles:
        return None

    # Arrays numpy
    times:  pd.DatetimeIndex = pd.to_datetime([c.close_time for c in candles], utc=True)
    opens:  np.ndarray = np.array([float(c.open_price)  for c in candles], dtype=float)
    highs:  np.ndarray = np.array([float(c.high_price)  for c in candles], dtype=float)
    lows:   np.ndarray = np.array([float(c.low_price)   for c in candles], dtype=float)
    closes: np.ndarray = np.array([float(c.close_price) for c in candles], dtype=float)

    # BacktestConfig y conversion de porcentajes
    config = BacktestConfig(
        initial_capital=req.initial_capital,
        leverage=req.leverage,
        stop_loss_pct=(req.stop_loss_pct / 100)         if req.stop_loss_pct         else None,
        take_profit_pct=(req.take_profit_pct / 100)     if req.take_profit_pct       else None,
        breakeven_trigger_pct=(req.breakeven_trigger_pct / 100) if req.breakeven_trigger_pct else None,
        min_slope_pct=req.min_slope_pct,
        exit_slope_periods=req.exit_slope_periods,
        ema_gap_min_pct=req.ema_gap_min_pct,
        adx_min=req.adx_min,
        adx_require_di=req.adx_require_di,
        adx_require_rising=req.adx_require_rising,
        atr_period=req.atr_period,
        atr_stop_mult=req.atr_stop_mult,
        atr_trailing_mult=req.atr_trailing_mult,
        atr_stop_confirm_on_close=True,
    )

    # Generar senales
    signals = build_ema_long_signals(
        prices=closes,
        highs=highs,
        lows=lows,
        fast_span=10,
        slow_span=55,
        min_slope_pct=req.min_slope_pct,
        exit_slope_periods=req.exit_slope_periods,
        ema_gap_min_pct=req.ema_gap_min_pct,
        adx_min=req.adx_min,
        adx_period=14,  # mismo periodo que ATR por consistencia
        require_di_confirmation=req.adx_require_di,
        require_adx_rising=req.adx_require_rising,
    )

    # Ejecutar simulador
    result: BacktestResult = run_long_backtest(
        times=times,
        opens=opens,
        highs=highs,
        lows=lows,
        closes=closes,
        entry_signals=signals.entry_long,
        exit_signals=signals.exit_long,
        config=config,
        strategy_name=signals.name,
        symbol=req.symbol,
        interval=req.interval,
    )

    # Guardar en MongoDB
    backtest_id: str = await save_backtest_result(result)

    # Convertir a schema de respuesta
    return _result_to_response(result, backtest_id)