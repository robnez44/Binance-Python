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
from indicators.atr import compute_atr

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

def _resolve_initial_stop_price(
    entry_price: float,
    stop_loss_pct: Optional[float],
    atr_value: Optional[float],
    atr_stop_mult: Optional[float],
) -> tuple[Optional[float], str]:
    pct_stop = (
        entry_price * (1 - stop_loss_pct)
        if stop_loss_pct is not None else None
    )

    atr_stop = None
    if atr_stop_mult is not None and atr_stop_mult > 0 and atr_value is not None and atr_value > 0:
        atr_stop = entry_price - atr_value * atr_stop_mult

    if pct_stop is None and atr_stop is None:
        return None, "none"
    if pct_stop is None:
        return atr_stop, "atr"
    if atr_stop is None:
        return pct_stop, "pct"

    stop_price = max(pct_stop, atr_stop)
    stop_origin = "atr" if atr_stop >= pct_stop else "pct"
    return stop_price, stop_origin

def _apply_atr_trailing_stop(
    position: dict,
    close_price: float,
    atr_value: Optional[float],
    atr_trailing_mult: Optional[float],
) -> None:
    if atr_trailing_mult is None or atr_trailing_mult <= 0:
        return
    if atr_value is None or atr_value <= 0:
        return

    peak_close = max(position.get("peak_close", close_price), close_price)
    candidate_stop = peak_close - atr_value * atr_trailing_mult
    current_stop = position.get("stop_price")

    if current_stop is None or candidate_stop > current_stop:
        position["stop_price"] = candidate_stop
        position["stop_origin"] = "atr_trailing"

    position["peak_close"] = peak_close

def _is_stop_hit(
    low_price: float,
    close_price: float,
    stop_price: Optional[float],
    stop_origin: str,
    atr_stop_confirm_on_close: bool,
) -> bool:
    if stop_price is None:
        return False

    if atr_stop_confirm_on_close and stop_origin in ("atr", "atr_trailing"):
        return close_price <= stop_price

    return low_price <= stop_price

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
    use_atr_stop = config.atr_stop_mult is not None and config.atr_stop_mult > 0
    use_atr_trailing = config.atr_trailing_mult is not None and config.atr_trailing_mult > 0

    atr_values: Optional[np.ndarray] = None
    if use_atr_stop or use_atr_trailing:
        high_s = pd.Series(highs)
        low_s = pd.Series(lows)
        close_s = pd.Series(closes)
        atr_series = compute_atr(high_s, low_s, close_s, n=config.atr_period)
        atr_values = atr_series.bfill().ffill().to_numpy()

    for i in range(1, n):

        # ── Gestión de posición abierta ──────────────────────────────────
        if position is not None and i >= position["entry_index"]:

            if use_atr_trailing and atr_values is not None and i > position["entry_index"]:
                _apply_atr_trailing_stop(
                    position=position,
                    close_price=closes[i],
                    atr_value=float(atr_values[i]),
                    atr_trailing_mult=config.atr_trailing_mult,
                )

            # Breakeven — solo si está configurado y solo desde la vela siguiente
            if (
                breakeven_trigger is not None
                and i > position["entry_index"]
                and not position.get("breakeven_active", False)
                and highs[i] >= position["entry_price"] * (1 + breakeven_trigger)
            ):
                position["stop_price"] = position["entry_price"]
                position["breakeven_active"] = True
                position["stop_origin"] = "breakeven"

            stop_price        = position.get("stop_price")
            take_profit_price = position.get("take_profit_price")
            stop_origin       = position.get("stop_origin", "pct")

            stop_hit = _is_stop_hit(
                low_price=float(lows[i]),
                close_price=float(closes[i]),
                stop_price=stop_price,
                stop_origin=stop_origin,
                atr_stop_confirm_on_close=config.atr_stop_confirm_on_close,
            )
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
                if position.get("breakeven_active") and stop_price == position["entry_price"]:
                    stop_reason = "breakeven_stop"
                else:
                    if stop_origin == "atr_trailing":
                        stop_reason = "atr_trailing_stop"
                    elif stop_origin == "atr":
                        stop_reason = "atr_stop_loss"
                    else:
                        stop_reason = "stop_loss"
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

            atr_at_entry = None
            if atr_values is not None:
                atr_at_entry = float(atr_values[entry_index])

            stop_price, stop_origin = _resolve_initial_stop_price(
                entry_price=entry_price,
                stop_loss_pct=config.stop_loss_pct,
                atr_value=atr_at_entry,
                atr_stop_mult=config.atr_stop_mult,
            )

            position = {
                "entry_index":    entry_index,
                "entry_time":     times[entry_index].to_pydatetime(),
                "entry_price":    entry_price,
                "equity_before":  equity,
                "quantity":       quantity,
                "peak_close":     entry_price,
                "breakeven_active": False,
                "stop_price": stop_price,
                "stop_origin": stop_origin,
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