from services.binance import get_klines
from indicators.levels import find_support_resistance
from utils.utils import ask_candles_params, timestamp_to_utc, toDicto
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import json

if __name__ == "__main__":

    # ── Descarga de datos ─────────────────────────────────────────────────
    params = ask_candles_params()
    data = get_klines(params)

    cleaned_data = [toDicto(kline) for kline in data]
    print("\nÚltima vela:")
    print(json.dumps(cleaned_data[-1], indent=3, default=str))

    times = pd.to_datetime([k["close_time"] for k in cleaned_data], utc=True)
    prices = np.array([float(k["close_price"]) for k in cleaned_data], dtype=float)
    opens = np.array([float(k["open_price"]) for k in cleaned_data], dtype=float)
    highs = np.array([float(k["high_price"]) for k in cleaned_data], dtype=float)
    lows = np.array([float(k["low_price"]) for k in cleaned_data], dtype=float)

    high_s = pd.Series(highs, index=times)
    low_s = pd.Series(lows, index=times)
    close_s = pd.Series(prices, index=times)

    symbol = params["symbol"]
    interval = params["interval"]

    # ── Soportes y Resistencias ───────────────────────────────────────────
    sr_levels = find_support_resistance(
        high_s, low_s, close_s, times, symbol, interval,
        atr_n=14, tol_mult=0.75, touch_tol_mult=0.3, min_touches=1,
    )

    print(f"\nTotal de velas: {len(prices)}")
    print(f"Soportes y resistencias: {len(sr_levels)}")
    for lvl in sr_levels:
        tag = "SUP" if lvl.level_type == "support" else "RES"
        print(f"  {tag}  precio={lvl.price:>12.2f}  toques={lvl.touches:>3}  "
              f"{pd.Timestamp(lvl.timestamp).strftime('%Y-%m-%d %H:%M')}")

    # ══════════════════════════════════════════════════════════════════════
    #  Gráfico: velas japonesas + S/R
    # ══════════════════════════════════════════════════════════════════════
    fig, ax = plt.subplots(figsize=(22, 10))

    # ── Velas japonesas ───────────────────────────────────────────────────
    if len(times) > 1:
        candle_width = (times[1] - times[0]) * 0.7
    else:
        candle_width = pd.Timedelta(hours=1)

    bull = prices >= opens
    bear = ~bull

    # Cuerpos
    ax.bar(times[bull], (prices[bull] - opens[bull]), bottom=opens[bull],
           width=candle_width, color="#26a69a", edgecolor="#26a69a", zorder=3)
    ax.bar(times[bear], (prices[bear] - opens[bear]), bottom=opens[bear],
           width=candle_width, color="#ef5350", edgecolor="#ef5350", zorder=3)

    # Mechas
    ax.vlines(times[bull], lows[bull], highs[bull],
              color="#26a69a", linewidth=0.8, zorder=2)
    ax.vlines(times[bear], lows[bear], highs[bear],
              color="#ef5350", linewidth=0.8, zorder=2)

    # ── Soportes y Resistencias (extremo a extremo) ───────────────────────
    for lvl in sr_levels:
        color = "#2196F3" if lvl.level_type == "support" else "#FF9800"
        alpha = min(0.5 + lvl.touches * 0.05, 1.0)

        ax.hlines(lvl.price, xmin=times[0], xmax=times[-1],
                  colors=color, linestyles="--", linewidth=0.7,
                  alpha=alpha, zorder=5)

        # Anotación: precio + toques
        label = f"  ${lvl.price:.0f}"
        ax.annotate(
            label,
            xy=(times[-1], lvl.price),
            fontsize=8, fontweight="bold" if lvl.touches >= 3 else "normal",
            color=color, alpha=0.95,
            va="center", ha="left",
        )

        # Marcador en la vela de detección
        marker = "^" if lvl.level_type == "support" else "v"
        ax.scatter(times[lvl.idx], lvl.price, marker=marker, s=60,
                   color=color, edgecolors="black", linewidths=0.5, zorder=6)

    # ── Leyenda ───────────────────────────────────────────────────────────
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], color="#2196F3", linestyle="--", linewidth=1.5, label="Soporte"),
        Line2D([0], [0], color="#FF9800", linestyle="--", linewidth=1.5, label="Resistencia"),
        Line2D([0], [0], marker="^", color="#2196F3", linestyle="None",
               markersize=8, label="Fractal soporte"),
        Line2D([0], [0], marker="v", color="#FF9800", linestyle="None",
               markersize=8, label="Fractal resistencia"),
    ]
    ax.legend(handles=legend_elements, loc="best", fontsize=9)

    ax.set_ylabel("Precio (USDT)")
    ax.set_title(f"{symbol} • {interval} • Soportes y Resistencias  "
                 f"({len(sr_levels)} niveles)")
    ax.grid(True, alpha=0.2)

    fig.autofmt_xdate()
    plt.tight_layout()

    try:
        manager = plt.get_current_fig_manager()
        manager.window.showMaximized()
    except Exception:
        pass

    plt.show()
