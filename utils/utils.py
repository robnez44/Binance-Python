from datetime import datetime, timezone
from typing import Any, Dict, List
from decimal import Decimal

# Funcion para convertir el timestamp a UTC
def timestamp_to_utc(timestamp_ms: int) -> datetime:
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)

# Convertir a diccionario
def toDicto(kline: List[Any]) -> Dict[str, Any]:
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