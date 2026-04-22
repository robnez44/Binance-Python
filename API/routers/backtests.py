from __future__ import annotations

from typing import List, Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query

from API.schemas.backtest import BacktestRequest, BacktestResponse
from API.services.backtest_service import execute_backtest
from database.database import get_db
from database.repository import get_backtests

router = APIRouter()

def _doc_to_response(doc: dict) -> BacktestResponse:
    """
    Convierte un documento de MongoDB (con _id ObjectId y trades como lista
    de dicts) a un BacktestResponse completamente tipado.
    """
    from API.schemas.backtest import TradeResponse, BacktestConfigResponse

    raw_trades: list[dict] = doc.get("trades", [])
    trades: list[TradeResponse] = [
        TradeResponse(
            entry_time=t["entry_time"],
            exit_time=t["exit_time"],
            side=t["side"],
            entry_price=float(t["entry_price"]),
            exit_price=float(t["exit_price"]),
            quantity=float(t["quantity"]),
            pnl=float(t["pnl"]),
            return_pct=float(t["return_pct"]),
            candles_held=int(t["candles_held"]),
            exit_reason=t["exit_reason"],
            equity_before=float(t["equity_before"]),
            equity_after=float(t["equity_after"]),
        )
        for t in raw_trades
    ]

    raw_config: Optional[dict] = doc.get("config")
    config: Optional[BacktestConfigResponse] = None
    if raw_config:
        config = BacktestConfigResponse(
            initial_capital=float(raw_config["initial_capital"]),
            leverage=float(raw_config["leverage"]),
            stop_loss_pct=raw_config.get("stop_loss_pct"),
            take_profit_pct=raw_config.get("take_profit_pct"),
            breakeven_trigger_pct=raw_config.get("breakeven_trigger_pct"),
            min_slope_pct=float(raw_config["min_slope_pct"]),
            exit_slope_periods=int(raw_config["exit_slope_periods"]),
            ema_gap_min_pct=float(raw_config.get("ema_gap_min_pct", 0.0)),
            adx_min=float(raw_config.get("adx_min", 0.0)),
            adx_require_di=bool(raw_config.get("adx_require_di", True)),
            adx_require_rising=bool(raw_config.get("adx_require_rising", False)),
            atr_period=int(raw_config.get("atr_period", 14)),
            atr_stop_mult=raw_config.get("atr_stop_mult"),
            atr_trailing_mult=raw_config.get("atr_trailing_mult"),
            atr_stop_confirm_on_close=bool(raw_config.get("atr_stop_confirm_on_close", True)),
        )

    return BacktestResponse(
        id=str(doc["_id"]),
        symbol=doc["symbol"],
        interval=doc["interval"],
        strategy_name=doc["strategy_name"],
        start_time=doc.get("start_time"),
        end_time=doc.get("end_time"),
        created_at=doc.get("created_at"),
        initial_capital=float(doc["initial_capital"]),
        final_capital=float(doc["final_capital"]),
        total_return_pct=float(doc["total_return_pct"]),
        max_drawdown_pct=float(doc["max_drawdown_pct"]),
        total_trades=int(doc["total_trades"]),
        winning_trades=int(doc["winning_trades"]),
        losing_trades=int(doc["losing_trades"]),
        win_rate_pct=float(doc["win_rate_pct"]),
        profit_factor=float(doc["profit_factor"]),
        avg_trade_return_pct=float(doc["avg_trade_return_pct"]),
        trades=trades,
        config=config,
    )

# ══════════════════════════════════════════════════════════════════════════════
#  POST /api/backtests/run
# ══════════════════════════════════════════════════════════════════════════════
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

# ══════════════════════════════════════════════════════════════════════════════
#  GET /api/backtests
# ══════════════════════════════════════════════════════════════════════════════
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

    return [_doc_to_response(doc) for doc in docs]

# ══════════════════════════════════════════════════════════════════════════════
#  GET /api/backtests/{backtest_id}
# ══════════════════════════════════════════════════════════════════════════════
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

    return _doc_to_response(doc)