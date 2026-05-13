from __future__ import annotations
from typing import Any, Optional


def build_series_payload(
    analysis_doc: Optional[dict[str, Any]],
    include_adx_points: bool,
) -> Optional[dict[str, Any]]:
    """Construye un payload tipo `series` para exponer dentro del backtest.

    Devuelve None si no se pasó un `analysis_doc`.
    """
    if analysis_doc is None:
        return None

    payload: dict[str, Any] = {
        "symbol": analysis_doc.get("symbol"),
        "interval": analysis_doc.get("interval"),
        "start_time": analysis_doc.get("start_time"),
        "end_time": analysis_doc.get("end_time"),
        "start_price": analysis_doc.get("start_price"),
        "end_price": analysis_doc.get("end_price"),
        "total_candles": analysis_doc.get("total_candles"),
        "created_at": analysis_doc.get("created_at"),
        "candles": analysis_doc.get("candles", []),
        "trends": analysis_doc.get("trends", []),
        "ema_points": analysis_doc.get("ema_points", {}),
        "smi_points": analysis_doc.get("smi_points", []),
        "sr_levels": analysis_doc.get("sr_levels", []),
    }

    if include_adx_points:
        payload["adx_points"] = analysis_doc.get("adx_points", [])

    return payload
