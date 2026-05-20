from dataclasses import asdict
from datetime import datetime, timezone
from typing import List, Dict, Optional
from bson import ObjectId
from pymongo import UpdateOne
from database.database import get_db
from database.schemas import (
    Candle, SegmentMetrics, EMASnapshot, ADXSnapshot, SMISnapshot, SRLevel, AnalysisRecord,
)
from utils.utils import backtest_result_to_dict

def _strip_id(doc: Dict) -> Dict:
    return {k: v for k, v in doc.items() if k != "_id"}

#  Índices únicos
async def ensure_indexes() -> None:
    """Crea los índices únicos."""
    db = get_db()

    await db.candles.create_index(
        [("symbol", 1), ("interval", 1), ("open_time", 1)],
        unique=True,
        name="uq_candle",
    )

    await db.trends.create_index(
        [("symbol", 1), ("interval", 1), ("start_time", 1), ("end_time", 1)],
        unique=True,
        name="uq_trend",
    )

    await db.ema_snapshots.create_index(
        [("symbol", 1), ("interval", 1), ("timestamp", 1), ("span", 1)],
        unique=True,
        name="uq_ema_snap",
    )

    await db.adx_snapshots.create_index(
        [("symbol", 1), ("interval", 1), ("timestamp", 1)],
        unique=True,
        name="uq_adx_snap",
    )

    await db.smi_snapshots.create_index(
        [("symbol", 1), ("interval", 1), ("timestamp", 1)],
        unique=True,
        name="uq_smi_snap",
    )

    await db.sr_levels.create_index(
        [("symbol", 1), ("interval", 1), ("timestamp", 1), ("level_type", 1)],
        unique=True,
        name="uq_sr_level",
    )

    await db.analysis.create_index(
        [("symbol", 1), ("interval", 1), ("start_time", 1), ("end_time", 1)],
        unique=True,
        name="uq_analysis",
    )

    print("Índices verificados / creados.")

#  Candles
async def save_candles(candles: List[Candle]) -> int:
    """Guarda/actualiza candles. Retorna documentos afectados."""
    if not candles:
        return 0

    db = get_db()
    ops = []
    for candle in candles:
        doc = asdict(candle)
        ops.append(UpdateOne(
            {
                "symbol": doc["symbol"],
                "interval": doc["interval"],
                "open_time": doc["open_time"],
            },
            {"$set": doc},
            upsert=True,
        ))

    result = await db.candles.bulk_write(ops, ordered=False)
    return result.upserted_count + result.modified_count

