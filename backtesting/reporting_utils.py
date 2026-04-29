from __future__ import annotations

from typing import Literal

ExitReasonLabelStyle = Literal["plain", "icon"]

_PLAIN_LABELS: dict[str, str] = {
    "take_profit": "take profit",
    "stop_loss": "stop loss",
    "atr_stop_loss": "atr stop",
    "atr_trailing_stop": "trailing sl by atr",
    "breakeven_stop": "breakeven",
    "stop_loss_priority_same_bar": "stop loss (same bar)",
    "signal_exit": "signal exit",
    "end_of_data": "end of data",
}

_ICON_LABELS: dict[str, str] = {
    "take_profit": "✔  take_profit",
    "stop_loss": "✘  stop_loss",
    "atr_stop_loss": "✘  atr_stop",
    "atr_trailing_stop": "✘  Trailing SL by ATR",
    "breakeven_stop": "◈  breakeven",
    "stop_loss_priority_same_bar": "✘  sl_same_bar",
    "signal_exit": "↩  signal_exit",
    "end_of_data": "⏹  end_of_data",
}

def exit_reason_label(reason: str, style: ExitReasonLabelStyle = "plain") -> str:
    """Mapea códigos internos de salida a un label legible.

    - style="plain": pensado para mensajes de `alerts_feed`.
    - style="icon": pensado para prints de reporting (terminal).
    """
    if style == "icon":
        return _ICON_LABELS.get(reason, reason)
    return _PLAIN_LABELS.get(reason, reason)
