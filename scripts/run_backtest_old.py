import asyncio
import os
import re
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.lines import Line2D

from backtesting.simulator import run_long_backtest
from backtesting.records import BacktestConfig, BacktestResult, StrategySignals
from backtesting.strategies import build_ema_long_signals
from database.database import connectDB, disconnect
from database.repository import get_candles, save_backtest_result
from utils.utils import parse_utc

def _slugify_filename(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(text).strip())
    cleaned = cleaned.strip("_")
    return cleaned or "na"

def _build_pdf_path(result: BacktestResult, params: dict) -> Path:
    out_dir_raw = params.get("pdf_output_dir", "reports/backtests")
    out_dir = Path(out_dir_raw).expanduser()
    if not out_dir.is_absolute():
        out_dir = Path.cwd() / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    custom_filename = (params.get("pdf_filename") or "").strip()
    if custom_filename:
        filename = _slugify_filename(custom_filename)
        if not filename.lower().endswith(".pdf"):
            filename = f"{filename}.pdf"
    else:
        start_label = params["start_time"].strftime("%Y%m%d")
        end_dt = params.get("end_time") or datetime.now(timezone.utc)
        end_label = end_dt.strftime("%Y%m%d")
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = (
            f"{_slugify_filename(params['symbol'])}_"
            f"{_slugify_filename(params['interval'])}_"
            f"{_slugify_filename(result.strategy_name)}_"
            f"{start_label}_to_{end_label}_{ts}.pdf"
        )

    pdf_path = out_dir / filename
    if pdf_path.exists():
        dup_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        pdf_path = out_dir / f"{pdf_path.stem}_{dup_ts}{pdf_path.suffix}"
    return pdf_path

# ══════════════════════════════════════════════════════════════════════════════
#  Input
# ══════════════════════════════════════════════════════════════════════════════
def ask_backtest_params() -> dict:
    symbol          = input("Símbolo (default BTCUSDT): ").strip() or "BTCUSDT"
    interval        = input("Temporalidad (ej: 4h, 1d): ").strip()
    start_str       = input("Start UTC (YYYY-MM-DD HH:MM or YYYY-MM-DD): ").strip()
    end_str         = input("End UTC (opcional): ").strip()
    min_slope_pct   = input("Pendiente mínima EMA10 % (default 0.08): ").strip()
    exit_slope_p    = input("Velas negativas para salir (default 2): ").strip()
    ema_gap_min_str = input("Separación mínima EMA10-EMA55 % (opcional, Enter = 0): ").strip()
    adx_min_str     = input("ADX mínimo para filtrar ruido (opcional, Enter = 0): ").strip()

    adx_min = float(adx_min_str) if adx_min_str else 0.0
    ema_gap_min_pct = float(ema_gap_min_str) if ema_gap_min_str else 0.0
    if adx_min > 0:
        adx_di_str = input("Filtro +DI > -DI en entrada (S/n): ").strip().lower()
        adx_rise_str = input("Filtro ADX no decreciente en entrada (s/N): ").strip().lower()
        adx_require_di = adx_di_str != "n"
        adx_require_rising = adx_rise_str == "s"
    else:
        adx_require_di = False
        adx_require_rising = False

    leverage        = input("Apalancamiento (default 1X): ").strip()
    capital         = input("Capital inicial (default 10000): ").strip()
    pdf_filename    = input("Nombre PDF (opcional, Enter = automático): ").strip()

    # Gestión de riesgo automática (sin pedir SL manual): ATR dinámico por defecto.
    atr_period = 14
    atr_stop_mult = 1.8
    atr_trailing_mult = 2.2
    atr_stop_confirm_on_close = True
    pdf_output_dir = os.getenv("BACKTEST_PDF_DIR", "reports/backtests")

    return {
        "symbol":   symbol,
        "interval": interval,
        "start_time": parse_utc(start_str),
        "end_time":   parse_utc(end_str) if end_str else None,
        "config": BacktestConfig(
            initial_capital=float(capital) if capital else 10_000.0,
            leverage=float(leverage) if leverage else 1.0,
            stop_loss_pct=None,
            take_profit_pct=None,
            breakeven_trigger_pct=None,
            min_slope_pct=float(min_slope_pct) if min_slope_pct else 0.08,
            exit_slope_periods=int(exit_slope_p) if exit_slope_p else 2,
            ema_gap_min_pct=ema_gap_min_pct,
            adx_min=adx_min,
            adx_require_di=adx_require_di,
            adx_require_rising=adx_require_rising,
            atr_period=atr_period,
            atr_stop_mult=atr_stop_mult,
            atr_trailing_mult=atr_trailing_mult,
            atr_stop_confirm_on_close=atr_stop_confirm_on_close,
        ),
        "min_slope_pct":      float(min_slope_pct) if min_slope_pct else 0.08,
        "exit_slope_periods": int(exit_slope_p) if exit_slope_p else 2,
        "ema_gap_min_pct":    ema_gap_min_pct,
        "adx_min":            adx_min,
        "adx_require_di":     adx_require_di,
        "adx_require_rising": adx_require_rising,
        "use_adx":            adx_min > 0.0,
        "use_atr_stop":       True,
        "atr_stop_confirm_on_close": atr_stop_confirm_on_close,
        "pdf_output_dir":     pdf_output_dir,
        "pdf_filename":       pdf_filename,
    }

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
    t    = times[last]

    ema10   = signals.ema_fast[last]
    ema55   = signals.ema_slow[last]
    ema_gap_pct = ((ema10 - ema55) / ema55 * 100) if ema55 else 0.0
    slope   = slope_pct[last]
    price   = closes[last]
    has_adx = signals.adx_values is not None

    adx_val  = float(signals.adx_values[last])  if has_adx else None
    adx_prev = float(signals.adx_values[last - 1]) if has_adx and last > 0 else None
    plus_di  = float(signals.plus_di[last])      if has_adx else None
    minus_di = float(signals.minus_di[last])     if has_adx else None

    entry_signal = bool(signals.entry_long[last])
    exit_signal  = bool(signals.exit_long[last])

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
    slope_s   = "+" if slope >= 0 else ""
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
        print(f"  ▲  SEÑAL DE ENTRADA DETECTADA")
        print(f"     Ejecutar BUY al open de la siguiente vela")
        if has_adx:
            print(f"     ADX={adx_val:.1f}  +DI={plus_di:.1f}  -DI={minus_di:.1f}")
        print(f"     EMA 10={ema10:,.2f}  EMA 55={ema55:,.2f}  Pendiente={slope_s}{slope:.4f}%")

    elif exit_signal:
        print(f"  ▼  SEÑAL DE SALIDA DETECTADA")
        print(f"     Ejecutar SELL al open de la siguiente vela")
        print(f"     EMA 10={ema10:,.2f}  Pendiente={slope_s}{slope:.4f}%  Precio<EMA={price < ema10}")

    else:
        # Sin señal — mostrar qué falta para activarla
        print(f"  ·  Sin señal activa en esta vela")
        print()

        trend_ok  = ema10 > ema55
        gap_ok    = ema_gap_pct >= params["ema_gap_min_pct"]
        slope_ok  = slope >= params["min_slope_pct"]
        above_ok  = price > ema10
        adx_ok    = (adx_val >= params["adx_min"]) if (has_adx and params["adx_min"] > 0) else True
        require_di = params.get("adx_require_di", True)
        require_adx_rising = params.get("adx_require_rising", False)
        di_raw_ok = (plus_di > minus_di) if has_adx else True
        adx_up_raw_ok = ((adx_val >= adx_prev) if adx_prev is not None else True) if has_adx else True
        di_ok = di_raw_ok if require_di else True
        adx_up_ok = adx_up_raw_ok if require_adx_rising else True

        print(f"  Para ENTRADA necesitas:")
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

