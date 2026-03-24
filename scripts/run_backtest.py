import asyncio
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.lines import Line2D

from backtesting.simulator import run_long_backtest
from backtesting.records import BacktestConfig, BacktestResult
from backtesting.strategies import ema_vertical_cross_long_strategy
from database.database import connectDB, disconnect
from database.repository import get_candles, save_backtest_result
from utils.utils import parse_utc

# ══════════════════════════════════════════════════════════════════════════════
#  Input
# ══════════════════════════════════════════════════════════════════════════════
def ask_backtest_params() -> dict:
    symbol          = input("Símbolo (default BTCUSDT): ").strip() or "BTCUSDT"
    interval        = input("Temporalidad (ej: 4h, 1d): ").strip()
    start_str       = input("Start UTC (YYYY-MM-DD HH:MM or YYYY-MM-DD): ").strip()
    end_str         = input("End UTC (opcional): ").strip()
    stop_loss_pct   = input("Stop Loss % (opcional, Enter = desactivado): ").strip()
    take_profit_pct = input("Take Profit % (opcional, Enter = desactivado): ").strip()
    breakeven_pct   = input("Breakeven % (opcional, Enter = desactivado): ").strip()
    min_slope_pct   = input("Pendiente mínima EMA10 % (default 0.08): ").strip()
    exit_slope_p    = input("Velas negativas para salir (default 2): ").strip()
    leverage        = input("Apalancamiento (default 1X): ").strip()
    capital         = input("Capital inicial (default 10000): ").strip()

    return {
        "symbol":   symbol,
        "interval": interval,
        "start_time": parse_utc(start_str),
        "end_time":   parse_utc(end_str) if end_str else None,
        "config": BacktestConfig(
            initial_capital=float(capital) if capital else 10_000.0,
            leverage=float(leverage) if leverage else 1.0,
            stop_loss_pct=(float(stop_loss_pct) / 100) if stop_loss_pct else None,
            take_profit_pct=(float(take_profit_pct) / 100) if take_profit_pct else None,
            breakeven_trigger_pct=(float(breakeven_pct) / 100) if breakeven_pct else None,
            min_slope_pct=float(min_slope_pct) if min_slope_pct else 0.08,
            exit_slope_periods=int(exit_slope_p) if exit_slope_p else 2,
        ),
        "min_slope_pct":      float(min_slope_pct) if min_slope_pct else 0.08,
        "exit_slope_periods": int(exit_slope_p) if exit_slope_p else 2,
    }

