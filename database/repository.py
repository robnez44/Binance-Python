from dataclasses import asdict
from datetime import datetime, timezone
from typing import List, Dict

from pymongo import UpdateOne

from database.database import get_db
from database.schemas import (
    Candle, SegmentMetrics, EMASnapshot, ADXSnapshot, SMISnapshot, AnalysisRecord,
)


# ──────────────────────────────────────────────────────────────────────────── #
#  Índices únicos
# ──────────────────────────────────────────────────────────────────────────── #

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

    await db.analysis.create_index(
        [("symbol", 1), ("interval", 1), ("start_time", 1), ("end_time", 1)],
        unique=True,
        name="uq_analysis",
    )

    print("Índices verificados / creados.")


# ──────────────────────────────────────────────────────────────────────────── #
#  Candles
# ──────────────────────────────────────────────────────────────────────────── #

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


# ──────────────────────────────────────────────────────────────────────────── #
#  Trends
# ──────────────────────────────────────────────────────────────────────────── #

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


# ──────────────────────────────────────────────────────────────────────────── #
#  EMA Snapshots
# ──────────────────────────────────────────────────────────────────────────── #

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


# ──────────────────────────────────────────────────────────────────────────── #
#  ADX Snapshots
# ──────────────────────────────────────────────────────────────────────────── #

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


# ──────────────────────────────────────────────────────────────────────────── #
#  SMI Snapshots
# ──────────────────────────────────────────────────────────────────────────── #

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


# ──────────────────────────────────────────────────────────────────────────── #
#  Analysis Record (documento completo con trends + EMAs + ADX + SMI embebidos)
# ──────────────────────────────────────────────────────────────────────────── #

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
