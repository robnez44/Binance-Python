from __future__ import annotations
from typing import Optional, List, Dict, Any

from API.schemas.backtest import BacktestConfigResponse
from API.schemas.strategies import StrategyRecordResponse
from API.utils.strategies import config_to_dict, to_strategy_response
from database.repository import (
    save_strategy,
    get_strategies,
    get_strategy_by_id,
    delete_strategy,
)

async def save_strategy_record(
    config: BacktestConfigResponse | Dict[str, Any],
    name: Optional[str] = None,
    symbol: Optional[str] = None,
    interval: Optional[str] = None,
    description: Optional[str] = None,
) -> str:
    return await save_strategy(
        config=config_to_dict(config),
        name=name,
        symbol=symbol,
        interval=interval,
        description=description,
    )

async def list_strategies(symbol: Optional[str] = None, interval: Optional[str] = None, limit: int = 50) -> List[StrategyRecordResponse]:
    docs = await get_strategies(symbol=symbol, interval=interval, limit=limit)
    return [to_strategy_response(doc) for doc in docs]

async def get_strategy(strategy_id: str) -> Optional[StrategyRecordResponse]:
    doc = await get_strategy_by_id(strategy_id)
    if doc is None:
        return None
    return to_strategy_response(doc)


async def remove_strategy(strategy_id: str) -> bool:
    return await delete_strategy(strategy_id)
