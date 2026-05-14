from __future__ import annotations
from typing import List, Optional
from fastapi import APIRouter, Body, HTTPException, Query

from API.schemas.backtest import BacktestRequest, BacktestResponse
from API.openapi_examples.backtests_examples import OPENAPI_EXAMPLES
from API.services.backtest_service import execute_backtest, list_backtests, get_backtest_by_id

router = APIRouter()

#  POST /api/backtests/run
@router.post(
    "/run",
    response_model=BacktestResponse,
    summary="Correr un nuevo backtest",
    description=(
        "Recibe los parámetros, corre el backtest sobre los candles guardados "
        "en MongoDB y devuelve el resultado completo con todos los trades. "
        "Requiere que existan candles para el rango solicitado; la serie se arma "
        "solo con ese rango exacto y sus snapshots asociados."
    ),
)
async def run_backtest(
    req: BacktestRequest = Body(..., openapi_examples=OPENAPI_EXAMPLES),
) -> BacktestResponse:
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
async def list_backtests_endpoint(
    symbol:        str           = Query(..., description="Símbolo requerido, ej: BTCUSDT"),
    interval:      str           = Query(..., description="Intervalo requerido, ej: 4h"),
    strategy_name: Optional[str] = Query(None, description="Filtrar por nombre de estrategia (opcional)"),
    limit:         int           = Query(20, ge=1, le=200, description="Máximo de resultados"),
) -> List[BacktestResponse]:
    """Obtiene lista de backtests para un símbolo e intervalo específicos."""
    return await list_backtests(
        symbol=symbol,
        interval=interval,
        strategy_name=strategy_name,
        limit=limit,
    )

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
    """Obtiene un backtest por su ID."""
    try:
        return await get_backtest_by_id(backtest_id)
    except ValueError as e:
        # Mapear ValueError a errores HTTP apropiados
        msg = str(e)
        if "no encontrado" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        elif "inválido" in msg.lower() or "formato" in msg.lower():
            raise HTTPException(status_code=400, detail=msg)
        else:
            raise HTTPException(status_code=422, detail=msg)