from services.binance import get_klines
from scripts.classify_trends import find_all_trends
from scripts.ema_analysis import compute_ema, ema_pct_slope, ema_slope
from utils.utils import ask_candles_params, timestamp_to_utc, toDicto
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import json

if __name__ == "__main__":

    # ── Descarga de datos (una sola vez) ──────────────────────────────────
    params = ask_candles_params()
    data = get_klines(params)

    timestamp_ms = data[0][0]
    print("Fecha de apertura de la primera vela:", timestamp_to_utc(timestamp_ms))

    cleaned_data = [toDicto(kline) for kline in data]
    times = pd.to_datetime([k["close_time"] for k in cleaned_data], utc=True)
    prices = np.array([float(k["close_price"]) for k in cleaned_data], dtype=float)

    # ── Tendencias ────────────────────────────────────────────────────────
    WINDOW = 10
    MIN_WIN = 5
    MIN_R2 = 0.65
    PCT_SLOPE_MIN = 0.05

    trends = find_all_trends(prices, times, WINDOW, MIN_WIN, MIN_R2, PCT_SLOPE_MIN)

    # ── EMAs ──────────────────────────────────────────────────────────────
    EMA_SPANS = [10, 50, 200]
    EMA_COLORS = {10: "pink", 50: "orange", 200: "red"}

    emas = {}
    pct_slopes = {}
    slopes = {}
    for span in EMA_SPANS:
        emas[span] = compute_ema(prices, span)
        pct_slopes[span] = ema_pct_slope(emas[span])
        slopes[span] = ema_slope(emas[span])

    # ── Info por consola: Tendencias ───────────────────────────────────────
    print(f"\nTotal de velas: {len(prices)}")
    print(f"Tendencias detectadas: {len(trends)}\n")
    print(f"{'#':>2}  {'Régimen':<6}  {'Inicio':>6} → {'Fin':>6}  {'Length':>4}  "
          f"{'P.Inicio':>10}  {'P.Final':>10}  "
          f"{'a':>12}  {'pct_slope':>10}  {'R²':>8}  {'Rango temporal'}")
    print("─" * 130)

    for i, seg in enumerate(trends, 1):
        t0 = pd.Timestamp(seg.start_time).strftime("%Y/%m/%d %H:%M")
        t1 = pd.Timestamp(seg.end_time).strftime("%Y/%m/%d %H:%M")
        print(f"{i:>2}  {seg.regime:<6}  {seg.start_idx:>6} → {seg.end_idx:>6}  "
              f"{seg.length:>4}  {seg.start_price:>10.2f}  {seg.end_price:>10.2f}  "
              f"{seg.a:>+12.4f}  {seg.pct_slope:>+10.4f}%  "
              f"{seg.r2:>8.4f}  {t0} → {t1}")

    # ── Info por consola: EMAs ─────────────────────────────────────────────
    print()
    for span in EMA_SPANS:
        last_ema = emas[span][-1]
        last_pct_slope = pct_slopes[span][-1]
        last_slope = slopes[span][-1]
        print(f"  EMA {span:>3}:  Ultimo valor = {last_ema:>12.2f}   "
              f"Pendiente = {last_pct_slope:>+.4f} %   "
              f"Pendiente abs (Δ$ de la ult. vela) = {last_slope:>+.2f} USDT")

    # ── Gráfico: 3 subplots ───────────────────────────────────────────────
    color_map = {"UP": "green", "DOWN": "red", "SIDE": "gray"}

    fig, (ax_trends, ax_emas, ax_slope) = plt.subplots(
        3, 1, figsize=(14, 12),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 3, 1]},
    )

    # ── 1) Precio + Tendencias ────────────────────────────────────────────
    ax_trends.plot(times, prices, marker="o", ms=2, color="steelblue",
                   linewidth=1, label="Close price", zorder=2)

    labeled = set()
    for seg in trends:
        c = color_map[seg.regime]
        ax_trends.axvspan(times[seg.start_idx], times[seg.end_idx],
                          color=c, alpha=0.10, zorder=1)
        x_seg = np.arange(seg.length, dtype=float)
        y_seg = seg.a * x_seg + seg.b
        label = seg.regime if seg.regime not in labeled else None
        ax_trends.plot(times[seg.start_idx : seg.end_idx + 1], y_seg,
                       linewidth=2, linestyle="--", color=c, zorder=3,
                       label=label)
        labeled.add(seg.regime)

    ax_trends.set_ylabel("Precio (USDT)")
    ax_trends.set_title("Precio + Tendencias")
    ax_trends.legend(loc="best", fontsize=7, ncol=2)
    ax_trends.grid(True, alpha=0.2)

    # ── 2) Precio + EMAs ──────────────────────────────────────────────────
    ax_emas.plot(times, prices, marker="o", ms=2, color="steelblue",
                 linewidth=1, label="Close price", zorder=2)

    for span in EMA_SPANS:
        ax_emas.plot(times, emas[span], linewidth=1.5,
                     color=EMA_COLORS[span], label=f"EMA {span}", zorder=3)

    ax_emas.set_ylabel("Precio (USDT)")
    ax_emas.set_title("Precio + EMAs")
    ax_emas.legend(loc="best", fontsize=9)
    ax_emas.grid(True, alpha=0.2)

    # ── 3) Pendientes de las EMAs ─────────────────────────────────────────
    for span in EMA_SPANS:
        ax_slope.plot(times, pct_slopes[span], linewidth=1.2,
                      color=EMA_COLORS[span],
                      label=f"Pendiente EMA {span} (%)", zorder=2)

    ax_slope.axhline(0, color="black", linewidth=0.8, linestyle="--", alpha=0.5)
    ax_slope.set_ylabel("Pendiente (%)")
    ax_slope.set_xlabel("Fecha de cierre (UTC)")
    ax_slope.legend(loc="best", fontsize=9)
    ax_slope.grid(True, alpha=0.2)

    fig.autofmt_xdate()
    plt.tight_layout()
    plt.show()
