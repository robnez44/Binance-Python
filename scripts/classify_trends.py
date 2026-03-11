from datetime import datetime, timezone
from typing import List, Optional, Tuple
from database.schemas import SegmentMetrics
from services.binance import get_klines
from utils.utils import ask_candles_params, timestamp_to_utc, candles_to_dict
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import json

# ──────────────────────────────────────────────────────────────────────────── #
#  Funciones de regresión lineal y clasificación de tendencias

def fit_model_metrics(
    y_win: np.ndarray,
) -> Tuple[float, float, float, float, float, Optional[np.ndarray]]:
    n = len(y_win)
    if n < 2:
        return np.nan, np.nan, np.nan, np.nan, np.nan, None

    x = np.arange(n, dtype=float)
    a, b = np.polyfit(x, y_win, 1)
    y_hat = a * x + b

    mean_y = float(y_win.mean())
    ss_res = float(np.sum((y_win - y_hat) ** 2))
    ss_tot = float(np.sum((y_win - mean_y) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot != 0.0 else 0.0

    pct_slope = (a / mean_y) * 100.0 if mean_y != 0.0 else 0.0

    return float(a), float(b), float(r2), float(pct_slope), mean_y, y_hat

def classify_trend(
    a: float,
    r2: float,
    r2_min: float,
    pct_slope: float,
    pct_slope_min: float,
) -> str:
    if np.isnan(r2) or r2 < r2_min or np.isnan(a):
        return "SIDE"
    if not np.isnan(pct_slope) and abs(pct_slope) < pct_slope_min:
        return "SIDE"
    return "UP" if a > 0 else "DOWN"

def find_all_trends(
    prices: np.ndarray,
    times: np.ndarray,
    symbol: str,
    interval: str,
    window: int = 10,
    min_win: int = 5,
    r2_min: float = 0.50,
    pct_slope_min: float = 0.0,
) -> List[SegmentMetrics]:
    """Segmenta TODA la serie de precios en tendencias consecutivas.

    Algoritmo greedy con extensión controlada:
      1. Desde *start*, evaluar subventanas de tamaño L ∈ [min_win … window].
         Elegir la más **larga** con R² ≥ r2_min (tendencia válida).
         Si ninguna cumple, usar la de mejor R² como SIDE.
      2. **Extensión**: si el segmento es tendencia (UP/DOWN), intentar
         alargar vela a vela mientras R² ≥ r2_min y el régimen se mantenga.
         Máximo extra: min_win - 1 velas  →  tope = window + min_win - 1.
      3. Registrar el segmento y avanzar *start*.

    Garantías:
      - Ningún segmento < min_win velas.
      - Ningún segmento > window + min_win - 1 velas.

    Parameters
    ----------
    prices        : ndarray  – serie completa de precios (float).
    window        : int      – tamaño máximo de la ventana semilla.
    min_win       : int      – tamaño mínimo de subventana.
    r2_min        : float    – R² mínimo para considerar tendencia.
    pct_slope_min : float    – |pct_slope| mínimo (0.0 → solo R²+signo).

    Returns
    -------
    list[SegmentMetrics]  – lista ordenada de segmentos consecutivos.
    """
    assert min_win >= 2, "min_win debe ser >= 2"
    assert min_win <= window, "min_win no puede ser mayor que window"

    segments: List[SegmentMetrics] = []
    n = len(prices)
    start = 0

    while start <= n - min_win:
        max_len = min(window, n - start)

        best_seg: Optional[SegmentMetrics] = None

        for length in range(min_win, max_len + 1):
            end_i = start + length - 1
            y_win = prices[start : end_i + 1]
            a, b, r2, pct_slope, mean_y, _ = fit_model_metrics(y_win)

            if np.isnan(r2):
                continue

            regime = classify_trend(a, r2, r2_min, pct_slope, pct_slope_min)

            if regime != "SIDE":
                # Tendencia válida: preferir la MÁS LARGA (iteramos de corta
                # a larga, así la última válida es la más larga).
                best_seg = SegmentMetrics(
                    symbol=symbol, interval=interval,
                    start_idx=start, end_idx=end_i,
                    length=length, a=a, b=b, r2=r2,
                    pct_slope=pct_slope, mean_price=mean_y,
                    regime=regime,
                    start_time=str(times[start]),
                    end_time=str(times[end_i]),
                    start_price=float(prices[start]),
                    end_price=float(prices[end_i]),
                )

        if best_seg is not None:
            segments.append(best_seg)
            start = best_seg.end_idx + 1
        else:
            # No hay tendencia válida desde aquí: marcar como SIDE mínimo
            side_end = start + min_win - 1
            y_side = prices[start : side_end + 1]
            a, b, r2, pct_slope, mean_y, _ = fit_model_metrics(y_side)
            segments.append(SegmentMetrics(
                symbol=symbol, interval=interval,
                start_idx=start, end_idx=side_end,
                length=min_win, a=a, b=b, r2=r2,
                pct_slope=pct_slope, mean_price=mean_y,
                regime="SIDE",
                start_time=str(times[start]),
                end_time=str(times[side_end]),
                start_price=float(prices[start]),
                end_price=float(prices[side_end]),
            ))
            # Avanzar solo 1 vela para no ocultar tendencias cercanas
            start += 1

    # ── Residuo: marcar velas finales sin cubrir como SIDE ──────────────
    # (se fusionarán con SIDEs previos abajo)

    # ── Consolidar: eliminar solapamientos y fusionar SIDEs ───────────
    # Al avanzar de 1 en 1 para SIDEs, puede haber SIDEs solapados y
    # tendencias que arrancan dentro de un SIDE previo.
    consolidated: List[SegmentMetrics] = []
    covered_up_to = -1  # último índice ya cubierto

    for seg in segments:
        if seg.start_idx <= covered_up_to:
            if seg.regime == "SIDE":
                # SIDE solapado con lo ya cubierto: ignorar
                continue
            else:
                # Tendencia que empieza dentro de un SIDE previo:
                # recortar el SIDE anterior para que termine justo antes.
                if consolidated and consolidated[-1].regime == "SIDE":
                    prev = consolidated[-1]
                    new_side_end = seg.start_idx - 1
                    if new_side_end < prev.start_idx:
                        # El SIDE queda vacío: eliminarlo
                        consolidated.pop()
                    else:
                        y_s = prices[prev.start_idx : new_side_end + 1]
                        a, b, r2, pct_slope, mean_y, _ = fit_model_metrics(y_s)
                        consolidated[-1] = SegmentMetrics(
                            symbol=symbol, interval=interval,
                            start_idx=prev.start_idx, end_idx=new_side_end,
                            length=new_side_end - prev.start_idx + 1,
                            a=a, b=b, r2=r2,
                            pct_slope=pct_slope, mean_price=mean_y,
                            regime="SIDE",
                            start_time=str(times[prev.start_idx]),
                            end_time=str(times[new_side_end]),
                            start_price=float(prices[prev.start_idx]),
                            end_price=float(prices[new_side_end]),
                        )

        # Fusionar SIDEs consecutivos
        if (seg.regime == "SIDE" and consolidated
                and consolidated[-1].regime == "SIDE"
                and seg.start_idx == consolidated[-1].end_idx + 1):
            prev = consolidated[-1]
            new_end = seg.end_idx
            y_m = prices[prev.start_idx : new_end + 1]
            a, b, r2, pct_slope, mean_y, _ = fit_model_metrics(y_m)
            consolidated[-1] = SegmentMetrics(
                symbol=symbol, interval=interval,
                start_idx=prev.start_idx, end_idx=new_end,
                length=new_end - prev.start_idx + 1,
                a=a, b=b, r2=r2,
                pct_slope=pct_slope, mean_price=mean_y,
                regime="SIDE",
                start_time=str(times[prev.start_idx]),
                end_time=str(times[new_end]),
                start_price=float(prices[prev.start_idx]),
                end_price=float(prices[new_end]),
            )
        else:
            consolidated.append(seg)

        covered_up_to = max(covered_up_to, consolidated[-1].end_idx)

    # ── Si quedan velas al final sin cubrir, añadir/extender SIDE ─────
    if consolidated:
        last_covered = consolidated[-1].end_idx
        if last_covered < n - 1:
            tail_start = last_covered + 1
            y_tail = prices[tail_start:]
            a, b, r2, pct_slope, mean_y, _ = fit_model_metrics(y_tail)
            tail_seg = SegmentMetrics(
                symbol=symbol, interval=interval,
                start_idx=tail_start, end_idx=n - 1,
                length=n - tail_start,
                a=a, b=b, r2=r2,
                pct_slope=pct_slope, mean_price=mean_y,
                regime="SIDE",
                start_time=str(times[tail_start]),
                end_time=str(times[n - 1]),
                start_price=float(prices[tail_start]),
                end_price=float(prices[n - 1]),
            )
            # Fusionar con último si también es SIDE
            if consolidated[-1].regime == "SIDE":
                prev = consolidated[-1]
                y_m = prices[prev.start_idx : n]
                a, b, r2, pct_slope, mean_y, _ = fit_model_metrics(y_m)
                consolidated[-1] = SegmentMetrics(
                    symbol=symbol, interval=interval,
                    start_idx=prev.start_idx, end_idx=n - 1,
                    length=n - prev.start_idx,
                    a=a, b=b, r2=r2,
                    pct_slope=pct_slope, mean_price=mean_y,
                    regime="SIDE",
                    start_time=str(times[prev.start_idx]),
                    end_time=str(times[n - 1]),
                    start_price=float(prices[prev.start_idx]),
                    end_price=float(prices[n - 1]),
                )
            else:
                consolidated.append(tail_seg)

    # ── Garantizar que ningún segmento tenga < min_win velas ────────────
    # SIDEs cortos se absorben en el segmento adyacente, manteniendo
    # el régimen recalculado (no se fuerza el del vecino).
    final: List[SegmentMetrics] = []
    for seg in consolidated:
        if seg.length < min_win and seg.regime == "SIDE" and final:
            # Absorber en el segmento anterior
            prev = final[-1]
            new_end = seg.end_idx
            y_m = prices[prev.start_idx : new_end + 1]
            a, b, r2, pct_slope, mean_y, _ = fit_model_metrics(y_m)
            regime = classify_trend(a, r2, r2_min, pct_slope, pct_slope_min)
            final[-1] = SegmentMetrics(
                symbol=symbol, interval=interval,
                start_idx=prev.start_idx, end_idx=new_end,
                length=new_end - prev.start_idx + 1,
                a=a, b=b, r2=r2,
                pct_slope=pct_slope, mean_price=mean_y,
                regime=regime,
                start_time=str(times[prev.start_idx]),
                end_time=str(times[new_end]),
                start_price=float(prices[prev.start_idx]),
                end_price=float(prices[new_end]),
            )
        else:
            final.append(seg)

    return final

# ──────────────────────────────────────────────────────────────────────────── #
#  Bloque principal: descarga, análisis y gráfico
# ──────────────────────────────────────────────────────────────────────────── #

if __name__ == "__main__":

    # ── Descarga de datos ─────────────────────────────────────────────────
    params = ask_candles_params()
    data = get_klines(params)

    timestamp_ms = data[0][0]
    date_utc = timestamp_to_utc(timestamp_ms)
    print("Fecha de apertura de la primera vela:", date_utc)

    # ── Limpiar y preparar datos ────────────────────────────────────────────────────────
    cleaned_data = [candles_to_dict(kline) for kline in data]
    print(json.dumps(cleaned_data[-1], indent=3, default=str))

    X = [k["close_time"] for k in cleaned_data]
    prices = [k["close_price"] for k in cleaned_data]

    # ── Parámetros ────────────────────────────────────────────────────────
    WINDOW = 10
    MIN_WIN = 5
    MIN_R2 = 0.65
    PCT_SLOPE_MIN = 0.05

    # ── Preparación ───────────────────────────────────────────────────────
    float_prices = np.array([float(p) for p in prices], dtype=float)
    times = pd.to_datetime(X, utc=True)

    # ── Detección de TODAS las tendencias ─────────────────────────────────
    symbol = params["symbol"]
    interval = params["interval"]
    trends = find_all_trends(float_prices, times, symbol, interval, WINDOW, MIN_WIN, MIN_R2, PCT_SLOPE_MIN)

    print(f"\nTotal de velas: {len(float_prices)}")
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

    # ── Gráfico ───────────────────────────────────────────────────────────
    color_map = {"UP": "green", "DOWN": "red", "SIDE": "gray"}

    fig, ax = plt.subplots(figsize=(14, 6))

    # Serie completa de precios
    ax.plot(times, float_prices, marker="o", ms=3, color="steelblue", linewidth=1, label="Close price", zorder=2)

    # Graficar cada tendencia
    for i, seg in enumerate(trends, 1):
        c = color_map[seg.regime]

        # Zona sombreada
        ax.axvspan(times[seg.start_idx], times[seg.end_idx],
                   color=c, alpha=0.10, zorder=1)

        # Recta y = a·x + b sobre la subventana
        x_seg = np.arange(seg.length, dtype=float)
        y_seg = seg.a * x_seg + seg.b
        ax.plot(times[seg.start_idx : seg.end_idx + 1], y_seg,
                linewidth=2, linestyle="--", color=c, zorder=3,
                label=f"#{i} {seg.regime} L={seg.length} R²={seg.r2:.3f}")

    ax.set_xlabel("Fecha de cierre (UTC)")
    ax.set_ylabel("Precio de cierre (USDT)")
    ax.set_title("BTCUSDT • 4h • Segmentación de tendencias")
    ax.legend(loc="best", fontsize=8, ncol=2)
    ax.grid(True, alpha=0.2)
    fig.autofmt_xdate()
    plt.tight_layout()
    plt.show()