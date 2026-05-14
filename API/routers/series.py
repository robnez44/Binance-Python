from __future__ import annotations
from fastapi import APIRouter, HTTPException

from API.schemas.series import SeriesDataResponse
from API.services.series_service import get_series_for_backtest

router = APIRouter()

@router.get(
    "/{backtest_id}/series",
    response_model=SeriesDataResponse,
    summary="Obtener series (OHLC + indicadores) para un backtest",
)
async def get_series_for_backtest_endpoint(backtest_id: str) -> SeriesDataResponse:
    """Obtiene la serie de tiempo (OHLC + indicadores) para un backtest dado."""
    try:
        return await get_series_for_backtest(backtest_id)
    except ValueError as e:
        # Mapear ValueError a errores HTTP apropiados
        msg = str(e)
        if "no encontrado" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        elif "inválido" in msg.lower() or "formato" in msg.lower():
            raise HTTPException(status_code=400, detail=msg)
        else:
            raise HTTPException(status_code=422, detail=msg)