# ══════════════════════════════════════════════════════════════════════════════
#  Debug de señales — tabla vela a vela
# ══════════════════════════════════════════════════════════════════════════════
def debug_signals(
    times: pd.DatetimeIndex,
    closes: np.ndarray,
    opens: np.ndarray,
    signals,
    slope_pct: np.ndarray,
    result: BacktestResult,
    min_slope_pct: float,
    ema_gap_min_pct: float,
    adx_min: float,
    adx_require_di: bool,
    adx_require_rising: bool,
) -> None:
    has_adx = signals.adx_values is not None
    W = 160 if has_adx else 130

    print()
    print("═" * W)
    print("  DEBUG DE SEÑALES")
    print("═" * W)

    entry_exec = {t.entry_index: t for t in result.trades}
    exit_exec  = {t.exit_index:  t for t in result.trades}

    relevant = set()
    for i, (e, x) in enumerate(zip(signals.entry_long, signals.exit_long)):
        if e or x:
            relevant.update([max(0, i - 1), i, min(len(closes) - 1, i + 1)])
    for idx in list(entry_exec.keys()) + list(exit_exec.keys()):
        relevant.update([max(0, idx - 1), idx, min(len(closes) - 1, idx + 1)])

    if not relevant:
        print("  No hay señales ni trades en el rango.")
        print("═" * W)
        return

    adx_header = f"{'ADX':>7}  {'A≥mn':>5}  {'DI+':>4}  {'ADX↑':>4}  " if has_adx else ""
    print(
        f"  {'idx':>5}  {'Fecha':>16}  {'Close':>10}  "
        f"{'EMA10':>10}  {'EMA55':>10}  {'Gap%':>8}  {'Slope%':>8}  "
        f"{adx_header}"
        f"{'E10>E55':>7}  {'Gp≥mn':>6}  {'Slp≥mn':>6}  {'P>E10':>5}  Evento"
    )
    print("  " + "─" * (W - 2))

    prev_group = -99
    for i in sorted(relevant):
        if i > prev_group + 2:
            print("  " + "·" * (W - 2))
        prev_group = i

        ema10  = signals.ema_fast[i]
        ema55  = signals.ema_slow[i]
        ema_gap = ((ema10 - ema55) / ema55 * 100) if ema55 else 0.0
        slope  = slope_pct[i]
        price  = closes[i]
        fecha  = times[i].strftime("%m-%d %H:%M")

        cross_ok  = ema10 > ema55
        gap_ok    = ema_gap >= ema_gap_min_pct
        slope_ok  = slope >= min_slope_pct
        above_ok  = price > ema10
        cross_s   = "✔" if cross_ok else "✘"
        gap_s     = "✔" if gap_ok else "✘"
        slope_s   = "✔" if slope_ok else "✘"
        above_s   = "✔" if above_ok else "✘"

        adx_col = ""
        if has_adx:
            adx_v   = signals.adx_values[i]
            adx_ok  = adx_v >= adx_min if adx_min > 0 else True
            di_ok = signals.plus_di[i] > signals.minus_di[i]
            adx_up_ok = (adx_v >= signals.adx_values[i - 1]) if i > 0 else False
            adx_col = (
                f"{adx_v:>7.2f}  "
                f"{'✔' if adx_ok else '✘':>5}  "
                f"{'✔' if di_ok else '✘':>4}  "
                f"{'✔' if adx_up_ok else '✘':>4}  "
            )

        eventos = []
        next_open_str = f"open[{i+1}]={opens[i+1]:,.2f}" if (i + 1) < len(opens) else "open[next]=N/A"
        if signals.entry_long[i]:
            conds = f"{cross_s}{gap_s}{slope_s}{above_s}"
            if has_adx:
                adx_v2  = signals.adx_values[i]
                adx_ok2 = adx_v2 >= adx_min if adx_min > 0 else True
                di_ok2 = signals.plus_di[i] > signals.minus_di[i]
                adx_up_ok2 = (adx_v2 >= signals.adx_values[i - 1]) if i > 0 else False
                conds  += "✔" if adx_ok2 else "✘"
                if adx_require_di:
                    conds += "✔" if di_ok2 else "✘"
                if adx_require_rising:
                    conds += "✔" if adx_up_ok2 else "✘"
            eventos.append(f"SEÑAL ENTRADA [{conds}]  → {next_open_str}")
        if signals.exit_long[i]:
            eventos.append(f"SEÑAL SALIDA  → {next_open_str}")
        if i in entry_exec:
            t2 = entry_exec[i]
            eventos.append(f"EXEC ENTRADA  open={t2.entry_price:,.2f}")
        if i in exit_exec:
            t2 = exit_exec[i]
            eventos.append(f"EXEC SALIDA   open={t2.exit_price:,.2f}  ({t2.exit_reason})")

        evento_str = "  |  ".join(eventos) if eventos else ""
        slope_fmt = f"{slope:+.4f}".rjust(8)

        print(
            f"  {i:>5}  {fecha:>16}  {price:>10,.2f}  "
            f"{ema10:>10,.2f}  {ema55:>10,.2f}  {ema_gap:+7.4f}  "
            f"{slope_fmt}  "
            f"{adx_col}"
            f"  {cross_s:>5}    "
            f"  {gap_s}    "
            f"  {slope_s}    "
            f"  {above_s}  "
            f"{evento_str}"
        )

    print("  " + "─" * (W - 2))
    print()
    print("  RESUMEN DE TRADES")
    print("  " + "─" * 65)
    for idx, t in enumerate(result.trades, 1):
        pnl_s = "+" if t.pnl >= 0 else ""
        print(
            f"  Trade #{idx}  "
            f"señal[{t.entry_index - 1}] → exec[{t.entry_index}]  "
            f"señal_exit[{t.exit_index - 1}] → exec[{t.exit_index}]  "
            f"PnL: {pnl_s}${t.pnl:,.2f}  ({t.exit_reason})"
        )
    print("═" * W)
    print()

