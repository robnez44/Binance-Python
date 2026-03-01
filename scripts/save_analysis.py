"""
Hace el análisis completo y lo persiste en MongoDB.

  1. Descarga velas de Binance
  2. Calcula tendencias (classify_trends)
  3. Calcula EMAs + snapshots (ema_analysis)
  4. Arma el AnalysisRecord
  5. Guarda todo en 3 colecciones (trends, ema_snapshots, analysis)
"""

import asyncio
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from services.binance import get_klines
from scripts.classify_trends import find_all_trends
from scripts.ema_analysis import (compute_ema, ema_pct_slope, ema_slope, build_ema_snapshots,)
from utils.utils import ask_candles_params, toDicto
from database.database import connectDB, disconnect
from database.repository import ensure_indexes, save_trends, save_ema_snapshots, save_analysis
from database.schemas import AnalysisRecord


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

    print(f"\n{'─'*60}")
    print(f"  {symbol} | {interval} | {len(prices)} velas")
    print(f"  Rango: {times[0]}  →  {times[-1]}")
    print(f"{'─'*60}")

    # ── 2. Tendencias ─────────────────────────────────────────────────────
    trends = find_all_trends(
        prices, times, symbol, interval,
        WINDOW, MIN_WIN, MIN_R2, PCT_SLOPE_MIN,
    )
    print(f"\n  Tendencias detectadas: {len(trends)}")
    for t in trends:
        print(f"    {t.regime:>4}  velas {t.start_idx}–{t.end_idx}  "
              f"R²={t.r2:.2f}  pct_slope={t.pct_slope:+.4f}%")

    # ── 3. EMAs ───────────────────────────────────────────────────────────
    all_snapshots = []          # lista plana para save_ema_snapshots
    snapshots_by_span = {}      # dict[str, list] para AnalysisRecord

    for span in EMA_SPANS:
        ema_vals   = compute_ema(prices, span)
        abs_slopes = ema_slope(ema_vals)
        pct_slopes = ema_pct_slope(ema_vals)

        snaps = build_ema_snapshots(
            symbol, interval, span, prices,
            ema_vals, abs_slopes, pct_slopes, times,
        )
        all_snapshots.extend(snaps)
        snapshots_by_span[str(span)] = snaps

        last = snaps[-1]
        print(f"  EMA {span:>3}: {last.ema_value:>12.2f}  "
              f"slope={last.pct_slope:+.4f}%  "
              f"dist={last.distance_pct:+.2f}%")

    # ── 4. AnalysisRecord ─────────────────────────────────────────────────
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
        created_at=datetime.now(timezone.utc),
    )

    # ── 5. Guardar en MongoDB ─────────────────────────────────────────────
    await connectDB()
    await ensure_indexes()

    n_trends = await save_trends(trends)
    n_snaps  = await save_ema_snapshots(all_snapshots)
    analysis_id = await save_analysis(record)

    print(f"\n  Trends guardados/actualizados: {n_trends}")
    print(f"  EMA snap guardados/actualizados: {n_snaps}")
    print(f"  Analysis record: {analysis_id}")

    await disconnect()

if __name__ == "__main__":
    asyncio.run(main())
