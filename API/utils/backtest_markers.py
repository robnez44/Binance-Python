from __future__ import annotations
from typing import List

from backtesting.records import BacktestResult

def build_trade_markers(result: BacktestResult, candles: List) -> List[dict]:
    """Construye marcadores para consumo UI (mismo formato que antes).

    Ancla `bar_time` a `candle.open_time` para evitar desfases con la UI.
    """
    from backtesting.reporting_utils import exit_reason_label

    candle_open_times = [c.open_time for c in candles]
    markers: list[dict] = []

    for trade_number, trade in enumerate(result.trades, 1):
        if 0 <= trade.entry_index < len(candle_open_times):
            markers.append(
                {
                    "trade_number": trade_number,
                    "marker_type": "entry_exec",
                    "side": trade.side,
                    "bar_index": int(trade.entry_index),
                    "bar_time": candle_open_times[trade.entry_index],
                    "execution_time": trade.entry_time,
                    "price": float(trade.entry_price),
                }
            )

        if 0 <= trade.exit_index < len(candle_open_times):
            markers.append(
                {
                    "trade_number": trade_number,
                    "marker_type": "exit_exec",
                    "side": trade.side,
                    "bar_index": int(trade.exit_index),
                    "bar_time": candle_open_times[trade.exit_index],
                    "execution_time": trade.exit_time,
                    "price": float(trade.exit_price),
                    "pnl": float(trade.pnl),
                    "is_win": bool(trade.pnl > 0),
                    "exit_reason": trade.exit_reason,
                    "exit_reason_label": exit_reason_label(trade.exit_reason, style="plain"),
                }
            )

    markers.sort(
        key=lambda marker: (
            marker["bar_index"],
            0 if marker["marker_type"] == "entry_exec" else 1,
            marker["trade_number"],
        )
    )
    return markers