# ══════════════════════════════════════════════════════════════════════════════
#  Contexto de indicadores por trade (para el print detallado)
# ══════════════════════════════════════════════════════════════════════════════
def build_trade_context(
    result: BacktestResult,
    signals,
    closes: np.ndarray,
    slope_pct: np.ndarray,
    min_slope_pct: float,
    exit_slope_periods: int,
) -> list:
    contexts = []
    has_adx = signals.adx_values is not None

    for trade in result.trades:
        si = trade.entry_index - 1
        xi = max(trade.exit_index - 1, 0)

        adx_entry  = float(signals.adx_values[si])  if has_adx else None
        adx_prev_entry = float(signals.adx_values[si - 1]) if has_adx and si > 0 else None
        pdi_entry  = float(signals.plus_di[si])      if has_adx else None
        mdi_entry  = float(signals.minus_di[si])     if has_adx else None

        neg_streak = 0
        if trade.exit_reason == "signal_exit":
            for j in range(xi, max(xi - exit_slope_periods - 10, -1), -1):
                if j >= 0 and slope_pct[j] <= -min_slope_pct:
                    neg_streak += 1
                else:
                    break

        contexts.append({
            "signal_index_entry": si,
            "signal_index_exit":  xi,
            "ema10_entry":  signals.ema_fast[si],
            "ema55_entry":  signals.ema_slow[si],
            "ema_gap_entry": ((signals.ema_fast[si] - signals.ema_slow[si]) / signals.ema_slow[si] * 100) if signals.ema_slow[si] else 0.0,
            "slope_entry":  slope_pct[si],
            "price_entry":  closes[si],
            "adx_entry":    adx_entry,
            "adx_prev_entry": adx_prev_entry,
            "plus_di_entry": pdi_entry,
            "minus_di_entry": mdi_entry,
            "ema10_exit":   signals.ema_fast[xi],
            "slope_exit":   slope_pct[xi],
            "price_exit":   closes[xi],
            "neg_streak":   neg_streak,
        })

    return contexts

