from datetime import datetime, timezone

from backtesting.serializers import candles_to_dict

# ══════════════════════════════════════════════════════════════════════════════
#  Conversión de timestamps
# ══════════════════════════════════════════════════════════════════════════════    
def timestamp_to_utc(timestamp_ms: int) -> datetime:
    """Convierte un timestamp en milisegundos a datetime UTC."""
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)

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