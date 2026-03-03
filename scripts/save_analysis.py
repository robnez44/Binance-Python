"""
Hace el análisis completo y lo persiste en MongoDB.

  1. Descarga velas de Binance
  2. Guarda candles en MongoDB
  3. Calcula tendencias (classify_trends)
  4. Calcula EMAs + snapshots (ema_analysis)
  5. Calcula ADX + snapshots
  6. Calcula SMI + snapshots
  7. Arma el AnalysisRecord
  8. Guarda todo en colecciones (candles, trends, ema_snapshots, adx_snapshots, smi_snapshots, analysis)
"""
import asyncio
from datetime import datetime, timezone
import numpy as np
import pandas as pd

from services.binance import get_klines
from scripts.classify_trends import find_all_trends
from indicators.emas import (compute_ema, ema_pct_slope, ema_slope, build_ema_snapshots,)
from indicators.adx import compute_adx, build_adx_snapshots
from indicators.smi import compute_squeeze, build_smi_snapshots
from utils.utils import ask_candles_params, toDicto
from database.database import connectDB, disconnect
from database.repository import (
    ensure_indexes, save_candles, save_trends,
    save_ema_snapshots, save_adx_snapshots, save_smi_snapshots, save_analysis,
)
from database.schemas import AnalysisRecord, Candle


# ── Parámetros ────────────────────────────────────────────────────────────── #
EMA_SPANS  = [10, 55, 200]
WINDOW     = 10
MIN_WIN    = 5
MIN_R2     = 0.65
PCT_SLOPE_MIN = 0.05


async def main():
    # ── 1. Descarga de datos ──────────────────────────────────────────────
    params = ask_candles_params()
    data   = get_klines(params)

    symbol   = params["symbol"]
    interval = params["interval"]

    cleaned = [toDicto(kline) for kline in data]
    times   = pd.to_datetime([k["close_time"] for k in cleaned], utc=True)
    prices  = np.array([float(k["close_price"]) for k in cleaned], dtype=float)
    highs   = np.array([float(k["high_price"])  for k in cleaned], dtype=float)
    lows    = np.array([float(k["low_price"])   for k in cleaned], dtype=float)

    high_s  = pd.Series(highs,  index=times)
    low_s   = pd.Series(lows,   index=times)
    close_s = pd.Series(prices, index=times)

    print(f"\n{'─'*60}")
    print(f"  {symbol} | {interval} | {len(prices)} velas")
    print(f"  Rango: {times[0]}  →  {times[-1]}")
    print(f"{'─'*60}")

    # ── 2. Candles ────────────────────────────────────────────────────────
    candles = []
    for k in cleaned:
        candles.append(Candle(
            symbol=symbol,
            interval=interval,
            open_time=k["open_time"] if isinstance(k["open_time"], datetime) else k["open_time"].to_pydatetime(),
            open_price=float(k["open_price"]),
            high_price=float(k["high_price"]),
            low_price=float(k["low_price"]),
            close_price=float(k["close_price"]),
            volume=float(k["volume"]),
            close_time=k["close_time"] if isinstance(k["close_time"], datetime) else k["close_time"].to_pydatetime(),
            quote_asset_volume=float(k["quote_asset_volume"]),
            number_of_trades=int(k["number_of_trades"]),
            taker_buy_base_asset_volume=float(k["taker_buy_base_asset_volume"]),
            taker_buy_quote_asset_volume=float(k["taker_buy_quote_asset_volume"]),
        ))
    print(f"\n  Candles preparadas: {len(candles)}")

    # ── 3. Tendencias ─────────────────────────────────────────────────────
    trends = find_all_trends(
        prices, times, symbol, interval,
        WINDOW, MIN_WIN, MIN_R2, PCT_SLOPE_MIN,
    )
    print(f"  Tendencias detectadas: {len(trends)}")
    for t in trends:
        print(f"    {t.regime:>4}  velas {t.start_idx}–{t.end_idx}  "
              f"R²={t.r2:.2f}  pct_slope={t.pct_slope:+.4f}%")

    # ── 4. EMAs ───────────────────────────────────────────────────────────
    all_ema_snapshots = []
    snapshots_by_span = {}

    for span in EMA_SPANS:
        ema_vals   = compute_ema(prices, span)
        abs_slopes = ema_slope(ema_vals)
        pct_slopes = ema_pct_slope(ema_vals)

        snaps = build_ema_snapshots(
            symbol, interval, span, prices,
            ema_vals, abs_slopes, pct_slopes, times,
        )
        all_ema_snapshots.extend(snaps)
        snapshots_by_span[str(span)] = snaps

        last = snaps[-1]
        print(f"  EMA {span:>3}: {last.ema_value:>12.2f}  "
              f"slope={last.pct_slope:+.4f}%  "
              f"dist={last.distance_pct:+.2f}%")

    # ── 5. ADX ────────────────────────────────────────────────────────────
    adx_df = compute_adx(high_s, low_s, close_s, n=14)
    adx_snaps = build_adx_snapshots(symbol, interval, adx_df, times)
    last_adx = adx_snaps[-1]
    print(f"  ADX: {last_adx.adx:>8.2f}  +DI={last_adx.plus_di:.2f}  -DI={last_adx.minus_di:.2f}")

    # ── 6. SMI ────────────────────────────────────────────────────────────
    sqz_df = compute_squeeze(high_s, low_s, close_s)
    smi_snaps = build_smi_snapshots(symbol, interval, sqz_df, times)
    last_smi = smi_snaps[-1]
    print(f"  SMI: {last_smi.smi:>+.4f}")

    # ── 7. AnalysisRecord ─────────────────────────────────────────────────
    record = AnalysisRecord(
        symbol=symbol,
        interval=interval,
        start_time=times[0].to_pydatetime(),
        end_time=times[-1].to_pydatetime(),
        start_price=float(prices[0]),
        end_price=float(prices[-1]),
        total_candles=len(prices),
        trends=trends,
        ema_points=snapshots_by_span,
        adx_points=adx_snaps,
        smi_points=smi_snaps,
        created_at=datetime.now(timezone.utc),
    )

    # ── 8. Guardar en MongoDB ─────────────────────────────────────────────
    await connectDB()
    await ensure_indexes()

    n_candles = await save_candles(candles)
    n_trends  = await save_trends(trends)
    n_snaps   = await save_ema_snapshots(all_ema_snapshots)
    n_adx     = await save_adx_snapshots(adx_snaps)
    n_smi     = await save_smi_snapshots(smi_snaps)
    analysis_id = await save_analysis(record)

    print(f"\n  Candles guardadas/actualizadas: {n_candles}")
    print(f"  Trends guardados/actualizados: {n_trends}")
    print(f"  EMA snap guardados/actualizados: {n_snaps}")
    print(f"  ADX snap guardados/actualizados: {n_adx}")
    print(f"  SMI snap guardados/actualizados: {n_smi}")
    print(f"  Analysis record: {analysis_id}")

    await disconnect()

if __name__ == "__main__":
    asyncio.run(main())
