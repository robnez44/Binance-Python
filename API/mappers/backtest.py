from __future__ import annotations
from dataclasses import asdict

from backtesting.records import BacktestConfig, BacktestResult, Trade
from backtesting.reporting_utils import exit_reason_label
from API.schemas.backtest import (
    BacktestConfigResponse,
    BacktestResponse,
    TradeResponse,
)

def _map_timeline_event_code(code: str) -> str:
    """Mapea un código técnico de timeline a una etiqueta legible.

    Ejemplos:
      - "entry_signal" -> "Entry Signal"
      - "exit_exec_t1_signal_exit" -> "Trade #1 Exit (Strategy Signal Exit)"
    """
    if not code:
        return code

    def _map_token(token: str) -> str:
        if token.startswith("entry_signal"):
            return "Entry Signal"
        if token.startswith("exit_signal"):
            return "Exit Signal"
        if token.startswith("entry_exec_t"):
            trade_no = token.replace("entry_exec_t", "")
            return f"Trade #{trade_no} Entry Executed"
        if token.startswith("exit_exec_t"):
            rest = token.replace("exit_exec_t", "")
            parts = rest.split("_", 1)
            trade_no = parts[0]
            reason = parts[1] if len(parts) > 1 else "unknown"
            reason_label = exit_reason_label(reason, style="plain")
            return f"Trade #{trade_no} Exit ({reason_label})"
        return token

    # tokens pueden estar separados por ' | ' o '_'
    if " | " in code:
        tokens = code.split(" | ")
        return " | ".join(_map_token(t) for t in tokens)

    # si hay múltiples sub-tokens con underscore después de exit_exec_t
    return _map_token(code)

def trade_to_response(trade: Trade) -> TradeResponse:
    return TradeResponse(
        entry_time=trade.entry_time,
        exit_time=trade.exit_time,
        side=trade.side,
        entry_price=trade.entry_price,
        exit_price=trade.exit_price,
        quantity=trade.quantity,
        pnl=trade.pnl,
        return_pct=trade.return_pct,
        candles_held=trade.candles_held,
        exit_reason=trade.exit_reason,
        exit_reason_label=exit_reason_label(trade.exit_reason, style="plain"),
        equity_before=trade.equity_before,
        equity_after=trade.equity_after,
    )

def config_to_response(config: BacktestConfig) -> BacktestConfigResponse:
    return BacktestConfigResponse(
        initial_capital=config.initial_capital,
        leverage=config.leverage,
        stop_loss_pct=config.stop_loss_pct,
        take_profit_pct=config.take_profit_pct,
        breakeven_trigger_pct=config.breakeven_trigger_pct,
        min_slope_pct=config.min_slope_pct,
        exit_slope_periods=config.exit_slope_periods,
        ema_gap_min_pct=config.ema_gap_min_pct,
        adx_min=config.adx_min,
        adx_require_di=config.adx_require_di,
        adx_require_rising=config.adx_require_rising,
        atr_period=config.atr_period,
        atr_stop_mult=config.atr_stop_mult,
        atr_trailing_mult=config.atr_trailing_mult,
        atr_stop_confirm_on_close=config.atr_stop_confirm_on_close,
    )

def result_to_backtest_response(result: BacktestResult, backtest_id: str) -> BacktestResponse:
    alerts_feed_payload = [asdict(event) for event in result.alerts_feed]
    signals_timeline_payload = [asdict(row) for row in result.signals_timeline]

    # Normalizar cualquier código técnico en 'event' a una etiqueta legible
    for row in signals_timeline_payload:
        ev = row.get("event")
        if isinstance(ev, str) and ev:
            row["event"] = _map_timeline_event_code(ev)

    return BacktestResponse(
        id=backtest_id,
        symbol=result.symbol,
        interval=result.interval,
        strategy_name=result.strategy_name,
        start_time=result.start_time,
        end_time=result.end_time,
        created_at=result.created_at,
        initial_capital=result.initial_capital,
        final_capital=result.final_capital,
        total_return_pct=result.total_return_pct,
        max_drawdown_pct=result.max_drawdown_pct,
        total_trades=result.total_trades,
        winning_trades=result.winning_trades,
        losing_trades=result.losing_trades,
        win_rate_pct=result.win_rate_pct,
        profit_factor=min(result.profit_factor, 999.0),
        avg_trade_return_pct=result.avg_trade_return_pct,
        loaded_candles_count=result.loaded_candles_count,
        trades=[trade_to_response(trade) for trade in result.trades],
        config=config_to_response(result.config) if result.config else None,
        alerts_feed=alerts_feed_payload,
        signals_timeline=signals_timeline_payload,
    )