# ══════════════════════════════════════════════════════════════════════════════
#  Print resumen en terminal
# ══════════════════════════════════════════════════════════════════════════════
def _reason_label(reason: str) -> str:
    labels = {
        "take_profit":                 "✔  take_profit",
        "stop_loss":                   "✘  stop_loss",
        "atr_stop_loss":               "✘  atr_stop",
        "atr_trailing_stop":           "✘  atr_trailing",
        "breakeven_stop":              "◈  breakeven",
        "stop_loss_priority_same_bar": "✘  sl_same_bar",
        "signal_exit":                 "↩  signal_exit",
        "end_of_data":                 "⏹  end_of_data",
    }
    return labels.get(reason, reason)


def print_summary(
    result: BacktestResult,
    params: dict,
    trade_contexts: list,
) -> None:
    W    = 80
    SEP  = "─" * W
    SEP2 = "═" * W
    config = params["config"]

    print()
    print(SEP2)
    print(f"  BACKTEST RESULT  ·  {params['symbol']}  ·  {params['interval']}")
    print(SEP2)

    print()
    print(f"  {'Estrategia':<28} {result.strategy_name}")
    start_label = params["start_time"].strftime("%Y-%m-%d")
    end_label   = params["end_time"].strftime("%Y-%m-%d") if params.get("end_time") else "hoy"
    print(f"  {'Rango':<28} {start_label} -> {end_label}")
    print(f"  {'Capital inicial':<28} ${result.initial_capital:>12,.2f}")
    print(f"  {'Apalancamiento':<28} {config.leverage:.1f}x")

    print(f"  {'Stop Loss manual':<28} desactivado")
    print(f"  {'Take Profit manual':<28} desactivado")
    print(f"  {'Breakeven manual':<28} desactivado")
    print(f"  {'Velas para salida':<28} {params['exit_slope_periods']}")
    print(f"  {'Pendiente mínima':<28} {params['min_slope_pct']:.4f}%")
    print(f"  {'Gap EMA mínimo':<28} {params['ema_gap_min_pct']:.4f}%")
    if params["use_adx"]:
        print(f"  {'ADX mínimo':<28} {params['adx_min']:.1f}")
        print(f"  {'Filtro +DI > -DI':<28} {'activo' if params['adx_require_di'] else 'desactivado'}")
        print(f"  {'Filtro ADX creciente':<28} {'activo' if params['adx_require_rising'] else 'desactivado'}")
    else:
        print(f"  {'ADX mínimo':<28} desactivado")
    atr_stop_label = f"ATR x{config.atr_stop_mult:g} (n={config.atr_period})" if config.atr_stop_mult else "desactivado"
    atr_trail_label = f"ATR x{config.atr_trailing_mult:g} (n={config.atr_period})" if config.atr_trailing_mult else "desactivado"
    atr_confirm_label = "cierre de vela" if config.atr_stop_confirm_on_close else "toque intravela"
    print(f"  {'SL dinámico ATR':<28} {atr_stop_label}")
    print(f"  {'Trailing ATR':<28} {atr_trail_label}")
    print(f"  {'Confirmación stop ATR':<28} {atr_confirm_label}")

    print()
    print(SEP)
    print(f"  RENDIMIENTO")
    print()
    capital_delta = result.final_capital - result.initial_capital
    delta_sign    = "+" if capital_delta >= 0 else ""
    ret_sign      = "+" if result.total_return_pct >= 0 else ""
    print(f"  {'Capital final':<28} ${result.final_capital:>12,.2f}")
    print(f"  {'Ganancia neta':<28} {delta_sign}${capital_delta:,.2f}")
    print(f"  {'Retorno total':<28} {ret_sign}{result.total_return_pct:.2f}%")
    print(f"  {'Max Drawdown':<28} {result.max_drawdown_pct:.2f}%")

    print()
    print(SEP)
    print(f"  TRADES")
    print()
    total     = result.total_trades
    wins      = result.winning_trades
    loss      = result.losing_trades
    BAR_LEN   = 20
    win_fill  = round(wins / total * BAR_LEN) if total else 0
    loss_fill = round(loss / total * BAR_LEN) if total else 0
    rest_fill = BAR_LEN - win_fill - loss_fill
    bar       = "[" + ("█" * win_fill) + ("░" * loss_fill) + ("·" * rest_fill) + "]"
    avg_sign  = "+" if result.avg_trade_return_pct >= 0 else ""
    print(f"  {'Total operaciones':<28} {total}")
    print(f"  {'Win / Loss':<28} {wins} / {loss}  {bar}")
    print(f"  {'Win rate':<28} {result.win_rate_pct:.1f}%")
    print(f"  {'Profit Factor':<28} {result.profit_factor:.2f}")
    print(f"  {'Retorno promedio':<28} {avg_sign}{result.avg_trade_return_pct:.2f}%")

    if not result.trades:
        print()
        print(SEP2)
        return

    print()
    print(SEP)
    print(f"  DETALLE DE OPERACIONES")

    for idx, (t, ctx) in enumerate(zip(result.trades, trade_contexts), 1):
        print()
        pnl_sign  = "+" if t.pnl >= 0 else ""
        ret_sign2 = "+" if t.return_pct >= 0 else ""

        print(f"  Trade #{idx}  {_reason_label(t.exit_reason)}")
        print(f"  {'─' * (W - 2)}")
        print(
            f"  Entrada: {t.entry_time.strftime('%Y-%m-%d %H:%M')}   "
            f"Salida: {t.exit_time.strftime('%Y-%m-%d %H:%M')}   "
            f"Velas: {t.candles_held}   "
            f"PnL: {pnl_sign}${t.pnl:,.2f}   "
            f"Ret: {ret_sign2}{t.return_pct:.2f}%"
        )
        print(f"  P.Entrada: {t.entry_price:,.2f}   P.Salida: {t.exit_price:,.2f}")

        # ── Condiciones de ENTRADA ────────────────────────────────────────
        print()
        si = ctx["signal_index_entry"]
        print(f"  ENTRADA — vela de señal #{si} → ejecución al open de vela #{t.entry_index}")

        ema10_e  = ctx["ema10_entry"]
        ema55_e  = ctx["ema55_entry"]
        gap_e    = ctx["ema_gap_entry"]
        slope_e  = ctx["slope_entry"]
        price_e  = ctx["price_entry"]
        cross_ok = ema10_e > ema55_e
        gap_ok   = gap_e >= params["ema_gap_min_pct"]

        cross_sym = "✔" if cross_ok else "✘"
        gap_sym   = "✔" if gap_ok else "✘"
        slope_sym = "✔" if slope_e >= params["min_slope_pct"] else "✘"
        above_sym = "✔" if price_e > ema10_e else "✘"
        cross_rel = ">" if cross_ok else "<"
        above_rel = ">" if price_e > ema10_e else "<"
        slope_e_s = "+" if slope_e >= 0 else ""

        print(f"    {cross_sym}  EMA 10 {cross_rel} EMA 55")
        print(f"         EMA 10 = {ema10_e:>12,.2f}")
        print(f"         EMA 55 = {ema55_e:>12,.2f}")
        print(f"    {gap_sym}  Gap EMA10-EMA55 = {gap_e:+.4f}%"
              f"   (mín requerido: +{params['ema_gap_min_pct']:.4f}%)")
        print(f"    {slope_sym}  Pendiente EMA 10 = {slope_e_s}{slope_e:.4f}%"
              f"   (mín requerido: +{params['min_slope_pct']:.4f}%)")
        print(f"    {above_sym}  Precio {above_rel} EMA 10")
        print(f"         Precio = {price_e:>12,.2f}")
        print(f"         EMA 10 = {ema10_e:>12,.2f}")

        if ctx["adx_entry"] is not None and params["use_adx"]:
            adx_e    = ctx["adx_entry"]
            adx_ok   = adx_e >= params["adx_min"]
            adx_sym  = "✔" if adx_ok else "✘"
            adx_label = (
                "muy fuerte" if adx_e >= 40 else
                "fuerte" if adx_e >= 25 else
                "débil emergente" if adx_e >= 20 else "lateral"
            )
            print(f"    {adx_sym}  ADX = {adx_e:.2f}   (mín requerido: {params['adx_min']:.1f})  [{adx_label}]")
            pdi_e = ctx['plus_di_entry']
            mdi_e = ctx['minus_di_entry']
            di_ok = pdi_e > mdi_e
            if params["adx_require_di"]:
                di_sym = "✔" if di_ok else "✘"
                print(f"    {di_sym}  +DI > -DI")
            print(f"         +DI = {pdi_e:.2f}   -DI = {mdi_e:.2f}")
            if ctx["adx_prev_entry"] is not None:
                adx_prev_e = ctx["adx_prev_entry"]
                adx_up_ok = adx_e >= adx_prev_e
                if params["adx_require_rising"]:
                    adx_up_sym = "✔" if adx_up_ok else "✘"
                    print(f"    {adx_up_sym}  ADX actual >= ADX previo")
                print(f"         ADX prev = {adx_prev_e:.2f}   ADX actual = {adx_e:.2f}")

        # ── Condiciones de SALIDA ─────────────────────────────────────────
        print()
        xi = ctx["signal_index_exit"]
        print(f"  SALIDA — {_reason_label(t.exit_reason)}")

        if t.exit_reason == "signal_exit":
            print(f"  (vela de señal #{xi} → ejecución al open de vela #{t.exit_index})")

            ema10_x  = ctx["ema10_exit"]
            slope_x  = ctx["slope_exit"]
            price_x  = ctx["price_exit"]
            neg_str  = ctx["neg_streak"]
            n        = params["exit_slope_periods"]

            streak_sym = "✔" if neg_str >= n else "✘"
            slope_sym2 = "✔" if slope_x <= -params["min_slope_pct"] else "✘"
            below_sym  = "✔" if price_x < ema10_x else "✘"
            below_rel  = "<" if price_x < ema10_x else ">"
            slope_x_s  = "+" if slope_x >= 0 else ""

            print(f"    {streak_sym}  Pendiente negativa sostenida: {neg_str} velas"
                  f"   (se necesitan {n})")
            print(f"    {slope_sym2}  Pendiente EMA 10 = {slope_x_s}{slope_x:.4f}%"
                  f"   (máx permitido: -{params['min_slope_pct']:.4f}%)")
            print(f"    {below_sym}  Precio {below_rel} EMA 10")
            print(f"         Precio = {price_x:>12,.2f}")
            print(f"         EMA 10 = {ema10_x:>12,.2f}")

        elif t.exit_reason in ("stop_loss", "stop_loss_priority_same_bar"):
            sl_pct = config.stop_loss_pct * 100 if config.stop_loss_pct else 0
            print(f"    ✘  Stop Loss tocado: precio cayó a {t.exit_price:,.2f}")
            print(f"       Stop al {sl_pct:.1f}% bajo entrada  ({t.entry_price:,.2f} → {t.exit_price:,.2f})")

        elif t.exit_reason == "atr_stop_loss":
            print(f"    ✘  Stop dinámico ATR tocado")
            print(f"       Entrada: {t.entry_price:,.2f}   Salida: {t.exit_price:,.2f}")

        elif t.exit_reason == "atr_trailing_stop":
            print(f"    ✘  Trailing ATR tocado (protección de ganancia)")
            print(f"       Entrada: {t.entry_price:,.2f}   Salida: {t.exit_price:,.2f}")

        elif t.exit_reason == "breakeven_stop":
            print(f"    ◈  Precio volvió al precio de entrada (stop en breakeven)")
            print(f"       Entrada: {t.entry_price:,.2f}   Salida: {t.exit_price:,.2f}")

        elif t.exit_reason == "take_profit":
            tp_pct = config.take_profit_pct * 100 if config.take_profit_pct else 0
            print(f"    ✔  Take Profit al {tp_pct:.1f}%")
            print(f"       Entrada: {t.entry_price:,.2f}   Salida: {t.exit_price:,.2f}")

        elif t.exit_reason == "end_of_data":
            print(f"    ⏹  Cierre forzado al final del rango de datos")
            print(f"       Último precio disponible: {t.exit_price:,.2f}")

    print()
    print(SEP2)
    print()


