from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from decimal import Decimal

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

def trade_to_dict(trade) -> Dict[str, Any]:
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

def config_to_dict(config) -> Optional[Dict[str, Any]]:
    """Convierte un BacktestConfig (dataclass) a diccionario para MongoDB."""
    if config is None:
        return None
    return {
        "initial_capital": config.initial_capital,
        "leverage": config.leverage,
        "stop_loss_pct": config.stop_loss_pct,
        "take_profit_pct": config.take_profit_pct,
    }

def backtest_result_to_dict(result) -> Dict[str, Any]:
    """Convierte un BacktestResult completo a diccionario para MongoDB."""
    return {
        "symbol": result.symbol,
        "interval": result.interval,
        "start_time": result.start_time,
        "end_time": result.end_time,
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
        "config": config_to_dict(result.config),
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
    symbol = "BTCUSDT"

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