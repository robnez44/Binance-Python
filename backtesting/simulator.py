"""
Motor de backtesting.

Funciones:
- run_long_backtest: ejecuta un backtest long simple con una posición a la vez
- _close_long_trade: cierra una posición y crea un Trade
"""
from datetime import datetime
from typing import List, Optional
import numpy as np
import pandas as pd
from backtesting.metrics import summarize_backtest
from backtesting.records import BacktestConfig, BacktestResult, Trade

def _close_long_trade(
    position: dict,
    exit_index: int,
    exit_price: float,
    exit_time: datetime,
    exit_reason: str,
) -> Trade:

    pnl = position["quantity"] * (exit_price - position["entry_price"])
    equity_after = position["equity_before"] + pnl
    return_pct = (
        (pnl / position["equity_before"]) * 100
        if position["equity_before"] else 0.0
    )

    return Trade(
        entry_time=position["entry_time"],
        exit_time=exit_time,
        side="long",
        entry_index=position["entry_index"],
        exit_index=exit_index,
        entry_price=position["entry_price"],
        exit_price=exit_price,
        quantity=position["quantity"],
        pnl=pnl,
        return_pct=return_pct,
        candles_held=exit_index - position["entry_index"],
        exit_reason=exit_reason,
        equity_before=position["equity_before"],
        equity_after=equity_after,
    )

def run_long_backtest(
    times: pd.DatetimeIndex,
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    entry_signals: np.ndarray,
    exit_signals: np.ndarray,
    config: BacktestConfig,
    strategy_name: str = "long_strategy",
    symbol: str = "",
    interval: str = "",
) -> BacktestResult:
    """
    Backtest long sencillo: una posición a la vez, ejecución al open siguiente.

    Flujo por vela:
      1. Si hay posición abierta: revisar stop loss → take profit → señal de salida
      2. Si no hay posición: revisar señal de entrada

    Reglas de ejecución:
      - Entrada: al OPEN de la vela i+1 después de la señal (sin look-ahead bias)
      - Stop loss y take profit: se evalúan contra high/low de la vela actual
      - Si stop y TP se tocan en la misma vela: gana el stop (conservador)
      - Breakeven: OPCIONAL, controlado por config.breakeven_trigger_pct
          · None  → desactivado (recomendado para temporalidades altas como 4h/1d)
          · float → se activa cuando high >= entry_price * (1 + trigger), solo
                    a partir de la vela SIGUIENTE a la de entrada
          · Cuando se activa, mueve el stop al precio de entrada (riesgo cero)
      - Apalancamiento: multiplica el tamaño nocional de la posición
    """
    n = len(closes)
    if not all(len(arr) == n for arr in [opens, highs, lows, entry_signals, exit_signals]):
        raise ValueError("Todos los arrays deben tener la misma longitud")

    trades: List[Trade] = []
    equity = config.initial_capital
    position: Optional[dict] = None

    breakeven_trigger = config.breakeven_trigger_pct  # None = desactivado

    for i in range(1, n):

        # ── Gestión de posición abierta ──────────────────────────────────
        if position is not None and i >= position["entry_index"]:

            # Breakeven — solo si está configurado y solo desde la vela siguiente
            if (
                breakeven_trigger is not None
                and i > position["entry_index"]
                and not position.get("breakeven_active", False)
                and highs[i] >= position["entry_price"] * (1 + breakeven_trigger)
            ):
                position["stop_price"] = position["entry_price"]
                position["breakeven_active"] = True

            stop_price        = position.get("stop_price")
            take_profit_price = position.get("take_profit_price")

            stop_hit = stop_price is not None and lows[i] <= stop_price
            tp_hit   = take_profit_price is not None and highs[i] >= take_profit_price

            # Stop y TP en la misma vela → stop gana (conservador)
            if stop_hit and tp_hit:
                trade = _close_long_trade(
                    position=position,
                    exit_index=i,
                    exit_price=stop_price,
                    exit_time=times[i].to_pydatetime(),
                    exit_reason="stop_loss_priority_same_bar",
                )
                trades.append(trade)
                equity   = trade.equity_after
                position = None
                continue

            # Stop Loss
            if stop_hit:
                stop_reason = (
                    "breakeven_stop"
                    if position.get("breakeven_active") and stop_price == position["entry_price"]
                    else "stop_loss"
                )
                trade = _close_long_trade(
                    position=position,
                    exit_index=i,
                    exit_price=stop_price,
                    exit_time=times[i].to_pydatetime(),
                    exit_reason=stop_reason,
                )
                trades.append(trade)
                equity   = trade.equity_after
                position = None
                continue

            # Take Profit
            if tp_hit:
                trade = _close_long_trade(
                    position=position,
                    exit_index=i,
                    exit_price=take_profit_price,
                    exit_time=times[i].to_pydatetime(),
                    exit_reason="take_profit",
                )
                trades.append(trade)
                equity   = trade.equity_after
                position = None
                continue

            # Señal de salida → ejecuta al open de la vela siguiente
            if i < n - 1 and exit_signals[i]:
                trade = _close_long_trade(
                    position=position,
                    exit_index=i + 1,
                    exit_price=opens[i + 1],
                    exit_time=times[i + 1].to_pydatetime(),
                    exit_reason="signal_exit",
                )
                trades.append(trade)
                equity   = trade.equity_after
                position = None
                continue

        # ── Apertura de nueva posición ───────────────────────────────────
        if position is None and i < n - 1 and entry_signals[i]:
            entry_index    = i + 1
            entry_price    = opens[entry_index]
            position_notional = equity * config.leverage
            quantity       = position_notional / entry_price if entry_price > 0 else 0.0

            position = {
                "entry_index":    entry_index,
                "entry_time":     times[entry_index].to_pydatetime(),
                "entry_price":    entry_price,
                "equity_before":  equity,
                "quantity":       quantity,
                "breakeven_active": False,
                "stop_price": (
                    entry_price * (1 - config.stop_loss_pct)
                    if config.stop_loss_pct is not None else None
                ),
                "take_profit_price": (
                    entry_price * (1 + config.take_profit_pct)
                    if config.take_profit_pct is not None else None
                ),
            }

    # ── Cierre forzado al final de los datos ─────────────────────────────
    if position is not None:
        trade = _close_long_trade(
            position=position,
            exit_index=n - 1,
            exit_price=closes[-1],
            exit_time=times[-1].to_pydatetime(),
            exit_reason="end_of_data",
        )
        trades.append(trade)

    start_time: Optional[datetime] = times[0].to_pydatetime() if len(times) > 0 else None
    end_time:   Optional[datetime] = times[-1].to_pydatetime() if len(times) > 0 else None

    return summarize_backtest(
        trades=trades,
        initial_capital=config.initial_capital,
        strategy_name=strategy_name,
        symbol=symbol,
        interval=interval,
        start_time=start_time,
        end_time=end_time,
        config=config,
    )