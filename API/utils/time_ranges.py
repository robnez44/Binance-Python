from __future__ import annotations

import re
from datetime import timedelta


def shift_back_one_interval(timestamp, interval: str):
    """Resta un intervalo temporal simple (4h, 1d, 1w, etc.)."""
    match = re.fullmatch(r"(\d+)([smhdwM])", str(interval).strip())
    if not match:
        return timestamp

    value = int(match.group(1))
    unit = match.group(2)

    if unit == "s":
        return timestamp - timedelta(seconds=value)
    if unit == "m":
        return timestamp - timedelta(minutes=value)
    if unit == "h":
        return timestamp - timedelta(hours=value)
    if unit == "d":
        return timestamp - timedelta(days=value)
    if unit == "w":
        return timestamp - timedelta(weeks=value)

    if unit == "M":
        try:
            from dateutil.relativedelta import relativedelta

            return timestamp - relativedelta(months=value)
        except Exception:
            return timestamp

    return timestamp
