from __future__ import annotations
import numpy as np
import pandas as pd

from backtesting.records import (
    BacktestAlertEvent,
    BacktestResult,
    SignalTimelineRow,
    StrategySignals,
)
from backtesting.reporting_utils import exit_reason_label

def build_alerts_feed(
    times: pd.DatetimeIndex,
    closes: np.ndarray,
    signals: StrategySignals,
    result: BacktestResult,
) -> list[BacktestAlertEvent]:
    """Construye alertas estilo bot con eventos relevantes y ejecuciones reales."""
    n = len(closes)
    events: list[BacktestAlertEvent] = []

    for trade_number, trade in enumerate(result.trades, 1):
        entry_signal_index = trade.entry_index - 1
        if (
            0 <= entry_signal_index < n
            and bool(signals.entry_long[entry_signal_index])
        ):
            events.append(
                BacktestAlertEvent(
                    index=int(entry_signal_index),
                    timestamp=times[entry_signal_index].to_pydatetime(),
                    event_type="entry_signal",
                    action="BUY_NEXT_OPEN",
                    message="Senal de entrada detectada.",
                    price=float(closes[entry_signal_index]),
                    trade_number=trade_number,
                    exit_reason=None,
                )
            )

        if 0 <= trade.entry_index < n:
            events.append(
                BacktestAlertEvent(
                    index=int(trade.entry_index),
                    timestamp=times[trade.entry_index].to_pydatetime(),
                    event_type="entry_exec",
                    action="BUY_EXECUTED",
                    message="Entrada ejecutada.",
                    price=float(trade.entry_price),
                    trade_number=trade_number,
                    exit_reason=None,
                )
            )

        if trade.exit_reason == "signal_exit":
            exit_signal_index = trade.exit_index - 1
            if (
                0 <= exit_signal_index < n
                and bool(signals.exit_long[exit_signal_index])
            ):
                events.append(
                    BacktestAlertEvent(
                        index=int(exit_signal_index),
                        timestamp=times[exit_signal_index].to_pydatetime(),
                        event_type="exit_signal",
                        action="SELL_NEXT_OPEN",
                        message="Senal de salida detectada.",
                        price=float(closes[exit_signal_index]),
                        trade_number=trade_number,
                        exit_reason="signal_exit",
                    )
                )

        if 0 <= trade.exit_index < n:
            events.append(
                BacktestAlertEvent(
                    index=int(trade.exit_index),
                    timestamp=times[trade.exit_index].to_pydatetime(),
                    event_type="exit_exec",
                    action="SELL_EXECUTED",
                    message=f"Salida ejecutada ({exit_reason_label(trade.exit_reason, style='plain')}).",
                    price=float(trade.exit_price),
                    trade_number=trade_number,
                    exit_reason=trade.exit_reason,
                )
            )

    priority = {
        "entry_signal": 0,
        "exit_signal": 1,
        "entry_exec": 2,
        "exit_exec": 3,
    }
    events.sort(
        key=lambda e: (
            e.index,
            priority.get(e.event_type, 99),
            e.trade_number or 0,
        )
    )
    return events

def build_signals_timeline(
    times: pd.DatetimeIndex,
    closes: np.ndarray,
    signals: StrategySignals,
    slope_pct: np.ndarray,
    result: BacktestResult,
    min_slope_pct: float,
    ema_gap_min_pct: float,
) -> list[SignalTimelineRow]:
    """Construye filas de velas relevantes para `signals_timeline` (tabla de debug)."""
    n = len(closes)
    entry_signal_indices: set[int] = set()
    exit_signal_indices: set[int] = set()
    entry_exec_map: dict[int, int] = {}
    exit_exec_map: dict[int, tuple[int, str]] = {}

    for trade_number, trade in enumerate(result.trades, 1):
        entry_signal_index = trade.entry_index - 1
        if (
            0 <= entry_signal_index < n
            and bool(signals.entry_long[entry_signal_index])
        ):
            entry_signal_indices.add(entry_signal_index)

        if 0 <= trade.entry_index < n:
            entry_exec_map[trade.entry_index] = trade_number

        if trade.exit_reason == "signal_exit":
            exit_signal_index = trade.exit_index - 1
            if (
                0 <= exit_signal_index < n
                and bool(signals.exit_long[exit_signal_index])
            ):
                exit_signal_indices.add(exit_signal_index)

        if 0 <= trade.exit_index < n:
            exit_exec_map[trade.exit_index] = (trade_number, trade.exit_reason)

    relevant: set[int] = set()
    base_idxs = (
        list(entry_signal_indices)
        + list(exit_signal_indices)
        + list(entry_exec_map.keys())
        + list(exit_exec_map.keys())
    )
    for idx in base_idxs:
        relevant.update([max(0, idx - 1), idx, min(n - 1, idx + 1)])

    if not relevant:
        return []

    has_adx = signals.adx_values is not None
    rows: list[SignalTimelineRow] = []

    for i in sorted(relevant):
        ema10 = float(signals.ema_fast[i])
        ema55 = float(signals.ema_slow[i])
        gap_pct = ((ema10 - ema55) / ema55 * 100) if ema55 else 0.0
        slope = float(slope_pct[i])
        close = float(closes[i])

        cond_ema10_gt_ema55 = ema10 > ema55
        cond_gap_ge_min = gap_pct >= ema_gap_min_pct
        cond_slope_ge_min = slope >= min_slope_pct
        cond_price_gt_ema10 = close > ema10

        events: list[str] = []
        if i in entry_signal_indices:
            events.append("entry_signal")
        if i in exit_signal_indices:
            events.append("exit_signal")
        if i in entry_exec_map:
            events.append(f"entry_exec_t{entry_exec_map[i]}")
        if i in exit_exec_map:
            trade_no, reason = exit_exec_map[i]
            events.append(f"exit_exec_t{trade_no}_{reason}")

        rows.append(
            SignalTimelineRow(
                index=i,
                timestamp=times[i].to_pydatetime(),
                close_price=close,
                ema10=ema10,
                ema55=ema55,
                gap_pct=float(gap_pct),
                slope_pct=slope,
                cond_ema10_gt_ema55=bool(cond_ema10_gt_ema55),
                cond_gap_ge_min=bool(cond_gap_ge_min),
                cond_slope_ge_min=bool(cond_slope_ge_min),
                cond_price_gt_ema10=bool(cond_price_gt_ema10),
                adx=float(signals.adx_values[i]) if has_adx else None,
                plus_di=float(signals.plus_di[i]) if has_adx else None,
                minus_di=float(signals.minus_di[i]) if has_adx else None,
                event=" | ".join(events) if events else None,
            )
        )

    return rows