# ══════════════════════════════════════════════════════════════════════════════
#  Gráfico limpio: velas + EMAs + marcadores de trades
# ══════════════════════════════════════════════════════════════════════════════
def plot_backtest(
    times: pd.DatetimeIndex,
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    signals,
    result: BacktestResult,
    params: dict,
) -> None:

    has_adx   = signals.adx_values is not None
    n_subplots = 3 if has_adx else 2
    ratios     = [4, 1.2, 1] if has_adx else [4, 1]

    BULL      = "#26a69a"
    BEAR      = "#ef5350"
    EMA_FAST  = "pink"
    EMA_SLOW  = "orange"
    ENTRY_C   = "#1565c0"
    WIN_C     = "#2e7d32"
    LOSS_C    = "#c62828"
    BE_C      = "#f9a825"
    SL_C      = "#ef9a9a"
    ZONE_WIN  = "#a5d6a7"
    ZONE_LOSS = "#ef9a9a"
    ZONE_BE   = "#fff9c4"
    ADX_C     = "#7b1fa2"   # morado — línea ADX
    ADX_MIN_C = "#e53935"   # rojo punteado — umbral mínimo

    fig = plt.figure(figsize=(22, 12 if has_adx else 10))
    gs  = gridspec.GridSpec(n_subplots, 1, height_ratios=ratios, hspace=0.06)

    ax_price  = fig.add_subplot(gs[0])
    ax_equity = fig.add_subplot(gs[1], sharex=ax_price)
    ax_adx    = fig.add_subplot(gs[2], sharex=ax_price) if has_adx else None

    for ax in ([ax_price, ax_equity] + ([ax_adx] if ax_adx else [])):
        ax.set_facecolor("white")
        ax.grid(True, alpha=0.25, color="gray", linewidth=0.5)

    # ── Velas ────────────────────────────────────────────────────────────
    candle_width = (times[1] - times[0]) * 0.6 if len(times) > 1 else pd.Timedelta(hours=4)
    bull_mask    = closes >= opens
    bear_mask    = ~bull_mask

    ax_price.bar(
        times[bull_mask], closes[bull_mask] - opens[bull_mask],
        bottom=opens[bull_mask], width=candle_width,
        color=BULL, edgecolor=BULL, zorder=3,
    )
    ax_price.bar(
        times[bear_mask], closes[bear_mask] - opens[bear_mask],
        bottom=opens[bear_mask], width=candle_width,
        color=BEAR, edgecolor=BEAR, zorder=3,
    )
    ax_price.vlines(times[bull_mask], lows[bull_mask], highs[bull_mask],
                    color=BULL, linewidth=0.9, zorder=2)
    ax_price.vlines(times[bear_mask], lows[bear_mask], highs[bear_mask],
                    color=BEAR, linewidth=0.9, zorder=2)

    # ── Índice de vela dentro del cuerpo (debug visual sutil) ──────────
    # Se dibuja pequeño y con color cercano al de la vela para no distraer.
    price_span = max(highs.max() - lows.min(), 1e-9)
    min_body_h = price_span * 0.0012
    text_color_bull = "#0f766e"
    text_color_bear = "#b71c1c"

    for i in range(len(times)):
        o = opens[i]
        c = closes[i]
        body_low = min(o, c)
        body_high = max(o, c)
        body_h = body_high - body_low

        # Si la vela es casi doji, damos una altura mínima visual para centrar texto.
        center_y = body_low + (max(body_h, min_body_h) / 2)
        txt_color = text_color_bull if c >= o else text_color_bear
        idx_text = str(i)
        digits = len(idx_text)
        if digits == 1:
            idx_font = 5.0
        elif digits == 2:
            idx_font = 3.6
        else:
            idx_font = 3.0

        ax_price.text(
            times[i],
            center_y,
            idx_text,
            ha="center",
            va="center",
            fontsize=idx_font,
            color=txt_color,
            alpha=0.75,
            zorder=4,
            clip_on=True,
        )

    # ── EMAs ─────────────────────────────────────────────────────────────
    ax_price.plot(times, signals.ema_fast, color=EMA_FAST,
                  linewidth=1.6, label="EMA 10", zorder=4)
    ax_price.plot(times, signals.ema_slow, color=EMA_SLOW,
                  linewidth=1.6, label="EMA 55", zorder=4)

    # ── Trades ───────────────────────────────────────────────────────────
    price_range  = highs.max() - lows.min()
    arrow_offset = price_range * 0.016

    for trade in result.trades:
        t_entry = times[trade.entry_index]
        t_exit  = times[trade.exit_index]

        if trade.exit_reason == "take_profit" or trade.pnl > 0:
            zone_c = ZONE_WIN
            exit_c = WIN_C
        elif trade.exit_reason == "breakeven_stop":
            zone_c = ZONE_BE
            exit_c = BE_C
        else:
            zone_c = ZONE_LOSS
            exit_c = LOSS_C

        ax_price.axvspan(t_entry, t_exit, color=zone_c, alpha=0.35, zorder=1)

        if trade.exit_reason in ("stop_loss", "breakeven_stop", "stop_loss_priority_same_bar"):
            ax_price.hlines(
                trade.exit_price,
                xmin=t_entry, xmax=t_exit,
                colors=SL_C, linewidths=1.0, linestyles="--", zorder=5,
            )

        entry_y = lows[trade.entry_index] - arrow_offset * 0.8
        ax_price.plot(t_entry, entry_y, marker="^", color=ENTRY_C, markersize=10, zorder=6)

        exit_y = highs[trade.exit_index] + arrow_offset * 0.8
        ax_price.plot(t_exit, exit_y, marker="v", color=exit_c, markersize=10, zorder=6)

    # ── Leyenda ──────────────────────────────────────────────────────────
    legend_handles = [
        Line2D([0], [0], color=EMA_FAST, linewidth=1.6, label="EMA 10"),
        Line2D([0], [0], color=EMA_SLOW, linewidth=1.6, label="EMA 55"),
        Line2D([0], [0], marker="^", color=ENTRY_C, linestyle="None",
               markersize=9, label="Entrada (BUY)"),
        Line2D([0], [0], marker="v", color=WIN_C, linestyle="None",
               markersize=9, label="Salida ganadora"),
        Line2D([0], [0], marker="v", color=LOSS_C, linestyle="None",
               markersize=9, label="Salida perdedora"),
        Line2D([0], [0], marker="v", color=BE_C, linestyle="None",
               markersize=9, label="Breakeven"),
    ]
    ax_price.legend(handles=legend_handles, loc="upper left", fontsize=8, framealpha=0.9)

    ret_sign = "+" if result.total_return_pct >= 0 else ""
    title = (
        f"{params['symbol']}  ·  {params['interval']}  ·  {result.strategy_name}  ·  "
        f"Trades: {result.total_trades}  ·  "
        f"Win rate: {result.win_rate_pct:.1f}%  ·  "
        f"Retorno: {ret_sign}{result.total_return_pct:.2f}%"
    )
    ax_price.set_title(title, fontsize=10, pad=8)
    ax_price.set_ylabel("Precio (USDT)", fontsize=9)
    plt.setp(ax_price.get_xticklabels(), visible=False)

    # ── Curva de equity ───────────────────────────────────────────────────
    eq_times  = [times[0]]
    eq_values = [result.initial_capital]
    for trade in result.trades:
        eq_times.append(times[trade.exit_index])
        eq_values.append(trade.equity_after)

    eq_color = WIN_C if eq_values[-1] >= eq_values[0] else LOSS_C
    ax_equity.plot(eq_times, eq_values, color=eq_color, linewidth=1.5, zorder=3)
    ax_equity.fill_between(
        eq_times, eq_values, result.initial_capital,
        where=[v >= result.initial_capital for v in eq_values],
        color=WIN_C, alpha=0.2, zorder=2,
    )
    ax_equity.fill_between(
        eq_times, eq_values, result.initial_capital,
        where=[v < result.initial_capital for v in eq_values],
        color=LOSS_C, alpha=0.2, zorder=2,
    )
    ax_equity.axhline(result.initial_capital, color="gray",
                      linewidth=0.8, linestyle="--")
    ax_equity.set_ylabel("Equity", fontsize=9)
    ax_equity.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: f"${x:,.0f}")
    )

    if ax_adx:
        plt.setp(ax_equity.get_xticklabels(), visible=False)
        ax_adx.plot(times, signals.adx_values, color=ADX_C,
                    linewidth=1.4, label="ADX", zorder=3)
        if params["adx_min"] > 0:
            ax_adx.axhline(params["adx_min"], color=ADX_MIN_C,
                           linewidth=1.0, linestyle="--", alpha=0.8,
                           label=f"Mín ADX ({params['adx_min']:.0f})")
        ax_adx.set_ylabel("ADX", fontsize=9)
        ax_adx.set_xlabel("Fecha (UTC)", fontsize=9)
        ax_adx.legend(loc="upper left", fontsize=8, framealpha=0.9)
    else:
        ax_equity.set_xlabel("Fecha (UTC)", fontsize=9)

    fig.autofmt_xdate(rotation=30, ha="right")
    plt.tight_layout()

    try:
        pdf_path = _build_pdf_path(result, params)
        fig.savefig(pdf_path, format="pdf", bbox_inches="tight")
        result.report_pdf_filename = pdf_path.name
        print(f"  PDF guardado: {pdf_path}")
    except Exception as exc:
        result.report_pdf_filename = None
        print(f"  Aviso: no se pudo guardar PDF ({exc})")

    try:
        manager = plt.get_current_fig_manager()
        manager.window.showMaximized()
    except Exception:
        pass

    plt.show()

