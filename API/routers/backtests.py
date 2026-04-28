from __future__ import annotations
from typing import List, Optional
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query

from API.schemas.backtest import BacktestRequest, BacktestResponse
from API.mappers.backtest import doc_to_backtest_response
from API.services.backtest_service import execute_backtest
from database.database import get_db

router = APIRouter()

#  POST /api/backtests/run
@router.post(
    "/run",
    response_model=BacktestResponse,
    summary="Correr un nuevo backtest",
    description=(
        "Recibe los parámetros, corre el backtest sobre los candles guardados "
        "en MongoDB y devuelve el resultado completo con todos los trades. "
        "Requiere que los candles existan — correr save_analysis primero."
    ),
)
async def run_backtest(req: BacktestRequest) -> BacktestResponse:
    response: Optional[BacktestResponse] = await execute_backtest(req)

    if response is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No hay candles en MongoDB para {req.symbol} {req.interval} "
                f"en el rango {req.start_time} → {req.end_time or 'último disponible'}. "
                "Ejecuta save_analysis primero para ese rango."
            ),
        )

    return response

#  GET /api/backtests
@router.get(
    "",
    response_model=List[BacktestResponse],
    summary="Listar todos los backtests",
    description="Devuelve todos los backtests guardados con sus trades completos.",
)
async def list_backtests(
    symbol:        Optional[str] = Query(None, description="Filtrar por símbolo, ej: BTCUSDT"),
    interval:      Optional[str] = Query(None, description="Filtrar por temporalidad, ej: 4h"),
    strategy_name: Optional[str] = Query(None, description="Filtrar por nombre de estrategia"),
    limit:         int           = Query(20, ge=1, le=200, description="Máximo de resultados"),
) -> List[BacktestResponse]:
    db = get_db()
    query: dict = {}

    if symbol:
        query["symbol"] = symbol
    if interval:
        query["interval"] = interval
    if strategy_name:
        query["strategy_name"] = strategy_name

    docs: list[dict] = await db.backtests.find(query).sort("created_at", -1).limit(limit).to_list(length=None)

    return [doc_to_backtest_response(doc) for doc in docs]

#  GET /api/backtests/{backtest_id}
@router.get(
    "/{backtest_id}",
    response_model=BacktestResponse,
    summary="Obtener un backtest por ID",
    description=(
        "Devuelve el resultado completo de un backtest específico por su ID de MongoDB, "
        "incluyendo todos los trades individuales y la configuración usada."
    ),
)
async def get_backtest(backtest_id: str) -> BacktestResponse:
    try:
        oid = ObjectId(backtest_id)
    except Exception:
        raise HTTPException(status_code=400, detail=f"ID inválido: '{backtest_id}'")

    db = get_db()
    doc: Optional[dict] = await db.backtests.find_one({"_id": oid})

    if doc is None:
        raise HTTPException(status_code=404, detail=f"Backtest '{backtest_id}' no encontrado.")

    return doc_to_backtest_response(doc)