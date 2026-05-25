import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

from backtesting.records import BacktestConfig, BacktestResult, StrategySignals
from backtesting.backtest_params import build_pdf_path
from indicators.atr import compute_atr


def _resolve_initial_stop_price(
    entry_price: float,
    stop_loss_pct: float | None,
    atr_value: float | None,
    atr_stop_mult: float | None,
) -> tuple[float | None, str]:
    pct_stop = (
        entry_price * (1 - stop_loss_pct)
        if stop_loss_pct is not None else None
    )

    atr_stop = None
    if atr_stop_mult is not None and atr_stop_mult > 0 and atr_value is not None and atr_value > 0:
        atr_stop = entry_price - atr_value * atr_stop_mult

    if pct_stop is None and atr_stop is None:
        return None, "none"
    if pct_stop is None:
        return atr_stop, "atr"
    if atr_stop is None:
        return pct_stop, "pct"

    stop_price = max(pct_stop, atr_stop)
    stop_origin = "atr" if atr_stop >= pct_stop else "pct"
    return stop_price, stop_origin


def _build_dynamic_stop_line(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    result: BacktestResult,
    config: BacktestConfig,
) -> np.ndarray:
    n = len(closes)
    stop_line = np.full(n, np.nan, dtype=float)

    use_atr_stop = config.atr_stop_mult is not None and config.atr_stop_mult > 0
    use_atr_trailing = config.atr_trailing_mult is not None and config.atr_trailing_mult > 0
    has_any_stop = use_atr_stop or use_atr_trailing or (config.stop_loss_pct is not None)
    if not has_any_stop:
        return stop_line

    atr_values: np.ndarray | None = None
    if use_atr_stop or use_atr_trailing:
        atr_series = compute_atr(
            pd.Series(highs),
            pd.Series(lows),
            pd.Series(closes),
            n=config.atr_period,
        )
        atr_values = atr_series.bfill().ffill().to_numpy()

    for trade in result.trades:
        entry_index = int(trade.entry_index)
        if entry_index < 0 or entry_index >= n:
            continue

        manage_end = int(trade.exit_index)
        if trade.exit_reason == "signal_exit" and manage_end > entry_index:
            # En signal_exit se cierra al open de la vela siguiente; la gestión llega hasta la vela de señal.
            manage_end -= 1
        manage_end = min(max(manage_end, entry_index), n - 1)

        atr_at_entry = float(atr_values[entry_index]) if atr_values is not None else None
        stop_price, _ = _resolve_initial_stop_price(
            entry_price=float(trade.entry_price),
            stop_loss_pct=config.stop_loss_pct,
            atr_value=atr_at_entry,
            atr_stop_mult=config.atr_stop_mult,
        )

        peak_close = float(trade.entry_price)
        breakeven_active = False

        for i in range(entry_index, manage_end + 1):
            if i > entry_index and use_atr_trailing and atr_values is not None:
                peak_close = max(peak_close, float(closes[i]))
                candidate_stop = peak_close - float(atr_values[i]) * float(config.atr_trailing_mult)
                if stop_price is None or candidate_stop > stop_price:
                    stop_price = candidate_stop

            if (
                config.breakeven_trigger_pct is not None
                and i > entry_index
                and not breakeven_active
                and float(highs[i]) >= float(trade.entry_price) * (1 + float(config.breakeven_trigger_pct))
            ):
                stop_price = float(trade.entry_price)
                breakeven_active = True

            if stop_price is not None:
                stop_line[i] = float(stop_price)

    return stop_line