# ══════════════════════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════════════════════
async def main() -> None:
    params = ask_backtest_params()

    print("\nConectando a MongoDB...")
    await connectDB()

    try:
        candles = await get_candles(
            symbol=params["symbol"],
            interval=params["interval"],
            start_time=params["start_time"],
            end_time=params["end_time"],
        )

        if not candles:
            print("No hay candles en MongoDB para ese rango.")
            print("Ejecuta primero: python -m scripts.save_analysis")
            return

        start_date = candles[0].open_time.strftime("%Y-%m-%d")
        end_date   = candles[-1].close_time.strftime("%Y-%m-%d")
        print(f"  {len(candles)} velas cargadas  [{start_date} -> {end_date}]")

        times  = pd.to_datetime([c.close_time for c in candles], utc=True)
        opens  = np.array([float(c.open_price)  for c in candles], dtype=float)
        highs  = np.array([float(c.high_price)  for c in candles], dtype=float)
        lows   = np.array([float(c.low_price)   for c in candles], dtype=float)
        closes = np.array([float(c.close_price) for c in candles], dtype=float)

        print("  Generando señales...")
        signals = build_ema_long_signals(
            prices=closes,
            highs=highs,
            lows=lows,
            fast_span=10,
            slow_span=55,
            min_slope_pct=params["min_slope_pct"],
            exit_slope_periods=params["exit_slope_periods"],
            ema_gap_min_pct=params["ema_gap_min_pct"],
            adx_min=params["adx_min"],
            adx_period=14,
            require_di_confirmation=params["adx_require_di"],
            require_adx_rising=params["adx_require_rising"],
        )

        base_entries = int(signals.entry_base_long.sum()) if signals.entry_base_long is not None else int(signals.entry_long.sum())
        filtered_entries = int(signals.entry_long.sum())
        print(f"  Entradas base EMA: {base_entries}   Entradas filtradas: {filtered_entries}   Salidas: {signals.exit_long.sum()}")
        if signals.active_filters:
            print(f"  Filtros activos: {', '.join(signals.active_filters)}")
        else:
            print("  Filtros activos: ninguno")

        from indicators.emas import ema_pct_slope
        slope_pct = ema_pct_slope(signals.ema_fast)

        # Alertas de la última vela (simulación bot en tiempo real)
        check_alerts(times, closes, signals, slope_pct, params)

        print("  Ejecutando backtest...")
        result = run_long_backtest(
            times=times, opens=opens, highs=highs, lows=lows, closes=closes,
            entry_signals=signals.entry_long,
            exit_signals=signals.exit_long,
            config=params["config"],
            strategy_name=signals.name,
            symbol=params["symbol"],
            interval=params["interval"],
        )

        trade_contexts = build_trade_context(
            result=result,
            signals=signals,
            closes=closes,
            slope_pct=slope_pct,
            min_slope_pct=params["min_slope_pct"],
            exit_slope_periods=params["exit_slope_periods"],
        )

        # Debug de señales
        debug_signals(
            times=times,
            closes=closes,
            opens=opens,
            signals=signals,
            slope_pct=slope_pct,
            result=result,
            min_slope_pct=params["min_slope_pct"],
            ema_gap_min_pct=params["ema_gap_min_pct"],
            adx_min=params["adx_min"],
            adx_require_di=params["adx_require_di"],
            adx_require_rising=params["adx_require_rising"],
        )

        print_summary(result, params, trade_contexts)
        plot_backtest(times, opens, highs, lows, closes, signals, result, params)

        backtest_id = await save_backtest_result(result)
        print(f"  Guardado en MongoDB  [_id: {backtest_id}]")
        if result.report_pdf_filename:
            print(f"  PDF en registro MongoDB: {result.report_pdf_filename}")
        print()

    finally:
        await disconnect()

if __name__ == "__main__":
    asyncio.run(main())