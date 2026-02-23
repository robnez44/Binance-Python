import requests
from typing import Any, Dict, List

BASE_URL = "https://api.binance.com/api/v3/"

def get_klines(params: Dict[str, Any]) -> List[List[Any]]:
    """Consulta el endpoint /klines de Binance y devuelve el JSON crudo."""
    response = requests.get(BASE_URL + "klines", params=params)
    return response.json()