# ══════════════════════════════════════════════════════════════════════════════
#  Debug de señales — imprime tabla detallada vela a vela
# ══════════════════════════════════════════════════════════════════════════════
def debug_signals(
    times: pd.DatetimeIndex,
    closes: np.ndarray,
    opens: np.ndarray,
    signals,
    slope_pct: np.ndarray,
    result: BacktestResult,
    min_slope_pct: float,
) -> None:
    """
    Imprime una tabla con todas las velas donde:
      - Hay señal de entrada (entry_long = True)
      - O hay señal de salida (exit_long = True)
      - O hay un trade ejecutado (entrada o salida)

    Para cada vela muestra:
      - índice y fecha
      - EMA 10, EMA 55, pendiente, precio de cierre
      - si las condiciones de entrada se cumplen individualmente
      - si es señal o ejecución
    """
    W = 110
    print()
    print("═" * W)
    print("  DEBUG DE SEÑALES")
    print("═" * W)

    # Índices de ejecución real de trades (para marcarlos)
    entry_exec = {t.entry_index: t for t in result.trades}
    exit_exec  = {t.exit_index:  t for t in result.trades}

    # Recopilar índices relevantes: señales + ejecuciones + velas adyacentes
    relevant = set()
    for i, (e, x) in enumerate(zip(signals.entry_long, signals.exit_long)):
        if e or x:
            # Añadir también la vela anterior y la siguiente para contexto
            relevant.update([max(0, i - 1), i, min(len(closes) - 1, i + 1)])
    for idx in list(entry_exec.keys()) + list(exit_exec.keys()):
        relevant.update([max(0, idx - 1), idx, min(len(closes) - 1, idx + 1)])

    if not relevant:
        print("  No hay señales ni trades en el rango.")
        print("═" * W)
        return

    # Cabecera de la tabla
    print(
        f"  {'idx':>5}  "
        f"{'Fecha':>16}  "
        f"{'Close':>10}  "
        f"{'EMA10':>10}  "
        f"{'EMA55':>10}  "
        f"{'Slope%':>8}  "
        f"{'10>55':>5}  "
        f"{'Slp≥mn':>6}  "
        f"{'P>E10':>5}  "
        f"{'Evento'}"
    )
    print("  " + "─" * (W - 2))

    prev_group = -99
    for i in sorted(relevant):
        # Separador si hay salto entre grupos de velas
        if i > prev_group + 2:
            print("  " + "·" * (W - 2))
        prev_group = i

        ema10  = signals.ema_fast[i]
        ema55  = signals.ema_slow[i]
        slope  = slope_pct[i]
        price  = closes[i]
        fecha  = times[i].strftime("%m-%d %H:%M")

        cross_ok  = ema10 > ema55
        slope_ok  = slope >= min_slope_pct
        above_ok  = price > ema10

        cross_s = "✔" if cross_ok else "✘"
        slope_s = "✔" if slope_ok else "✘"
        above_s = "✔" if above_ok else "✘"

        # Determinar qué tipo de evento es esta vela
        eventos = []
        if signals.entry_long[i]:
            conds = "✔✔✔" if (cross_ok and slope_ok and above_ok) else f"{cross_s}{slope_s}{above_s}"
            eventos.append(f"SEÑAL ENTRADA [{conds}]  → ejecuta al open[{i+1}]={opens[i+1]:,.2f}")
        if signals.exit_long[i]:
            eventos.append(f"SEÑAL SALIDA  → ejecuta al open[{i+1}]={opens[i+1]:,.2f}")
        if i in entry_exec:
            t = entry_exec[i]
            eventos.append(f"EJECUCION ENTRADA  open={t.entry_price:,.2f}")
        if i in exit_exec:
            t = exit_exec[i]
            eventos.append(f"EJECUCION SALIDA   open={t.exit_price:,.2f}  ({t.exit_reason})")

        evento_str = "  |  ".join(eventos) if eventos else ""

        slope_sign = "+" if slope >= 0 else ""
        print(
            f"  {i:>5}  "
            f"{fecha:>16}  "
            f"{price:>10,.2f}  "
            f"{ema10:>10,.2f}  "
            f"{ema55:>10,.2f}  "
            f"{slope_sign}{slope:>7.4f}  "
            f"  {cross_s}    "
            f"  {slope_s}    "
            f"  {above_s}  "
            f"{evento_str}"
        )

    print("  " + "─" * (W - 2))
    print()

    # Resumen compacto de trades
    print("  RESUMEN DE TRADES")
    print("  " + "─" * 60)
    for idx, t in enumerate(result.trades, 1):
        pnl_s = "+" if t.pnl >= 0 else ""
        print(
            f"  Trade #{idx}  "
            f"señal[{t.entry_index - 1}] → exec_entry[{t.entry_index}]  "
            f"señal_exit[{t.exit_index - 1}] → exec_exit[{t.exit_index}]  "
            f"PnL: {pnl_s}${t.pnl:,.2f}  ({t.exit_reason})"
        )
    print("═" * W)
    print()

