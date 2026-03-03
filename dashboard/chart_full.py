from services.binance import get_klines
from indicators.emas import compute_ema, ema_pct_slope, ema_slope
from indicators.adx import compute_adx
from indicators.smi import compute_squeeze
from scripts.classify_trends import find_all_trends
from utils.utils import ask_candles_params, timestamp_to_utc, toDicto
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd
import json

if __name__ == "__main__":

    # ── Descarga de datos ─────────────────────────────────────────────────
    params = ask_candles_params()
    data = get_klines(params)

    timestamp_ms = data[0][0]
    print("Fecha de apertura de la primera vela:", timestamp_to_utc(timestamp_ms))

    cleaned_data = [toDicto(kline) for kline in data]
    print("\nÚltima vela:")
    print(json.dumps(cleaned_data[-1], indent=3, default=str))

    times = pd.to_datetime([k["close_time"] for k in cleaned_data], utc=True)
    prices = np.array([float(k["close_price"]) for k in cleaned_data], dtype=float)
    highs = np.array([float(k["high_price"]) for k in cleaned_data], dtype=float)
    lows = np.array([float(k["low_price"]) for k in cleaned_data], dtype=float)

    high_s = pd.Series(highs, index=times)
    low_s = pd.Series(lows, index=times)
    close_s = pd.Series(prices, index=times)

    symbol = params["symbol"]
    interval = params["interval"]

    # ── EMAs ──────────────────────────────────────────────────────────────
    EMA_SPANS = [10, 55, 200]
    EMA_COLORS = {10: "pink", 55: "orange", 200: "red"}

    emas = {}
    pct_slopes = {}
    slopes = {}
    for span in EMA_SPANS:
        emas[span] = compute_ema(prices, span)
        pct_slopes[span] = ema_pct_slope(emas[span])
        slopes[span] = ema_slope(emas[span])

    # ── ADX ───────────────────────────────────────────────────────────────
    adx_df = compute_adx(high_s, low_s, close_s, n=14)

    # ── Squeeze Momentum ─────────────────────────────────────────────────
    sqz_df = compute_squeeze(high_s, low_s, close_s)

    # ── Tendencias ────────────────────────────────────────────────────────
    WINDOW = 10
    MIN_WIN = 5
    MIN_R2 = 0.65
    PCT_SLOPE_MIN = 0.05
    trends = find_all_trends(
        prices, times, symbol, interval,
        WINDOW, MIN_WIN, MIN_R2, PCT_SLOPE_MIN,
    )

    # ── Info por consola ──────────────────────────────────────────────────
    print(f"\nTotal de velas: {len(prices)}")
    for span in EMA_SPANS:
        last_ema = emas[span][-1]
        last_pct = pct_slopes[span][-1]
        last_abs = slopes[span][-1]
        print(f"  EMA {span:>3}:  Valor = {last_ema:>12.2f}   "
              f"Pend% = {last_pct:>+.4f}%   "
              f"Pend abs = {last_abs:>+.2f} USDT")

    print(f"\n  ADX  : {adx_df['ADX'].iloc[-1]:>8.2f}")
    print(f"  Squeeze ON : {'Sí' if sqz_df['squeeze_on'].iloc[-1] else 'No'}")
    print(f"  Momentum   : {sqz_df['mom'].iloc[-1]:>+.4f}")
    print(f"\n  Tendencias detectadas: {len(trends)}")
    for i, t in enumerate(trends, 1):
        print(f"    #{i:>2} {t.regime:>4}  velas {t.start_idx}–{t.end_idx}  "
              f"R²={t.r2:.2f}  pct_slope={t.pct_slope:+.4f}%")

    # ══════════════════════════════════════════════════════════════════════
    #  Gráfico con 4 subplots
    # ══════════════════════════════════════════════════════════════════════
    fig = plt.figure(figsize=(22, 14))
    gs = gridspec.GridSpec(
        4, 1,
        height_ratios=[3, 1, 2, 1.8],
        hspace=0.08,
    )

    ax_price = fig.add_subplot(gs[0])
    ax_slope = fig.add_subplot(gs[1], sharex=ax_price)
    ax_trend = fig.add_subplot(gs[2], sharex=ax_price)
    ax_sqz = fig.add_subplot(gs[3], sharex=ax_price)

    # ── 1) Precio + EMAs ─────────────────────────────────────────────────
    ax_price.plot(
        times, prices,
        marker="o", ms=2, color="steelblue", linewidth=1,
        label="Precio cierre", zorder=2,
    )
    for span in EMA_SPANS:
        ax_price.plot(
            times, emas[span],
            linewidth=1.5, color=EMA_COLORS[span],
            label=f"EMA {span}", zorder=3,
        )
    ax_price.set_ylabel("Precio (USDT)")
    ax_price.set_title(f"{symbol} • {interval} • Precio + EMAs + ADX + Squeeze")
    ax_price.legend(loc="best", fontsize=8)
    ax_price.grid(True, alpha=0.2)

    # ── 2) Pendientes de las EMAs ─────────────────────────────────────────
    for span in EMA_SPANS:
        ax_slope.plot(
            times, pct_slopes[span],
            linewidth=1.2, color=EMA_COLORS[span],
            label=f"Pend EMA {span} (%)", zorder=2,
        )
    ax_slope.axhline(0, color="black", linewidth=0.8, linestyle="--", alpha=0.5)
    ax_slope.set_ylabel("Pendiente (%)")
    ax_slope.legend(loc="best", fontsize=7)
    ax_slope.grid(True, alpha=0.2)

    # ── 3) Tendencias ─────────────────────────────────────────────────────
    color_map = {"UP": "green", "DOWN": "red", "SIDE": "gray"}

    ax_trend.plot(
        times, prices,
        marker="o", ms=2, color="steelblue", linewidth=1,
        label="Precio cierre", zorder=2,
    )

    labeled = set()
    for seg in trends:
        c = color_map[seg.regime]

        # Zona sombreada
        ax_trend.axvspan(times[seg.start_idx], times[seg.end_idx],
                         color=c, alpha=0.12, zorder=1)

        # Recta y = a·x + b sobre la subventana
        x_seg = np.arange(seg.length, dtype=float)
        y_seg = seg.a * x_seg + seg.b
        label = seg.regime if seg.regime not in labeled else None
        
        ax_trend.plot(times[seg.start_idx : seg.end_idx + 1], y_seg,
                      linewidth=2, linestyle="--", color=c, zorder=3,
                  label=label)
        labeled.add(seg.regime)

    ax_trend.set_ylabel("Precio (USDT)")
    ax_trend.legend(loc="best", fontsize=7, ncol=3)
    ax_trend.grid(True, alpha=0.2)

    # ── 4) Squeeze Momentum + ADX ────────────────────────────────────────
    ax_sqz.set_facecolor("#1a1a2e")

    mom = sqz_df["mom"].values
    sqz_off = sqz_df["squeeze_off"].values.astype(bool)

    # Barras coloreadas por signo y aceleración
    colors = []
    for i in range(len(mom)):
        if mom[i] >= 0:
            colors.append("lime" if (i > 0 and mom[i] > mom[i - 1]) else "darkgreen")
        else:
            colors.append("red" if (i > 0 and mom[i] < mom[i - 1]) else "darkred")

    # ancho de barra ≈ 80 % del intervalo entre velas
    if len(times) > 1:
        bar_width = (times[1] - times[0]) * 0.8
    else:
        bar_width = None
    ax_sqz.bar(times, mom, width=bar_width, color=colors, alpha=0.85, zorder=2)

    # Indicador de squeeze (cruces en la línea cero)
    cross_colors = ["gray" if off else "white" for off in sqz_off]
    ax_sqz.scatter(times, np.zeros(len(times)), marker="x", c=cross_colors,
                   s=22, linewidths=1.2, zorder=4)

    # ADX superpuesto (línea blanca, eje derecho)
    ax_adx_overlay = ax_sqz.twinx()
    ax_adx_overlay.set_facecolor("none")   # transparente, hereda fondo oscuro
    ax_adx_overlay.plot(times, adx_df["ADX"].values, color="white",
                        linewidth=1.3, alpha=0.9, zorder=5, label="ADX")
    ax_adx_overlay.set_ylabel("ADX", color="white", fontsize=9)
    ax_adx_overlay.tick_params(axis="y", colors="white", labelsize=8)
    # Centrar el rango del ADX para que la línea quede sobre las barras
    adx_ceil = max(60, np.nanmax(adx_df["ADX"].values) * 1.2)
    ax_adx_overlay.set_ylim(-adx_ceil * 0.4, adx_ceil)

    ax_sqz.axhline(0, color="white", linewidth=0.5, alpha=0.35)
    ax_sqz.set_ylabel("Squeeze Mom", color="white", fontsize=9)
    ax_sqz.set_xlabel("Fecha de cierre (UTC)")
    ax_sqz.tick_params(axis="y", colors="white", labelsize=8)
    ax_sqz.grid(True, alpha=0.15, color="gray")

    # Leyenda manual para cruces squeeze + ADX
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker="x", color="white", linestyle="None",
               markersize=6, label="Squeeze ON"),
        Line2D([0], [0], marker="x", color="gray", linestyle="None",
               markersize=6, label="Squeeze OFF"),
        Line2D([0], [0], color="white", linewidth=1.5, label="ADX"),
    ]
    ax_sqz.legend(handles=legend_elements, loc="best", fontsize=7,
                  facecolor="#1a1a2e", edgecolor="gray", labelcolor="white")

    # Ocultar x-labels de subplots superiores
    for ax in [ax_price, ax_slope, ax_trend]:
        plt.setp(ax.get_xticklabels(), visible=False)

    fig.autofmt_xdate()
    plt.tight_layout()

    try:
        manager = plt.get_current_fig_manager()
        manager.window.showMaximized()
    except Exception:
        pass

    plt.show()
