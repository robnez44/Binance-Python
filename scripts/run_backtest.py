import asyncio
import numpy as np
import pandas as pd

from backtesting.simulator import run_long_backtest
from backtesting.strategies import build_ema_long_signals
from backtesting.alerts import build_alerts_feed, build_signals_timeline
from backtesting.series import build_series_payload
from backtesting.backtest_params import ask_backtest_params
from backtesting.backtest_plot import plot_backtest
from backtesting.backtest_reporting import build_trade_context, check_alerts, debug_signals, print_summary
from database.database import connectDB, disconnect
from database.repository import get_analysis_for_range, get_candles, save_backtest_result
from indicators.emas import ema_pct_slope

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
        end_date = candles[-1].close_time.strftime("%Y-%m-%d")
        print(f"  {len(candles)} velas cargadas  [{start_date} -> {end_date}]")

        times = pd.to_datetime([c.close_time for c in candles], utc=True)
        opens = np.array([float(c.open_price) for c in candles], dtype=float)
        highs = np.array([float(c.high_price) for c in candles], dtype=float)
        lows = np.array([float(c.low_price) for c in candles], dtype=float)
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

        slope_pct = ema_pct_slope(signals.ema_fast)

        print("  Ejecutando backtest...")
        result = run_long_backtest(
            times=times,
            opens=opens,
            highs=highs,
            lows=lows,
            closes=closes,
            entry_signals=signals.entry_long,
            exit_signals=signals.exit_long,
            config=params["config"],
            strategy_name=signals.name,
            symbol=params["symbol"],
            interval=params["interval"],
        )

        # Construir artefactos de observabilidad (persistidos en MongoDB)
        result.alerts_feed = build_alerts_feed(times, closes, signals, result, slope_pct=slope_pct)
        result.signals_timeline = build_signals_timeline(
            times=times,
            closes=closes,
            signals=signals,
            slope_pct=slope_pct,
            result=result,
            min_slope_pct=params.get("min_slope_pct", 0.0),
            ema_gap_min_pct=params.get("ema_gap_min_pct", 0.0),
        )

        # Print-only
        check_alerts(feed=result.alerts_feed, params=params)

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
        series_doc = await get_analysis_for_range(
            symbol=params["symbol"],
            interval=params["interval"],
            start_time=times[0].to_pydatetime(),
            end_time=times[-1].to_pydatetime(),
        )
        result.loaded_candles_count = len(candles)
        # Si hay analysis, siempre lo reutilizamos
        result.analysis_reused = True
        result.analysis_record_id = str(series_doc.get("_id"))
        use_adx = params["adx_min"] > 0 or params["adx_require_di"] or params["adx_require_rising"]
        # Build series payload for display only (do not attach to result or persist)
        series_payload = build_series_payload(
            analysis_doc=series_doc,
            include_adx_points=use_adx,
        )
        plot_backtest(times, opens, highs, lows, closes, signals, result, params)

        # Guardar una sola vez, ya con el nombre de PDF resuelto.
        backtest_id = await save_backtest_result(result)
        print(f"  Guardado en MongoDB  [_id: {backtest_id}]")
        if result.report_pdf_filename:
            print(f"  PDF en registro MongoDB: {result.report_pdf_filename}")
        print()

    finally:
        await disconnect()

if __name__ == "__main__":
    asyncio.run(main())
