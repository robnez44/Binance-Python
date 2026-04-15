import numpy as np
import pandas as pd

from backtesting.records import StrategySignals

# ══════════════════════════════════════════════════════════════════════════════
#  Sistema de alertas — simula el comportamiento del bot en tiempo real
# ══════════════════════════════════════════════════════════════════════════════
def check_alerts(
    times: pd.DatetimeIndex,
    closes: np.ndarray,
    signals: StrategySignals,
    slope_pct: np.ndarray,
    params: dict,
) -> None:
    """
    Evalúa la última vela disponible y emite alertas si hay señales activas.

    Simula lo que haría el bot en tiempo real al cierre de cada vela:
      - Alerta de ENTRADA si se detecta señal de compra
      - Alerta de SALIDA si se detecta señal de venta
      - Estado actual de los indicadores para la última vela

    En producción, este bloque se ejecutaría cada vez que cierra una vela
    (via websocket de Binance o polling periódico).
    """
    W = 72
    last = len(closes) - 1
    t = times[last]

    ema10 = signals.ema_fast[last]
    ema55 = signals.ema_slow[last]
    ema_gap_pct = ((ema10 - ema55) / ema55 * 100) if ema55 else 0.0
    slope = slope_pct[last]
    price = closes[last]
    has_adx = signals.adx_values is not None

    adx_val = float(signals.adx_values[last]) if has_adx else None
    adx_prev = float(signals.adx_values[last - 1]) if has_adx and last > 0 else None
    plus_di = float(signals.plus_di[last]) if has_adx else None
    minus_di = float(signals.minus_di[last]) if has_adx else None

    entry_signal = bool(signals.entry_long[last])
    exit_signal = bool(signals.exit_long[last])

    print()
    print("═" * W)
    print(f"  ALERTAS  ·  {params['symbol']}  ·  {params['interval']}")
    print(f"  Última vela: {t.strftime('%Y-%m-%d %H:%M UTC')}")
    print("═" * W)

    # ── Estado de indicadores ─────────────────────────────────────────────
    print()
    print(f"  {'INDICADORES':}")
    print(f"  {'─' * (W - 2)}")

    cross_rel = ">" if ema10 > ema55 else "<"
    slope_s = "+" if slope >= 0 else ""
    print(f"  {'Precio':<20} {price:>12,.2f}")
    print(f"  {'EMA 10':<20} {ema10:>12,.2f}   ({cross_rel} EMA 55 = {ema55:,.2f})")
    print(f"  {'Gap EMA10-55':<20} {ema_gap_pct:>+8.4f}%   (mín: {params['ema_gap_min_pct']:.4f}%)")
    print(f"  {'Pendiente EMA 10':<20} {slope_s}{slope:.4f}%   (mín: {params['min_slope_pct']:.4f}%)")
    if signals.filter_total_count is not None and signals.filter_pass_count is not None:
        total_filters = int(signals.filter_total_count[last])
        passed_filters = int(signals.filter_pass_count[last])
        if total_filters > 0:
            print(f"  {'Filtros (pasan)':<20} {passed_filters}/{total_filters}")

    if has_adx:
        require_di = params.get("adx_require_di", True)
        require_adx_rising = params.get("adx_require_rising", False)
        adx_label = (
            "muy fuerte" if adx_val >= 40
            else "fuerte" if adx_val >= 25
            else "débil emergente" if adx_val >= 20
            else "lateral"
        )
        adx_ok = adx_val >= params["adx_min"] if params["adx_min"] > 0 else True
        di_raw_ok = plus_di > minus_di
        adx_up_raw_ok = (adx_val >= adx_prev) if adx_prev is not None else True
        di_ok = di_raw_ok if require_di else True
        adx_up_ok = adx_up_raw_ok if require_adx_rising else True
        adx_sym = "✔" if adx_ok else "✘"
        di_sym = "✔" if di_raw_ok else "✘"
        adx_up_sym = "✔" if adx_up_raw_ok else "✘"
        di_req = "ON" if require_di else "OFF"
        adx_up_req = "ON" if require_adx_rising else "OFF"
        print(f"  {'ADX':<20} {adx_val:>8.2f}   {adx_sym} {adx_label}")
        print(f"  {'+DI / -DI':<20} {plus_di:>8.2f} / {minus_di:>8.2f}   {di_sym} +DI > -DI (filtro {di_req})")
        if adx_prev is not None:
            print(f"  {'ADX momentum':<20} {adx_prev:>8.2f} -> {adx_val:>8.2f}   {adx_up_sym} ADX no decreciente (filtro {adx_up_req})")

    # ── Señal activa ──────────────────────────────────────────────────────
    print()
    if entry_signal:
        print("  ▲  SEÑAL DE ENTRADA DETECTADA")
        print("     Ejecutar BUY al open de la siguiente vela")
        if has_adx:
            print(f"     ADX={adx_val:.1f}  +DI={plus_di:.1f}  -DI={minus_di:.1f}")
        print(f"     EMA 10={ema10:,.2f}  EMA 55={ema55:,.2f}  Pendiente={slope_s}{slope:.4f}%")

    elif exit_signal:
        print("  ▼  SEÑAL DE SALIDA DETECTADA")
        print("     Ejecutar SELL al open de la siguiente vela")
        print(f"     EMA 10={ema10:,.2f}  Pendiente={slope_s}{slope:.4f}%  Precio<EMA={price < ema10}")

    else:
        # Sin señal — mostrar qué falta para activarla
        print("  ·  Sin señal activa en esta vela")
        print()

        trend_ok = ema10 > ema55
        gap_ok = ema_gap_pct >= params["ema_gap_min_pct"]
        slope_ok = slope >= params["min_slope_pct"]
        above_ok = price > ema10
        adx_ok = (adx_val >= params["adx_min"]) if (has_adx and params["adx_min"] > 0) else True
        require_di = params.get("adx_require_di", True)
        require_adx_rising = params.get("adx_require_rising", False)
        di_raw_ok = (plus_di > minus_di) if has_adx else True
        adx_up_raw_ok = ((adx_val >= adx_prev) if adx_prev is not None else True) if has_adx else True
        di_ok = di_raw_ok if require_di else True
        adx_up_ok = adx_up_raw_ok if require_adx_rising else True

        print("  Para ENTRADA necesitas:")
        trend_sym = "✔" if trend_ok else "✘"
        print(f"    {trend_sym}  EMA 10 > EMA 55  (régimen alcista)")
        gap_sym = "✔" if gap_ok else "✘"
        print(f"    {gap_sym}  Gap EMA10-EMA55 >= {params['ema_gap_min_pct']:.4f}%  (actual: {ema_gap_pct:+.4f}%)")
        slope_sym = "✔" if slope_ok else "✘"
        print(f"    {slope_sym}  Pendiente >= {params['min_slope_pct']:.4f}%  (actual: {slope_s}{slope:.4f}%)")
        above_sym = "✔" if above_ok else "✘"
        print(f"    {above_sym}  Precio > EMA 10  (precio={price:,.2f}  ema10={ema10:,.2f})")
        if has_adx and params["adx_min"] > 0:
            adx_sym2 = "✔" if adx_ok else "✘"
            print(f"    {adx_sym2}  ADX >= {params['adx_min']:.1f}  (actual: {adx_val:.2f})")
            if require_di:
                di_sym2 = "✔" if di_ok else "✘"
                print(f"    {di_sym2}  +DI > -DI  (+DI={plus_di:.2f}  -DI={minus_di:.2f})")
            if adx_prev is not None:
                if require_adx_rising:
                    adx_up_sym2 = "✔" if adx_up_ok else "✘"
                    print(f"    {adx_up_sym2}  ADX actual >= ADX previo  ({adx_val:.2f} vs {adx_prev:.2f})")

    print()
    print("═" * W)
    print()
