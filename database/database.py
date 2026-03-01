from pymongo import AsyncMongoClient
from dataclasses import asdict
from datetime import datetime, timezone
from typing import List, Optional
from database.schemas import AnalysisRecord
from dotenv import load_dotenv
import os

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

_client: Optional[AsyncMongoClient] = None
_db = None

async def connectDB():
    global _client, _db
    try:
        _client = AsyncMongoClient(MONGO_URI)
        _db = _client["crypto_data"]
        await _db.command("ping")
        print("Connected to MongoDB")
    except Exception as e:
        print(f"Error conectando a MongoDB: {e}")
        _client = None
        _db = None
        raise

async def disconnect():
    global _client
    try:
        if _client:
            await _client.close()
            print("MongoDB desconectado")
    except Exception as e:
        print(f"Error desconectando: {e}")
        raise

def get_db():
    if _db is None:
        raise RuntimeError("No hay conexión a MongoDB. Llama a connect() primero.")
    return _db