# ══════════════════════════════════════════════════════════════════════════════
#  Contexto de indicadores por trade
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

    for trade in result.trades:
        si = trade.entry_index - 1
        xi = max(trade.exit_index - 1, 0)

        ema10_entry = signals.ema_fast[si]
        ema55_entry = signals.ema_slow[si]
        slope_entry = slope_pct[si]
        price_entry = closes[si]

        ema10_exit  = signals.ema_fast[xi]
        slope_exit  = slope_pct[xi]
        price_exit  = closes[xi]

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
            "ema10_entry":  ema10_entry,
            "ema55_entry":  ema55_entry,
            "slope_entry":  slope_entry,
            "price_entry":  price_entry,
            "ema10_exit":   ema10_exit,
            "slope_exit":   slope_exit,
            "price_exit":   price_exit,
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

    sl_label = (str(round(config.stop_loss_pct * 100, 4)) + "%") if config.stop_loss_pct else "desactivado"
    tp_label = (str(round(config.take_profit_pct * 100, 4)) + "%") if config.take_profit_pct else "desactivado"
    be_label = (str(round(config.breakeven_trigger_pct * 100, 4)) + "%") if config.breakeven_trigger_pct else "desactivado"
    print(f"  {'Stop Loss':<28} {sl_label}")
    print(f"  {'Take Profit':<28} {tp_label}")
    print(f"  {'Breakeven trigger':<28} {be_label}")
    print(f"  {'Velas para salida':<28} {params['exit_slope_periods']}")
    print(f"  {'Pendiente mínima':<28} {params['min_slope_pct']:.4f}%")

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

        print()
        si_label = ctx["signal_index_entry"]
        print(f"  ENTRADA — vela de señal #{si_label} → ejecución al open de vela #{t.entry_index}")

        ema10_e  = ctx["ema10_entry"]
        ema55_e  = ctx["ema55_entry"]
        slope_e  = ctx["slope_entry"]
        price_e  = ctx["price_entry"]
        cross_ok = ema10_e > ema55_e

        cross_sym = "✔" if cross_ok else "✘"
        slope_sym = "✔" if slope_e >= params["min_slope_pct"] else "✘"
        above_sym = "✔" if price_e > ema10_e else "✘"
        cross_rel = ">" if cross_ok else "<"
        above_rel = ">" if price_e > ema10_e else "<"
        slope_e_s = "+" if slope_e >= 0 else ""

        print(f"    {cross_sym}  EMA 10 {cross_rel} EMA 55")
        print(f"         EMA 10 = {ema10_e:>12,.2f}")
        print(f"         EMA 55 = {ema55_e:>12,.2f}")
        print(f"    {slope_sym}  Pendiente EMA 10 = {slope_e_s}{slope_e:.4f}%"
              f"   (mín requerido: +{params['min_slope_pct']:.4f}%)")
        print(f"    {above_sym}  Precio {above_rel} EMA 10")
        print(f"         Precio = {price_e:>12,.2f}")
        print(f"         EMA 10 = {ema10_e:>12,.2f}")

        print()
        xi_label = ctx["signal_index_exit"]
        print(f"  SALIDA — {_reason_label(t.exit_reason)}")

        if t.exit_reason == "signal_exit":
            print(f"  (vela de señal #{xi_label} → ejecución al open de vela #{t.exit_index})")

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

    fig = plt.figure(figsize=(22, 10))
    gs  = gridspec.GridSpec(2, 1, height_ratios=[4, 1], hspace=0.06)
    ax_price  = fig.add_subplot(gs[0])
    ax_equity = fig.add_subplot(gs[1], sharex=ax_price)

    ax_price.set_facecolor("white")
    ax_equity.set_facecolor("white")
    ax_price.grid(True, alpha=0.25, color="gray", linewidth=0.5)
    ax_equity.grid(True, alpha=0.25, color="gray", linewidth=0.5)

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
    text_color_bull = "#0f766e"  # variante más oscura de BULL
    text_color_bear = "#b71c1c"  # variante más oscura de BEAR

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

        # Línea horizontal de stop loss dentro de la zona
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
    ax_equity.set_xlabel("Fecha (UTC)", fontsize=9)
    ax_equity.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: f"${x:,.0f}")
    )

    fig.autofmt_xdate(rotation=30, ha="right")
    plt.tight_layout()

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
        signals = ema_vertical_cross_long_strategy(
            closes, highs,
            fast_span=10,
            slow_span=55,
            min_slope_pct=params["min_slope_pct"],
            exit_slope_periods=params["exit_slope_periods"],
        )
        print(f"  Entradas: {signals.entry_long.sum()}   Salidas: {signals.exit_long.sum()}")

        from indicators.emas import ema_pct_slope
        slope_pct = ema_pct_slope(signals.ema_fast)

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

        # Debug de señales — imprime tabla vela a vela
        debug_signals(
            times=times,
            closes=closes,
            opens=opens,
            signals=signals,
            slope_pct=slope_pct,
            result=result,
            min_slope_pct=params["min_slope_pct"],
        )

        print_summary(result, params, trade_contexts)

        backtest_id = await save_backtest_result(result)
        print(f"  Guardado en MongoDB  [_id: {backtest_id}]")
        print()

        plot_backtest(times, opens, highs, lows, closes, signals, result, params)

    finally:
        await disconnect()
if __name__ == "__main__":
    asyncio.run(main())