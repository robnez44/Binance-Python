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


def _format_timeline_event(event_code: str) -> str:
    """Convierte códigos de eventos técnicos a labels legibles para la timeline."""
    if event_code.startswith("entry_signal"):
        return "🟢 Entry Signal"
    elif event_code.startswith("exit_signal"):
        return "🔴 Exit Signal"
    elif event_code.startswith("entry_exec_t"):
        # Extrae número de trade: "entry_exec_t1" → "Trade #1 Entry Executed"
        trade_no = event_code.replace("entry_exec_t", "")
        return f"🟢 Trade #{trade_no} Entry Executed"
    elif event_code.startswith("exit_exec_t"):
        # Extrae número y motivo: "exit_exec_t1_signal_exit" → "Trade #1 Exit (Signal Exit)"
        parts = event_code.replace("exit_exec_t", "").split("_", 1)
        trade_no = parts[0]
        reason = parts[1] if len(parts) > 1 else "unknown"
        reason_label = exit_reason_label(reason, style="plain")
        return f"🔴 Trade #{trade_no} Exit ({reason_label})"
    return event_code

def _format_alert_message(
    event_type: str,
    trade_number: int,
    price: float,
    ema10: float | None = None,
    ema55: float | None = None,
    slope: float | None = None,
    adx: float | None = None,
    plus_di: float | None = None,
    minus_di: float | None = None,
    base_signal: bool | None = None,
    filter_total: int | None = None,
    filter_pass: int | None = None,
    active_filters: list[str] | None = None,
    exit_reason: str | None = None,
    pnl: float | None = None,
) -> str:
    """Genera un mensaje descriptivo y natural para la alerta."""
    if event_type == "entry_signal":
        parts: list[str] = []
        # EMA gap
        if ema10 is not None and ema55 is not None:
            gap = ((ema10 - ema55) / ema55 * 100) if ema55 else 0
            parts.append(f"EMA10>EMA55 (gap {gap:+.2f}%)")

        # Base signal (pre-filtros)
        if base_signal is not None:
            parts.append("Base: EMA cross" if base_signal else "Base: no")

        # Momentum / slope
        if slope is not None:
            parts.append(f"Momentum: {slope:+.4f}%")

        # ADX info
        if adx is not None:
            di_desc = ""
            if plus_di is not None and minus_di is not None:
                di_desc = ", +DI>-DI" if plus_di > minus_di else ", +DI<=-DI"
            parts.append(f"ADX {adx:.1f}{di_desc}")

        # Precio relativo
        if ema10 is not None:
            parts.append("Precio > EMA10" if price > ema10 else "Precio <= EMA10")

        # Filtros
        if filter_total is not None and filter_pass is not None:
            parts.append(f"Filtros: {filter_pass}/{filter_total} pasaron")
        elif active_filters:
            parts.append(f"Filtros: {', '.join(active_filters[:3])}")

        details = " • ".join(parts) if parts else "detalle no disponible"
        return f"📈 Oportunidad detectada — {details}."
    
    elif event_type == "entry_exec":
        return f"🟢 Entrada ejecutada — Compra en ${price:,.2f} — Iniciando posición #{trade_number}"
    
    elif event_type == "exit_signal":
        return f"📉 Señal de cierre: EMA10 comenzó a bajar sostenidamente."
    
    elif event_type == "exit_exec":
        reason_desc = exit_reason_label(exit_reason or "unknown", style="plain")
        pnl_emoji = "✅" if pnl and pnl >= 0 else "❌"
        pnl_str = f"${pnl:,.2f}" if pnl is not None else "?"
        return f"🔴 Posición cerrada — Salida en ${price:,.2f} ({reason_desc}) • PnL: {pnl_emoji} {pnl_str}"
    
    return ""