def doc_to_backtest_response(doc: dict) -> BacktestResponse:
    raw_trades: list[dict] = doc.get("trades", [])
    trades: list[TradeResponse] = [
        TradeResponse(
            entry_time=t["entry_time"],
            exit_time=t["exit_time"],
            side=t["side"],
            entry_price=float(t["entry_price"]),
            exit_price=float(t["exit_price"]),
            quantity=float(t["quantity"]),
            pnl=float(t["pnl"]),
            return_pct=float(t["return_pct"]),
            candles_held=int(t["candles_held"]),
            exit_reason=t["exit_reason"],
            exit_reason_label=exit_reason_label(str(t["exit_reason"]), style="plain"),
            equity_before=float(t["equity_before"]),
            equity_after=float(t["equity_after"]),
        )
        for t in raw_trades
    ]

    raw_config: dict | None = doc.get("config")
    config: BacktestConfigResponse | None = None
    if raw_config:
        config = BacktestConfigResponse(
            initial_capital=float(raw_config["initial_capital"]),
            leverage=float(raw_config["leverage"]),
            stop_loss_pct=raw_config.get("stop_loss_pct"),
            take_profit_pct=raw_config.get("take_profit_pct"),
            breakeven_trigger_pct=raw_config.get("breakeven_trigger_pct"),
            min_slope_pct=float(raw_config["min_slope_pct"]),
            exit_slope_periods=int(raw_config["exit_slope_periods"]),
            ema_gap_min_pct=float(raw_config.get("ema_gap_min_pct", 0.0)),
            adx_min=float(raw_config.get("adx_min", 0.0)),
            adx_require_di=bool(raw_config.get("adx_require_di", True)),
            adx_require_rising=bool(raw_config.get("adx_require_rising", False)),
            atr_period=int(raw_config.get("atr_period", 14)),
            atr_stop_mult=raw_config.get("atr_stop_mult"),
            atr_trailing_mult=raw_config.get("atr_trailing_mult"),
            atr_stop_confirm_on_close=bool(raw_config.get("atr_stop_confirm_on_close", True)),
        )
    # If signals_timeline is present in the stored doc, map any technical event codes
    raw_timeline = doc.get(
        "signals_timeline",
        doc.get("alerts_timeline", doc.get("relevant_signals_timeline", [])),
    )
    signals_timeline_payload = []
    for row in raw_timeline:
        if isinstance(row, dict):
            ev = row.get("event")
            if isinstance(ev, str) and ev:
                row = dict(row)  # copy
                row["event"] = _map_timeline_event_code(ev)
        signals_timeline_payload.append(row)

    return BacktestResponse(
        id=str(doc["_id"]),
        symbol=doc["symbol"],
        interval=doc["interval"],
        strategy_name=doc["strategy_name"],
        start_time=doc.get("start_time"),
        end_time=doc.get("end_time"),
        created_at=doc.get("created_at"),
        initial_capital=float(doc["initial_capital"]),
        final_capital=float(doc["final_capital"]),
        total_return_pct=float(doc["total_return_pct"]),
        max_drawdown_pct=float(doc["max_drawdown_pct"]),
        total_trades=int(doc["total_trades"]),
        winning_trades=int(doc["winning_trades"]),
        losing_trades=int(doc["losing_trades"]),
        win_rate_pct=float(doc["win_rate_pct"]),
        profit_factor=float(doc["profit_factor"]),
        avg_trade_return_pct=float(doc["avg_trade_return_pct"]),
        loaded_candles_count=int(doc.get("loaded_candles_count", 0)),
        trades=trades,
        config=config,
        alerts_feed=doc.get("alerts_feed", []),
        signals_timeline=signals_timeline_payload,
    )
