from __future__ import annotations
from typing import Any, Dict, List
import os
import requests
from dotenv import load_dotenv

load_dotenv()
BASE_URL = os.getenv("BINANCE_API")
KLINES_MAX_LIMIT = 1000
KLINES_DEFAULT_LIMIT = 1000

def get_klines(params: Dict[str, Any]) -> List[List[Any]]:
    """Consulta el endpoint /klines de Binance y devuelve el JSON crudo."""
    req_params = dict(params)

    limit = req_params.get("limit")
    if limit is None:
        req_params["limit"] = KLINES_DEFAULT_LIMIT
    else:
        try:
            limit_int = int(limit)
        except (TypeError, ValueError):
            limit_int = KLINES_DEFAULT_LIMIT
        req_params["limit"] = max(1, min(limit_int, KLINES_MAX_LIMIT))

    response = requests.get(BASE_URL + "klines", params=req_params, timeout=30)
    response.raise_for_status()
    data = response.json()

    # Binance puede responder errores en JSON con forma dict
    if isinstance(data, dict) and ("code" in data or "msg" in data):
        raise RuntimeError(f"Binance API error: {data}")

    return data
