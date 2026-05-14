from __future__ import annotations
from typing import Optional
from bson import ObjectId
import numpy as np
import pandas as pd

from backtesting.alerts import build_alerts_feed, build_signals_timeline
from backtesting.records import BacktestConfig, BacktestResult
from backtesting.strategies import build_ema_long_signals
from backtesting.simulator import run_long_backtest
from database.repository import (
    get_candles,
    save_backtest_result,
)
from API.schemas.backtest import BacktestRequest, BacktestResponse
from API.mappers.backtest import result_to_backtest_response, doc_to_backtest_response
from database.database import get_db
from indicators.emas import ema_pct_slope
from utils.utils import parse_utc

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

    series_start_time = candles[0].open_time
    series_end_time = candles[-1].close_time
    expected_candle_count = len(candles)

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

    result.loaded_candles_count = len(candles)

    slope_pct = ema_pct_slope(signals.ema_fast)
    result.alerts_feed = build_alerts_feed(
        times=times,
        closes=closes,
        signals=signals,
        result=result,
        slope_pct=slope_pct,
    )
    result.signals_timeline = build_signals_timeline(
        times=times,
        closes=closes,
        signals=signals,
        slope_pct=slope_pct,
        result=result,
        min_slope_pct=req.min_slope_pct,
        ema_gap_min_pct=req.ema_gap_min_pct,
    )

    # Guardar en MongoDB
    backtest_id: str = await save_backtest_result(result)

    # Convertir a schema de respuesta
    return result_to_backtest_response(result, backtest_id)

async def list_backtests(
    symbol: str,
    interval: str,
    strategy_name: Optional[str] = None,
    limit: int = 20,
) -> list[BacktestResponse]:
    """Lista backtests de MongoDB para un símbolo e intervalo específicos.

    Args:
        symbol: Símbolo requerido (ej: BTCUSDT).
        interval: Intervalo requerido (ej: 4h).
        strategy_name: Filtrar por nombre de estrategia (opcional).
        limit: Máximo de resultados (1-200).

    Returns:
        Lista de BacktestResponse ordenados por fecha descendente.
    """
    db = get_db()
    query: dict = {"symbol": symbol, "interval": interval}

    if strategy_name:
        query["strategy_name"] = strategy_name

    docs: list[dict] = await db.backtests.find(query).sort("created_at", -1).limit(limit).to_list(length=None)
    
    return [doc_to_backtest_response(doc) for doc in docs]

async def get_backtest_by_id(backtest_id: str) -> BacktestResponse:
    """Obtiene un backtest específico por su ID.

    Args:
        backtest_id: ObjectId de MongoDB del backtest.

    Returns:
        BacktestResponse con el backtest solicitado.

    Raises:
        ValueError: Si el ID es inválido o el backtest no existe.
    """
    try:
        oid = ObjectId(backtest_id)
    except Exception as e:
        raise ValueError(f"ID inválido: '{backtest_id}'") from e

    db = get_db()
    doc: Optional[dict] = await db.backtests.find_one({"_id": oid})

    if doc is None:
        raise ValueError(f"Backtest '{backtest_id}' no encontrado")

    return doc_to_backtest_response(doc)