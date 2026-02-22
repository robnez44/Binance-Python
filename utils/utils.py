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