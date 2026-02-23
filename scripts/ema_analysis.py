from services.binance import get_klines
from utils.utils import ask_candles_params, timestamp_to_utc, toDicto
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import json

# ──────────────────────────────────────────────────────────────────────────── #
#  Cálculo de EMAs y su pendiente
# ──────────────────────────────────────────────────────────────────────────── #

def compute_ema(prices: np.ndarray, span: int) -> np.ndarray:
    """Calcula la EMA usando pandas (exactamente igual que la fórmula clásica)."""
    s = pd.Series(prices)
    return s.ewm(span=span, adjust=False).mean().to_numpy()


def ema_pct_slope(ema: np.ndarray) -> np.ndarray:
    """Pendiente porcentual punto a punto de una EMA.

    slope[i] = (ema[i] - ema[i-1]) / ema[i-1] * 100
        """
    # El primer valor se rellena con 0.0 (no hay pendiente definida).
    n = len(ema)
    slope = np.zeros(n)
    for i in range(1, n):
        if ema[i - 1] != 0:
            slope[i] = (ema[i] - ema[i - 1]) / ema[i - 1] * 100
    return slope

def ema_slope(ema: np.ndarray) -> np.ndarray:
    """Pendiente absoluta punto a punto de una EMA.

    slope[i] = ema[i] - ema[i-1]
        """
    n = len(ema)
    slope = np.zeros(n)
    for i in range(1, n):
        slope[i] = ema[i] - ema[i - 1]
    return slope


# ──────────────────────────────────────────────────────────────────────────── #
#  Main
# ──────────────────────────────────────────────────────────────────────────── #

if __name__ == "__main__":

    # ── Descarga de datos ─────────────────────────────────────────────────
    params = ask_candles_params()
    data = get_klines(params)

    timestamp_ms = data[0][0]
    date_utc = timestamp_to_utc(timestamp_ms)
    print("\nFecha de apertura de la primera vela:", date_utc)

    # ── Limpiar y preparar datos ──────────────────────────────────────────
    cleaned_data = [toDicto(kline) for kline in data]
    print("\nInformacion de la última vela:")
    print(json.dumps(cleaned_data[-1], indent=3, default=str))

    times = pd.to_datetime([k["close_time"] for k in cleaned_data], utc=True)
    prices = np.array([float(k["close_price"]) for k in cleaned_data], dtype=float)

    # ── Parametros EMA ────────────────────────────────────────────────────
    EMA_SPANS = [10, 50, 200]           # agregar 200 cuando quieras
    EMA_COLORS = {10: "pink", 50: "orange", 200: "red"}

    # ── Calculos ───────────────────────────────────────────────────────────
    emas = {}
    pct_slopes = {}
    slopes = {}
    for span in EMA_SPANS:
        emas[span] = compute_ema(prices, span)
        pct_slopes[span] = ema_pct_slope(emas[span])
        slopes[span] = ema_slope(emas[span])


    # ── Info por consola ──────────────────────────────────────────────────
    print(f"\nTotal de velas: {len(prices)}")
    for span in EMA_SPANS:
        last_ema = emas[span][-1]
        last_pct_slope = pct_slopes[span][-1]
        last_slope = slopes[span][-1]
        print(f"  EMA {span:>3}:  Ultimo valor = {last_ema:>12.2f}   "
              f"Pendiente = {last_pct_slope:>+.4f} %   "
              f"Pendiente abs (Δ$ de la ult. vela) = {last_slope:>+.2f} USDT")

    # ── Gráfico ───────────────────────────────────────────────────────────
    fig, (ax_price, ax_slope) = plt.subplots(
        2, 1, figsize=(14, 8),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
    )

    # --- Subplot superior: precio + EMAs ---
    ax_price.plot(
        times, prices,
        marker="o", ms=2, color="steelblue", linewidth=1,
        label="Close price", zorder=2,
    )

    for span in EMA_SPANS:
        ax_price.plot(
            times, emas[span],
            linewidth=1.5, color=EMA_COLORS[span],
            label=f"EMA {span}", zorder=3,
        )

    ax_price.set_ylabel("Precio de cierre (USDT)")
    ax_price.set_title("BTCUSDT • Precio + EMAs")
    ax_price.legend(loc="best", fontsize=9)
    ax_price.grid(True, alpha=0.2)

    # --- Subplot inferior: pendientes de las EMAs ---
    for span in EMA_SPANS:
        ax_slope.plot(
            times, slopes[span],
            linewidth=1.2, color=EMA_COLORS[span],
            label=f"Pendiente EMA {span} (%)", zorder=2,
        )

    ax_slope.axhline(0, color="black", linewidth=0.8, linestyle="--", alpha=0.5)
    ax_slope.set_ylabel("Pendiente (%)")
    ax_slope.set_xlabel("Fecha de cierre (UTC)")
    ax_slope.legend(loc="best", fontsize=9)
    ax_slope.grid(True, alpha=0.2)

    fig.autofmt_xdate()
    plt.tight_layout()
    plt.show()