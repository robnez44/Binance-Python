import numpy as np
import pandas as pd

from backtesting.records import BacktestResult, StrategySignals

# ══════════════════════════════════════════════════════════════════════════════
#  Debug de señales — tabla vela a vela
# ══════════════════════════════════════════════════════════════════════════════
def debug_signals(
    times: pd.DatetimeIndex,
    closes: np.ndarray,
    opens: np.ndarray,
    signals: StrategySignals,
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
    exit_exec = {t.exit_index: t for t in result.trades}

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

        ema10 = signals.ema_fast[i]
        ema55 = signals.ema_slow[i]
        ema_gap = ((ema10 - ema55) / ema55 * 100) if ema55 else 0.0
        slope = slope_pct[i]
        price = closes[i]
        fecha = times[i].strftime("%m-%d %H:%M")

        cross_ok = ema10 > ema55
        gap_ok = ema_gap >= ema_gap_min_pct
        slope_ok = slope >= min_slope_pct
        above_ok = price > ema10
        cross_s = "✔" if cross_ok else "✘"
        gap_s = "✔" if gap_ok else "✘"
        slope_s = "✔" if slope_ok else "✘"
        above_s = "✔" if above_ok else "✘"

        adx_col = ""
        if has_adx:
            adx_v = signals.adx_values[i]
            adx_ok = adx_v >= adx_min if adx_min > 0 else True
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
                adx_v2 = signals.adx_values[i]
                adx_ok2 = adx_v2 >= adx_min if adx_min > 0 else True
                di_ok2 = signals.plus_di[i] > signals.minus_di[i]
                adx_up_ok2 = (adx_v2 >= signals.adx_values[i - 1]) if i > 0 else False
                conds += "✔" if adx_ok2 else "✘"
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
    signals: StrategySignals,
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

        adx_entry = float(signals.adx_values[si]) if has_adx else None
        adx_prev_entry = float(signals.adx_values[si - 1]) if has_adx and si > 0 else None
        pdi_entry = float(signals.plus_di[si]) if has_adx else None
        mdi_entry = float(signals.minus_di[si]) if has_adx else None

        neg_streak = 0
        if trade.exit_reason == "signal_exit":
            for j in range(xi, max(xi - exit_slope_periods - 10, -1), -1):
                if j >= 0 and slope_pct[j] <= -min_slope_pct:
                    neg_streak += 1
                else:
                    break

        contexts.append(
            {
                "signal_index_entry": si,
                "signal_index_exit": xi,
                "ema10_entry": signals.ema_fast[si],
                "ema55_entry": signals.ema_slow[si],
                "ema_gap_entry": ((signals.ema_fast[si] - signals.ema_slow[si]) / signals.ema_slow[si] * 100) if signals.ema_slow[si] else 0.0,
                "slope_entry": slope_pct[si],
                "price_entry": closes[si],
                "adx_entry": adx_entry,
                "adx_prev_entry": adx_prev_entry,
                "plus_di_entry": pdi_entry,
                "minus_di_entry": mdi_entry,
                "ema10_exit": signals.ema_fast[xi],
                "slope_exit": slope_pct[xi],
                "price_exit": closes[xi],
                "neg_streak": neg_streak,
            }
        )

    return contexts

# ══════════════════════════════════════════════════════════════════════════════
#  Print resumen en terminal
# ══════════════════════════════════════════════════════════════════════════════
def _reason_label(reason: str) -> str:
    labels = {
        "take_profit": "✔  take_profit",
        "stop_loss": "✘  stop_loss",
        "atr_stop_loss": "✘  atr_stop",
        "atr_trailing_stop": "✘  atr_trailing",
        "breakeven_stop": "◈  breakeven",
        "stop_loss_priority_same_bar": "✘  sl_same_bar",
        "signal_exit": "↩  signal_exit",
        "end_of_data": "⏹  end_of_data",
    }
    return labels.get(reason, reason)

def print_summary(
    result: BacktestResult,
    params: dict,
    trade_contexts: list,
) -> None:
    W = 80
    SEP = "─" * W
    SEP2 = "═" * W
    config = params["config"]

    print()
    print(SEP2)
    print(f"  BACKTEST RESULT  ·  {params['symbol']}  ·  {params['interval']}")
    print(SEP2)

    print()
    print(f"  {'Estrategia':<28} {result.strategy_name}")
    start_label = params["start_time"].strftime("%Y-%m-%d")
    end_label = params["end_time"].strftime("%Y-%m-%d") if params.get("end_time") else "hoy"
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
    print("  RENDIMIENTO")
    print()
    capital_delta = result.final_capital - result.initial_capital
    delta_sign = "+" if capital_delta >= 0 else ""
    ret_sign = "+" if result.total_return_pct >= 0 else ""
    print(f"  {'Capital final':<28} ${result.final_capital:>12,.2f}")
    print(f"  {'Ganancia neta':<28} {delta_sign}${capital_delta:,.2f}")
    print(f"  {'Retorno total':<28} {ret_sign}{result.total_return_pct:.2f}%")
    print(f"  {'Max Drawdown':<28} {result.max_drawdown_pct:.2f}%")

    print()
    print(SEP)
    print("  TRADES")
    print()
    total = result.total_trades
    wins = result.winning_trades
    loss = result.losing_trades
    BAR_LEN = 20
    win_fill = round(wins / total * BAR_LEN) if total else 0
    loss_fill = round(loss / total * BAR_LEN) if total else 0
    rest_fill = BAR_LEN - win_fill - loss_fill
    bar = "[" + ("█" * win_fill) + ("░" * loss_fill) + ("·" * rest_fill) + "]"
    avg_sign = "+" if result.avg_trade_return_pct >= 0 else ""
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
    print("  DETALLE DE OPERACIONES")

    for idx, (t, ctx) in enumerate(zip(result.trades, trade_contexts), 1):
        print()
        pnl_sign = "+" if t.pnl >= 0 else ""
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

        ema10_e = ctx["ema10_entry"]
        ema55_e = ctx["ema55_entry"]
        gap_e = ctx["ema_gap_entry"]
        slope_e = ctx["slope_entry"]
        price_e = ctx["price_entry"]
        cross_ok = ema10_e > ema55_e
        gap_ok = gap_e >= params["ema_gap_min_pct"]

        cross_sym = "✔" if cross_ok else "✘"
        gap_sym = "✔" if gap_ok else "✘"
        slope_sym = "✔" if slope_e >= params["min_slope_pct"] else "✘"
        above_sym = "✔" if price_e > ema10_e else "✘"
        cross_rel = ">" if cross_ok else "<"
        above_rel = ">" if price_e > ema10_e else "<"
        slope_e_s = "+" if slope_e >= 0 else ""

        print(f"    {cross_sym}  EMA 10 {cross_rel} EMA 55")
        print(f"         EMA 10 = {ema10_e:>12,.2f}")
        print(f"         EMA 55 = {ema55_e:>12,.2f}")
        print(
            f"    {gap_sym}  Gap EMA10-EMA55 = {gap_e:+.4f}%"
            f"   (mín requerido: +{params['ema_gap_min_pct']:.4f}%)"
        )
        print(
            f"    {slope_sym}  Pendiente EMA 10 = {slope_e_s}{slope_e:.4f}%"
            f"   (mín requerido: +{params['min_slope_pct']:.4f}%)"
        )
        print(f"    {above_sym}  Precio {above_rel} EMA 10")
        print(f"         Precio = {price_e:>12,.2f}")
        print(f"         EMA 10 = {ema10_e:>12,.2f}")

        if ctx["adx_entry"] is not None and params["use_adx"]:
            adx_e = ctx["adx_entry"]
            adx_ok = adx_e >= params["adx_min"]
            adx_sym = "✔" if adx_ok else "✘"
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

            ema10_x = ctx["ema10_exit"]
            slope_x = ctx["slope_exit"]
            price_x = ctx["price_exit"]
            neg_str = ctx["neg_streak"]
            n = params["exit_slope_periods"]

            streak_sym = "✔" if neg_str >= n else "✘"
            slope_sym2 = "✔" if slope_x <= -params["min_slope_pct"] else "✘"
            below_sym = "✔" if price_x < ema10_x else "✘"
            below_rel = "<" if price_x < ema10_x else ">"
            slope_x_s = "+" if slope_x >= 0 else ""

            print(
                f"    {streak_sym}  Pendiente negativa sostenida: {neg_str} velas"
                f"   (se necesitan {n})"
            )
            print(
                f"    {slope_sym2}  Pendiente EMA 10 = {slope_x_s}{slope_x:.4f}%"
                f"   (máx permitido: -{params['min_slope_pct']:.4f}%)"
            )
            print(f"    {below_sym}  Precio {below_rel} EMA 10")
            print(f"         Precio = {price_x:>12,.2f}")
            print(f"         EMA 10 = {ema10_x:>12,.2f}")

        elif t.exit_reason in ("stop_loss", "stop_loss_priority_same_bar"):
            sl_pct = config.stop_loss_pct * 100 if config.stop_loss_pct else 0
            print(f"    ✘  Stop Loss tocado: precio cayó a {t.exit_price:,.2f}")
            print(f"       Stop al {sl_pct:.1f}% bajo entrada  ({t.entry_price:,.2f} → {t.exit_price:,.2f})")

        elif t.exit_reason == "atr_stop_loss":
            print("    ✘  Stop dinámico ATR tocado")
            print(f"       Entrada: {t.entry_price:,.2f}   Salida: {t.exit_price:,.2f}")

        elif t.exit_reason == "atr_trailing_stop":
            print("    ✘  Trailing ATR tocado (protección de ganancia)")
            print(f"       Entrada: {t.entry_price:,.2f}   Salida: {t.exit_price:,.2f}")

        elif t.exit_reason == "breakeven_stop":
            print("    ◈  Precio volvió al precio de entrada (stop en breakeven)")
            print(f"       Entrada: {t.entry_price:,.2f}   Salida: {t.exit_price:,.2f}")

        elif t.exit_reason == "take_profit":
            tp_pct = config.take_profit_pct * 100 if config.take_profit_pct else 0
            print(f"    ✔  Take Profit al {tp_pct:.1f}%")
            print(f"       Entrada: {t.entry_price:,.2f}   Salida: {t.exit_price:,.2f}")

        elif t.exit_reason == "end_of_data":
            print("    ⏹  Cierre forzado al final del rango de datos")
            print(f"       Último precio disponible: {t.exit_price:,.2f}")

    print()
    print(SEP2)
    print()
