from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from decimal import Decimal
from backtesting.records import (
    BacktestAlertEvent,
    BacktestConfig,
    BacktestResult,
    SignalTimelineRow,
    Trade,
)

# ══════════════════════════════════════════════════════════════════════════════
#  Conversión de timestamps
# ══════════════════════════════════════════════════════════════════════════════    
def timestamp_to_utc(timestamp_ms: int) -> datetime:
    """Convierte un timestamp en milisegundos a datetime UTC."""
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)

# ══════════════════════════════════════════════════════════════════════════════
#  Conversores a dict (para guardar en MongoDB)
# ══════════════════════════════════════════════════════════════════════════════
def candles_to_dict(kline: List[Any]) -> Dict[str, Any]:
    """Convierte una kline cruda de Binance (lista) a diccionario tipado."""
    return {
        "open_time": timestamp_to_utc(kline[0]),
        "open_price": Decimal(kline[1]),
        "high_price": Decimal(kline[2]),
        "low_price": Decimal(kline[3]),
        "close_price": Decimal(kline[4]),
        "volume": Decimal(kline[5]),
        "close_time": timestamp_to_utc(kline[6]),
        "quote_asset_volume": Decimal(kline[7]),
        "number_of_trades": int(kline[8]),
        "taker_buy_base_asset_volume": Decimal(kline[9]),
        "taker_buy_quote_asset_volume": Decimal(kline[10]),
    }

def trade_to_dict(trade: Trade) -> Dict[str, Any]:
    """Convierte un Trade (dataclass) a diccionario para MongoDB."""
    return {
        "entry_time": trade.entry_time,
        "exit_time": trade.exit_time,
        "side": trade.side,
        "entry_index": trade.entry_index,
        "exit_index": trade.exit_index,
        "entry_price": trade.entry_price,
        "exit_price": trade.exit_price,
        "quantity": trade.quantity,
        "pnl": trade.pnl,
        "return_pct": trade.return_pct,
        "candles_held": trade.candles_held,
        "exit_reason": trade.exit_reason,
        "equity_before": trade.equity_before,
        "equity_after": trade.equity_after,
    }

def alert_event_to_dict(event: BacktestAlertEvent) -> Dict[str, Any]:
    """Convierte un BacktestAlertEvent a diccionario para MongoDB."""
    return {
        "index": event.index,
        "timestamp": event.timestamp,
        "event_type": event.event_type,
        "action": event.action,
        "message": event.message,
        "price": event.price,
        "trade_number": event.trade_number,
        "exit_reason": event.exit_reason,
        "exit_reason_label": event.exit_reason_label,
    }

def signal_timeline_row_to_dict(row: SignalTimelineRow) -> Dict[str, Any]:
    """Convierte una fila de timeline de señales a diccionario para MongoDB."""
    return {
        "index": row.index,
        "timestamp": row.timestamp,
        "close_price": row.close_price,
        "ema10": row.ema10,
        "ema55": row.ema55,
        "gap_pct": row.gap_pct,
        "slope_pct": row.slope_pct,
        "cond_ema10_gt_ema55": row.cond_ema10_gt_ema55,
        "cond_gap_ge_min": row.cond_gap_ge_min,
        "cond_slope_ge_min": row.cond_slope_ge_min,
        "cond_price_gt_ema10": row.cond_price_gt_ema10,
        "adx": row.adx,
        "plus_di": row.plus_di,
        "minus_di": row.minus_di,
        "event": row.event,
    }

def config_to_dict(config: BacktestConfig) -> Optional[Dict[str, Any]]:
    """Convierte un BacktestConfig (dataclass) a diccionario para MongoDB."""
    if config is None:
        return None
    return {
        "initial_capital": config.initial_capital,
        "leverage": config.leverage,
        "stop_loss_pct": config.stop_loss_pct,
        "take_profit_pct": config.take_profit_pct,
        "breakeven_trigger_pct": config.breakeven_trigger_pct,
        "min_slope_pct": config.min_slope_pct,
        "exit_slope_periods": config.exit_slope_periods,
        "ema_gap_min_pct": config.ema_gap_min_pct,
        "adx_min": config.adx_min,
        "adx_require_di": config.adx_require_di,
        "adx_require_rising": config.adx_require_rising,
        "atr_period": config.atr_period,
        "atr_stop_mult": config.atr_stop_mult,
        "atr_trailing_mult": config.atr_trailing_mult,
        "atr_stop_confirm_on_close": config.atr_stop_confirm_on_close,
    }

def backtest_result_to_dict(result: BacktestResult) -> Dict[str, Any]:
    """Convierte un BacktestResult completo a diccionario para MongoDB."""
    timeline = result.signals_timeline
    alerts_feed_docs = [alert_event_to_dict(e) for e in result.alerts_feed]
    timeline_docs = [signal_timeline_row_to_dict(r) for r in timeline]
    return {
        "symbol": result.symbol,
        "interval": result.interval,
        "start_time": result.start_time,
        "end_time": result.end_time,
        "analysis_record_id": result.analysis_record_id,
        "analysis_reused": result.analysis_reused,
        "loaded_candles_count": result.loaded_candles_count,
        "strategy_name": result.strategy_name,
        "initial_capital": result.initial_capital,
        "final_capital": result.final_capital,
        "total_return_pct": result.total_return_pct,
        "total_trades": result.total_trades,
        "winning_trades": result.winning_trades,
        "losing_trades": result.losing_trades,
        "win_rate_pct": result.win_rate_pct,
        "profit_factor": result.profit_factor if result.profit_factor != float("inf") else 999.0,
        "avg_trade_return_pct": result.avg_trade_return_pct,
        "max_drawdown_pct": result.max_drawdown_pct,
        "report_pdf_filename": result.report_pdf_filename,
        "config": config_to_dict(result.config),
        "alerts_feed": alerts_feed_docs,
        "signals_timeline": timeline_docs,
        "trades": [trade_to_dict(t) for t in result.trades],
        "created_at": result.created_at or datetime.now(timezone.utc),
    }

def parse_utc(s: str) -> datetime:
    """
    Convierte entrada tipo:
      2026-02-01
      2026-02-01 04:00
    a datetime con tz UTC.
    """
    s = s.strip()
    # con hora
    if " " in s:
        return datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    # solo fecha
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)

def ask_candles_params():
    # ---- symbol fijo por ahora ---
    smbl = input("Simbolo (default: BTCUSDT): ").strip()
    symbol = smbl if smbl else "BTCUSDT"

    # --- interval ---
    interval = input("Temporalidad (ej: 4h, 1d, 3d, 1w, 1M): ").strip()

    # --- start ---
    start_str = input("Start UTC (YYYY-MM-DD HH:MM or YYYY-MM-DD): ").strip()
    start_date = parse_utc(start_str)
    start_time = int(start_date.timestamp() * 1000)

    # --- end opcional ---
    end_str = input("End UTC (opcional): ").strip()
    end_time = int(parse_utc(end_str).timestamp() * 1000) if end_str else None

    params = {
    "symbol": symbol,
    "interval": interval,
    "startTime": start_time,
    **({"endTime": end_time} if end_time else {})
    }   

    return params