# ══════════════════════════════════════════════════════════════════════════════
#  Gráfico limpio: velas + EMAs + marcadores de trades
# ══════════════════════════════════════════════════════════════════════════════
def plot_backtest(
    times: pd.DatetimeIndex,
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    signals: StrategySignals,
    result: BacktestResult,
    params: dict,
    show: bool = False,
) -> None:

    has_adx = signals.adx_values is not None
    n_subplots = 3 if has_adx else 2
    ratios = [4, 1.2, 1] if has_adx else [4, 1]

    BULL = "#26a69a"
    BEAR = "#ef5350"
    EMA_FAST = "pink"
    EMA_SLOW = "orange"
    ENTRY_C = "#1565c0"
    WIN_C = "#2e7d32"
    LOSS_C = "#c62828"
    BE_C = "#f9a825"
    SL_C = "#ef9a9a"
    ZONE_WIN = "#a5d6a7"
    ZONE_LOSS = "#ef9a9a"
    ZONE_BE = "#fff9c4"
    ATR_STOP_C = "#8d6e63"  # marrón suave — stop dinámico ATR
    ADX_C = "#7b1fa2"   # morado — línea ADX
    ADX_MIN_C = "#e53935"   # rojo punteado — umbral mínimo
    PDI_C = "#66bb6a"   # verde suave — +DI
    MDI_C = "#ef5350"   # rojo — -DI

    fig = plt.figure(figsize=(22, 12 if has_adx else 10))
    gs = gridspec.GridSpec(n_subplots, 1, height_ratios=ratios, hspace=0.06)

    ax_price = fig.add_subplot(gs[0])
    ax_equity = fig.add_subplot(gs[1], sharex=ax_price)
    ax_adx = fig.add_subplot(gs[2], sharex=ax_price) if has_adx else None

    for ax in ([ax_price, ax_equity] + ([ax_adx] if ax_adx else [])):
        ax.set_facecolor("white")
        ax.grid(True, alpha=0.25, color="gray", linewidth=0.5)

    # ── Velas ────────────────────────────────────────────────────────────
    candle_width = (times[1] - times[0]) * 0.6 if len(times) > 1 else pd.Timedelta(hours=4)
    bull_mask = closes >= opens
    bear_mask = ~bull_mask

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
    price_range = highs.max() - lows.min()
    arrow_offset = price_range * 0.016

    for trade in result.trades:
        t_entry = times[trade.entry_index]
        t_exit = times[trade.exit_index]

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

    # ── Línea de stop dinámico (ATR/manual) ─────────────────────────────
    stop_line = _build_dynamic_stop_line(
        highs=highs,
        lows=lows,
        closes=closes,
        result=result,
        config=params["config"],
    )
    has_stop_line = np.isfinite(stop_line).any()
    if has_stop_line:
        ax_price.plot(
            times,
            stop_line,
            color=ATR_STOP_C,
            linewidth=1.2,
            linestyle="--",
            label="Stop dinámico",
            zorder=5,
        )

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
    if has_stop_line:
        legend_handles.append(
            Line2D([0], [0], color=ATR_STOP_C, linewidth=1.2, linestyle="--", label="Stop dinámico")
        )
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
    eq_times = [times[0]]
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
        if signals.plus_di is not None:
            ax_adx.plot(times, signals.plus_di, color=PDI_C,
                        linewidth=1.2, label="+DI", alpha=0.95, zorder=2)
        if signals.minus_di is not None:
            ax_adx.plot(times, signals.minus_di, color=MDI_C,
                        linewidth=1.2, label="-DI", alpha=0.95, zorder=2)
        if params["adx_min"] > 0:
            ax_adx.axhline(params["adx_min"], color=ADX_MIN_C,
                           linewidth=1.0, linestyle="--", alpha=0.8,
                           label=f"Mín ADX ({params['adx_min']:.0f})")
        ax_adx.set_ylabel("ADX / DI", fontsize=9)
        ax_adx.set_xlabel("Fecha (UTC)", fontsize=9)
        ax_adx.legend(loc="upper left", fontsize=8, framealpha=0.9)
    else:
        ax_equity.set_xlabel("Fecha (UTC)", fontsize=9)

    fig.autofmt_xdate(rotation=30, ha="right")
    plt.tight_layout()

    try:
        pdf_path = build_pdf_path(result, params)
        fig.savefig(pdf_path, format="pdf", bbox_inches="tight")
        result.report_pdf_filename = pdf_path.name
        print(f"  PDF guardado: {pdf_path}")
    except Exception as exc:
        result.report_pdf_filename = None
        print(f"  Aviso: no se pudo guardar PDF ({exc})")

    if show:
        try:
            manager = plt.get_current_fig_manager()
            manager.window.showMaximized()
        except Exception:
            pass

        plt.show()
