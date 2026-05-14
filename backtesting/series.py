from __future__ import annotations
from dataclasses import asdict, is_dataclass
from typing import Any, Iterable, Mapping, Optional

def _normalize_item(item: Any) -> Any:
    if is_dataclass(item):
        return asdict(item)
    if isinstance(item, dict):
        return {k: v for k, v in item.items() if k != "_id"}
    return item

def _normalize_mapping(items_by_key: Mapping[str, Iterable[Any]]) -> dict[str, list[Any]]:
    return {
        key: [_normalize_item(item) for item in items]
        for key, items in items_by_key.items()
    }

def build_series_payload(
    candles: Iterable[Any],
    trends: Iterable[Any],
    ema_points: Mapping[str, Iterable[Any]],
    smi_points: Iterable[Any],
    sr_levels: Iterable[Any],
    adx_points: Optional[Iterable[Any]] = None,
) -> Optional[dict[str, Any]]:
    """Construye un payload tipo `series` para exponer dentro del backtest.

    El payload se arma únicamente con el rango exacto de candles del backtest
    y con snapshots ya guardados para ese mismo intervalo.
    """
    candle_list = [_normalize_item(item) for item in candles]
    if not candle_list:
        return None

    start_candle = candle_list[0]
    end_candle = candle_list[-1]

    payload: dict[str, Any] = {
        "symbol": start_candle.get("symbol"),
        "interval": start_candle.get("interval"),
        "start_time": start_candle.get("open_time"),
        "end_time": end_candle.get("close_time"),
        "start_price": start_candle.get("open_price"),
        "end_price": end_candle.get("close_price"),
        "total_candles": len(candle_list),
        "candles": candle_list,
        "ema_points": _normalize_mapping(ema_points),
        "smi_points": [_normalize_item(item) for item in smi_points],
        "sr_levels": [_normalize_item(item) for item in sr_levels],
    }

    # Para indicadores opcionales, incluir solo si hay datos.
    if not payload.get("smi_points"):
        payload.pop("smi_points", None)

    if not payload.get("sr_levels"):
        payload.pop("sr_levels", None)

    if adx_points:
        adx_norm = [_normalize_item(item) for item in adx_points]
        if adx_norm:
            payload["adx_points"] = adx_norm

    normalized_trends = [_normalize_item(item) for item in trends]
    if normalized_trends:
        payload["trends"] = normalized_trends

    return payload
