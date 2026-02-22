import matplotlib.pyplot as plt
from datetime import datetime, timezone
from utils.utils import timestamp_to_utc, toDicto
import pytz
import requests
import json

# URL de la API
url = "https://api.binance.com/api/v3/"

# Convertir fecha a milisegundos (Fecha UTC)                # YYYY/MM/DD - HH:MM:SS
start_date = datetime(2026, 2, 4, 4, tzinfo=timezone.utc)   # 2O26/02/04 - 04:00:00
start_time = int(start_date.timestamp() * 1000)
end_date = datetime(2026, 2, 12, tzinfo=timezone.utc)       # 2026/02/12 - 00:00:00
end_time = int(end_date.timestamp() * 1000)

# Request
params = {
    "symbol": "BTCUSDT",
    "interval": "4h",
    "startTime": start_time,
    "endTime": end_time,
}
response = requests.get(url+"klines", params=params)
data = response.json()
# print(json.dumps(data[-1], indent=3)) # Ver la ultima  vela

# Verificar la fecha de la primera vela
timestamp_ms = data[0][0]
date_utc = timestamp_to_utc(timestamp_ms)
print("Fecha de apertura de la primera vela:", date_utc)

# Limpiar los datos
cleaned_data = [toDicto(kline) for kline in data]
print(json.dumps(cleaned_data[-1], indent=3, default=str)) # Ver la ultima  vela
x = [k["close_time"] for k in cleaned_data]
y = [k["close_price"] for k in cleaned_data]

# Representar precios con grafico de lineas
fig, ax = plt.subplots(figsize=(10, 6))
ax.plot(x, y)
ax.set_xlabel("Fecha de cierre")
ax.set_ylabel("Precio de cierre")
ax.set_title("Bitcoin / TetherUS • 4h • Binance")
ax.grid(True, alpha=0.2)
plt.show()