def build_alerts_feed(
    times: pd.DatetimeIndex,
    closes: np.ndarray,
    signals: StrategySignals,
    result: BacktestResult,
    slope_pct: np.ndarray | None = None,
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
            ema10_signal = float(signals.ema_fast[entry_signal_index])
            ema55_signal = float(signals.ema_slow[entry_signal_index])
            adx_val = (
                float(signals.adx_values[entry_signal_index])
                if signals.adx_values is not None
                else None
            )
            plus_di_val = (
                float(signals.plus_di[entry_signal_index])
                if signals.plus_di is not None
                else None
            )
            minus_di_val = (
                float(signals.minus_di[entry_signal_index])
                if signals.minus_di is not None
                else None
            )
            base_sig = (
                bool(signals.entry_base_long[entry_signal_index])
                if signals.entry_base_long is not None
                else None
            )
            filt_total = (
                int(signals.filter_total_count[entry_signal_index])
                if signals.filter_total_count is not None
                else None
            )
            filt_pass = (
                int(signals.filter_pass_count[entry_signal_index])
                if signals.filter_pass_count is not None
                else None
            )
            slope_val = (
                float(slope_pct[entry_signal_index]) if slope_pct is not None else None
            )
            events.append(
                BacktestAlertEvent(
                    index=int(entry_signal_index),
                    timestamp=times[entry_signal_index].to_pydatetime(),
                    event_type="entry_signal",
                    action="BUY_NEXT_OPEN",
                    message=_format_alert_message(
                        "entry_signal",
                        trade_number,
                        float(closes[entry_signal_index]),
                        ema10=ema10_signal,
                        ema55=ema55_signal,
                        slope=slope_val,
                        adx=adx_val,
                        plus_di=plus_di_val,
                        minus_di=minus_di_val,
                        base_signal=base_sig,
                        filter_total=filt_total,
                        filter_pass=filt_pass,
                        active_filters=signals.active_filters,
                    ),
                    price=float(closes[entry_signal_index]),
                    trade_number=trade_number,
                    exit_reason=None,
                    exit_reason_label=None,
                )
            )

        if 0 <= trade.entry_index < n:
            events.append(
                BacktestAlertEvent(
                    index=int(trade.entry_index),
                    timestamp=times[trade.entry_index].to_pydatetime(),
                    event_type="entry_exec",
                    action="BUY_EXECUTED",
                    message=_format_alert_message(
                        "entry_exec",
                        trade_number,
                        float(trade.entry_price),
                    ),
                    price=float(trade.entry_price),
                    trade_number=trade_number,
                    exit_reason=None,
                    exit_reason_label=None,
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
                        message=_format_alert_message(
                            "exit_signal",
                            trade_number,
                            float(closes[exit_signal_index]),
                        ),
                        price=float(closes[exit_signal_index]),
                        trade_number=trade_number,
                        exit_reason="signal_exit",
                        exit_reason_label=exit_reason_label("signal_exit", style="plain"),
                    )
                )

        if 0 <= trade.exit_index < n:
            events.append(
                BacktestAlertEvent(
                    index=int(trade.exit_index),
                    timestamp=times[trade.exit_index].to_pydatetime(),
                    event_type="exit_exec",
                    action="SELL_EXECUTED",
                    message=_format_alert_message(
                        "exit_exec",
                        trade_number,
                        float(trade.exit_price),
                        exit_reason=trade.exit_reason,
                        pnl=float(trade.pnl),
                    ),
                    price=float(trade.exit_price),
                    trade_number=trade_number,
                    exit_reason=trade.exit_reason,
                    exit_reason_label=exit_reason_label(trade.exit_reason, style="plain"),
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
        event_codes: list[str] = []
        if i in entry_signal_indices:
            events.append("Entry Signal")
            event_codes.append("entry_signal")
        if i in exit_signal_indices:
            events.append("Exit Signal")
            event_codes.append("exit_signal")
        if i in entry_exec_map:
            trade_no = entry_exec_map[i]
            events.append(f"Trade #{trade_no} Entry Executed")
            event_codes.append(f"entry_exec_t{trade_no}")
        if i in exit_exec_map:
            trade_no, reason = exit_exec_map[i]
            reason_label = exit_reason_label(reason, style="plain")
            events.append(f"Trade #{trade_no} Exit ({reason_label})")
            event_codes.append(f"exit_exec_t{trade_no}_{reason}")

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
