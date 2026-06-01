from __future__ import annotations
from typing import Any, Dict

from API.schemas.backtest import BacktestConfigResponse
from API.schemas.strategies import StrategyRecordResponse

def config_to_dict(config: BacktestConfigResponse | Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(config, BacktestConfigResponse):
        return config.model_dump()
    return dict(config)

def to_strategy_response(doc: dict) -> StrategyRecordResponse:
    payload = dict(doc)
    payload.pop("_id", None)
    payload["id"] = str(doc.get("_id", payload.get("id", "")))
    return StrategyRecordResponse.model_validate(payload)
