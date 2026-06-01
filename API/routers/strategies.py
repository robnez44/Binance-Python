from __future__ import annotations
from typing import List, Optional

from fastapi import APIRouter, Body, HTTPException

from API.schemas.strategies import SaveStrategyRequest, StrategyRecordResponse
from API.services.strategies_service import save_strategy_record, list_strategies, get_strategy, remove_strategy

router = APIRouter()

@router.post("", response_model=dict)
async def save_strategy(req: SaveStrategyRequest = Body(...)) -> dict:
    try:
        strategy_id = await save_strategy_record(
            req.config,
            name=req.name,
            symbol=req.symbol,
            interval=req.interval,
            description=req.description,
        )
        return {"id": strategy_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.get("", response_model=List[StrategyRecordResponse])
async def list_saved_strategies(symbol: Optional[str] = None, interval: Optional[str] = None, limit: int = 50) -> List[StrategyRecordResponse]:
    return await list_strategies(symbol=symbol, interval=interval, limit=limit)

@router.get("/{strategy_id}", response_model=StrategyRecordResponse)
async def get_saved_strategy(strategy_id: str) -> StrategyRecordResponse:
    strategy = await get_strategy(strategy_id)
    if strategy is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strategy

@router.delete("/{strategy_id}")
async def delete_saved_strategy(strategy_id: str):
    ok = await remove_strategy(strategy_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Strategy not found or could not be deleted")
    return {"deleted": True}