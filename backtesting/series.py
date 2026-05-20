from __future__ import annotations
from dataclasses import asdict, is_dataclass
from datetime import datetime
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


def _item_timestamp(item: Any) -> datetime | None:
    if isinstance(item, dict):
        for key in ("timestamp", "open_time", "close_time"):
            value = item.get(key)
            if isinstance(value, datetime):
                return value

    return None


def _last_timestamp(items: Iterable[Any]) -> datetime | None:
    last_value: datetime | None = None
    for item in items:
        timestamp = _item_timestamp(item)
        if timestamp is not None:
          last_value = timestamp
    return last_value


def _filter_by_timestamp(items: Iterable[Any], cutoff: datetime | None, keys: tuple[str, ...]) -> list[Any]:
    normalized = [_normalize_item(item) for item in items]
    if cutoff is None:
        return normalized

    filtered: list[Any] = []
    for item in normalized:
        if not isinstance(item, dict):
            filtered.append(item)
            continue

        value: datetime | None = None
        for key in keys:
            candidate = item.get(key)
            if isinstance(candidate, datetime):
                value = candidate
                break

        if value is None or value <= cutoff:
            filtered.append(item)

    return filtered

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

    candle_cutoff = _last_timestamp(candle_list)

    ema_normalized = _normalize_mapping(ema_points)
    ema_cutoffs = [
        _last_timestamp(points)
        for points in ema_normalized.values()
        if points
    ]
    adx_normalized = [_normalize_item(item) for item in adx_points] if adx_points else []
    adx_cutoff = _last_timestamp(adx_normalized) if adx_normalized else None

    cutoff_candidates = [candle_cutoff, *ema_cutoffs, adx_cutoff]
    cutoff = min((value for value in cutoff_candidates if value is not None), default=None)

    candle_list = _filter_by_timestamp(candle_list, cutoff, ("open_time",))
    if not candle_list:
        return None

    ema_normalized = {
        key: _filter_by_timestamp(items, cutoff, ("timestamp",))
        for key, items in ema_normalized.items()
    }

    if adx_normalized:
        adx_normalized = _filter_by_timestamp(adx_normalized, cutoff, ("timestamp",))

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
        "ema_points": ema_normalized,
        "smi_points": [_normalize_item(item) for item in smi_points],
        "sr_levels": [_normalize_item(item) for item in sr_levels],
    }

    # Para indicadores opcionales, incluir solo si hay datos.
    if not payload.get("smi_points"):
        payload.pop("smi_points", None)

    if not payload.get("sr_levels"):
        payload.pop("sr_levels", None)

    if adx_normalized:
        payload["adx_points"] = adx_normalized

    normalized_trends = [_normalize_item(item) for item in trends]
    if normalized_trends:
        payload["trends"] = normalized_trends

    return payload
