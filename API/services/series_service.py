"""Service layer for series data retrieval and construction."""
from bson import ObjectId
from API.schemas.series import SeriesDataResponse
from backtesting.series import build_series_payload
from database.database import get_db
from database.repository import (
    get_adx_snapshots_for_range,
    get_candles,
    get_ema_snapshots_for_range,
    get_sr_levels_for_range,
    get_smi_snapshots_for_range,
    get_trends_for_range,
)

async def get_series_for_backtest(backtest_id: str) -> SeriesDataResponse:
    """Obtiene y construye la serie (OHLC + indicadores) para un backtest dado.

    Args:
        backtest_id: ObjectId de MongoDB del backtest.

    Returns:
        SeriesDataResponse con candles e indicadores alineados.

    Raises:
        ValueError: Si el backtest está incompleto o no hay candles.
    """
    try:
        oid = ObjectId(backtest_id)
    except Exception as e:
        raise ValueError(f"ID de backtest inválido: {backtest_id}") from e

    db = get_db()
    doc = await db.backtests.find_one({"_id": oid})
    if doc is None:
        raise ValueError(f"Backtest {backtest_id} no encontrado")

    symbol = doc.get("symbol")
    interval = doc.get("interval")
    start_time = doc.get("start_time")
    end_time = doc.get("end_time")

    if not (symbol and interval and start_time):
        raise ValueError("Faltan campos requeridos en backtest: symbol, interval, start_time")

    # Cargar candles para el rango exacto del backtest
    candles = await get_candles(symbol=symbol, interval=interval, start_time=start_time, end_time=end_time)
    if not candles:
        raise ValueError(f"No hay candles para {symbol} {interval} en rango {start_time} → {end_time}")

    series_start_time = candles[0].open_time
    series_end_time = candles[-1].close_time

    # Cargar todos los snapshots para el rango
    trends = await get_trends_for_range(symbol, interval, series_start_time, series_end_time)
    ema_snapshots = await get_ema_snapshots_for_range(symbol, interval, series_start_time, series_end_time)
    adx_snapshots = await get_adx_snapshots_for_range(symbol, interval, series_start_time, series_end_time)
    smi_snapshots = await get_smi_snapshots_for_range(symbol, interval, series_start_time, series_end_time)
    sr_levels = await get_sr_levels_for_range(symbol, interval, series_start_time, series_end_time)

    # Organizar snapshots EMA por span
    ema_points: dict[str, list[dict]] = {}
    for snap in ema_snapshots:
        span = str(snap.get("span"))
        ema_points.setdefault(span, []).append(snap)

    # Construir payload de series
    payload = build_series_payload(
        candles=candles,
        trends=trends,
        ema_points=ema_points,
        smi_points=smi_snapshots,
        sr_levels=sr_levels,
        adx_points=adx_snapshots if adx_snapshots else None,
    )

    if payload is None:
        raise ValueError("No se pudo construir el payload de series")

    return SeriesDataResponse.model_validate(payload)