async def get_candles(
    symbol: str,
    interval: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> List[Candle]:
    """Obtiene candles ordenadas por `open_time` desde MongoDB."""
    db = get_db()
    query = {
        "symbol": symbol,
        "interval": interval,
    }

    if start_time or end_time:
        query["open_time"] = {}
        if start_time:
            query["open_time"]["$gte"] = start_time
        if end_time:
            query["open_time"]["$lte"] = end_time

    docs = await db.candles.find(query).sort("open_time", 1).to_list(length=None)
    return [
        Candle(**{k: v for k, v in doc.items() if k != "_id"})
        for doc in docs
    ]

async def get_trends_for_range(
    symbol: str,
    interval: str,
    start_time: datetime,
    end_time: datetime,
) -> List[Dict]:
    db = get_db()
    query = {
        "symbol": symbol,
        "interval": interval,
        "start_time": {"$lte": end_time},
        "end_time": {"$gte": start_time},
    }
    docs = await db.trends.find(query).sort([("start_time", 1), ("end_time", 1)]).to_list(length=None)
    return [_strip_id(doc) for doc in docs]

#  Trends
async def save_trends(trends: List[SegmentMetrics]) -> int:
    """Guarda/actualiza tendencias. Retorna documentos afectados."""
    if not trends:
        return 0

    db = get_db()
    ops = []
    for trend in trends:
        doc = asdict(trend)
        ops.append(UpdateOne(
            {
                "symbol": doc["symbol"],
                "interval": doc["interval"],
                "start_time": doc["start_time"],
                "end_time": doc["end_time"],
            },
            {"$set": doc},
            upsert=True,
        ))

    result = await db.trends.bulk_write(ops, ordered=False)
    return result.upserted_count + result.modified_count

#  EMA Snapshots
async def save_ema_snapshots(snapshots: List[EMASnapshot]) -> int:
    """Guarda/actualiza snapshots EMA. Retorna documentos afectados."""
    if not snapshots:
        return 0

    db = get_db()
    ops = []
    for snap in snapshots:
        doc = asdict(snap)
        ops.append(UpdateOne(
            {
                "symbol": doc["symbol"],
                "interval": doc["interval"],
                "timestamp": doc["timestamp"],
                "span": doc["span"],
            },
            {"$set": doc},
            upsert=True,
        ))

    result = await db.ema_snapshots.bulk_write(ops, ordered=False)
    return result.upserted_count + result.modified_count

async def get_ema_snapshots_for_range(
    symbol: str,
    interval: str,
    start_time: datetime,
    end_time: datetime,
) -> List[Dict]:
    db = get_db()
    query = {
        "symbol": symbol,
        "interval": interval,
        "timestamp": {"$gte": start_time, "$lte": end_time},
    }
    docs = await db.ema_snapshots.find(query).sort([("span", 1), ("timestamp", 1)]).to_list(length=None)
    return [_strip_id(doc) for doc in docs]

#  ADX Snapshots
async def save_adx_snapshots(snapshots: List[ADXSnapshot]) -> int:
    """Guarda/actualiza snapshots ADX. Retorna documentos afectados."""
    if not snapshots:
        return 0

    db = get_db()
    ops = []
    for snap in snapshots:
        doc = asdict(snap)
        ops.append(UpdateOne(
            {
                "symbol": doc["symbol"],
                "interval": doc["interval"],
                "timestamp": doc["timestamp"],
            },
            {"$set": doc},
            upsert=True,
        ))

    result = await db.adx_snapshots.bulk_write(ops, ordered=False)
    return result.upserted_count + result.modified_count

async def get_adx_snapshots_for_range(
    symbol: str,
    interval: str,
    start_time: datetime,
    end_time: datetime,
) -> List[Dict]:
    db = get_db()
    query = {
        "symbol": symbol,
        "interval": interval,
        "timestamp": {"$gte": start_time, "$lte": end_time},
    }
    docs = await db.adx_snapshots.find(query).sort("timestamp", 1).to_list(length=None)
    return [_strip_id(doc) for doc in docs]

#  SMI Snapshots
async def save_smi_snapshots(snapshots: List[SMISnapshot]) -> int:
    """Guarda/actualiza snapshots SMI. Retorna documentos afectados."""
    if not snapshots:
        return 0

    db = get_db()
    ops = []
    for snap in snapshots:
        doc = asdict(snap)
        ops.append(UpdateOne(
            {
                "symbol": doc["symbol"],
                "interval": doc["interval"],
                "timestamp": doc["timestamp"],
            },
            {"$set": doc},
            upsert=True,
        ))

    result = await db.smi_snapshots.bulk_write(ops, ordered=False)
    return result.upserted_count + result.modified_count

async def get_smi_snapshots_for_range(
    symbol: str,
    interval: str,
    start_time: datetime,
    end_time: datetime,
) -> List[Dict]:
    db = get_db()
    query = {
        "symbol": symbol,
        "interval": interval,
        "timestamp": {"$gte": start_time, "$lte": end_time},
    }
    docs = await db.smi_snapshots.find(query).sort("timestamp", 1).to_list(length=None)
    return [_strip_id(doc) for doc in docs]

#  S/R Levels
async def save_sr_levels(levels: List[SRLevel]) -> int:
    """Guarda/actualiza niveles S/R. Retorna documentos afectados."""
    if not levels:
        return 0

    db = get_db()
    ops = []
    for lvl in levels:
        doc = asdict(lvl)
        ops.append(UpdateOne(
            {
                "symbol": doc["symbol"],
                "interval": doc["interval"],
                "timestamp": doc["timestamp"],
                "level_type": doc["level_type"],
            },
            {"$set": doc},
            upsert=True,
        ))

    result = await db.sr_levels.bulk_write(ops, ordered=False)
    return result.upserted_count + result.modified_count

async def get_sr_levels_for_range(
    symbol: str,
    interval: str,
    start_time: datetime,
    end_time: datetime,
) -> List[Dict]:
    db = get_db()
    query = {
        "symbol": symbol,
        "interval": interval,
        "timestamp": {"$gte": start_time, "$lte": end_time},
    }
    docs = await db.sr_levels.find(query).sort([("timestamp", 1), ("level_type", 1)]).to_list(length=None)
    return [_strip_id(doc) for doc in docs]

#  Analysis Record (completo con trends + EMAs + ADX + SMI + S/R embebidos)
async def save_analysis(record: AnalysisRecord) -> str:
    """Guarda/actualiza el AnalysisRecord completo. Retorna el _id."""
    db = get_db()
    doc = asdict(record)
    doc["created_at"] = datetime.now(timezone.utc)

    result = await db.analysis.update_one(
        {
            "symbol": doc["symbol"],
            "interval": doc["interval"],
            "start_time": doc["start_time"],
            "end_time": doc["end_time"],
        },
        {"$set": doc},
        upsert=True,
    )

    return str(result.upserted_id or "updated")

async def get_analysis_for_range(
    symbol: str,
    interval: str,
    start_time: datetime,
    end_time: datetime,
) -> Optional[Dict]:
    """Busca un analysis que cubra el rango pedido (o exacto), priorizando el más reciente."""
    db = get_db()

    covering_query = {
        "symbol": symbol,
        "interval": interval,
        "start_time": {"$lte": start_time},
        "end_time": {"$gte": end_time},
    }
    doc = await db.analysis.find_one(covering_query, sort=[("created_at", -1)])
    if doc is not None:
        return doc

    exact_query = {
        "symbol": symbol,
        "interval": interval,
        "start_time": start_time,
        "end_time": end_time,
    }
    return await db.analysis.find_one(exact_query)

# ══════════════════════════════════════════════════════════════════════════════
#  Backtesting
# ══════════════════════════════════════════════════════════════════════════════

async def save_backtest_result(
    result,
    trade_markers: Optional[List[Dict]] = None,
    series_start_time: Optional[datetime] = None,
    series_end_time: Optional[datetime] = None,
) -> str:
    """
    Guarda un BacktestResult en MongoDB. Retorna el _id del documento insertado.
    """
    db = get_db()
    doc = backtest_result_to_dict(result)
    if trade_markers is not None:
        doc["trade_markers"] = trade_markers
    if series_start_time is not None:
        doc["series_start_time"] = series_start_time
    if series_end_time is not None:
        doc["series_end_time"] = series_end_time
    insert_result = await db.backtests.insert_one(doc)
    return str(insert_result.inserted_id)

async def get_backtests(
    symbol: Optional[str] = None,
    interval: Optional[str] = None,
    strategy_name: Optional[str] = None,
    limit: int = 20,
) -> List[Dict]:
    """
    Obtiene backtests guardados, ordenados por fecha de creación (más reciente primero).

    Parámetros:
    - symbol: filtrar por símbolo (opcional)
    - interval: filtrar por temporalidad (opcional)
    - strategy_name: filtrar por estrategia (opcional)
    - limit: máximo de resultados (default 20)

    Retorna lista de documentos (sin los trades para no sobrecargar).
    """
    db = get_db()
    query = {}

    if symbol:
        query["symbol"] = symbol
    if interval:
        query["interval"] = interval
    if strategy_name:
        query["strategy_name"] = strategy_name

    # Excluir trades del resultado para que sea más ligero
    projection = {"trades": 0}

    docs = await db.backtests.find(
        query, projection
    ).sort("created_at", -1).limit(limit).to_list(length=None)

    return docs
    