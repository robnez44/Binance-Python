from __future__ import annotations

from typing import Literal

ExitReasonLabelStyle = Literal["plain", "icon"]

_PLAIN_LABELS: dict[str, str] = {
    "take_profit": "Take Profit Target Hit",
    "stop_loss": "Stop Loss Triggered",
    "atr_stop_loss": "Dynamic ATR Stop Loss Hit",
    "atr_trailing_stop": "Trailing Stop Loss (ATR) Hit",
    "breakeven_stop": "Price Returned to Breakeven",
    "stop_loss_priority_same_bar": "Stop Loss Hit (Same Bar)",
    "signal_exit": "Strategy Signal Exit",
    "end_of_data": "Position Closed at Data End",
}

_ICON_LABELS: dict[str, str] = {
    "take_profit": "✔  Take Profit Target Hit",
    "stop_loss": "✘  Stop Loss Triggered",
    "atr_stop_loss": "✘  Dynamic ATR Stop Loss",
    "atr_trailing_stop": "✘  Trailing Stop Loss (ATR)",
    "breakeven_stop": "◈  Breakeven Stop",
    "stop_loss_priority_same_bar": "✘  Stop Loss (Same Bar)",
    "signal_exit": "↩  Strategy Signal Exit",
    "end_of_data": "⏹  Data End Closure",
}

def exit_reason_label(reason: str, style: ExitReasonLabelStyle = "plain") -> str:
    """Mapea códigos internos de salida a un label legible.

    - style="plain": pensado para mensajes de `alerts_feed`.
    - style="icon": pensado para prints de reporting (terminal).
    """
    if style == "icon":
        return _ICON_LABELS.get(reason, reason)
    return _PLAIN_LABELS.get(reason, reason)
