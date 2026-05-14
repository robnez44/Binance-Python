from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database.database import connectDB, disconnect
from API.routers import backtests
from API.routers import series

# Lifespan
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await connectDB()
    yield
    await disconnect()

app = FastAPI(
    title="Crypto Analysis API",
    description="API para backtesting de estrategias de criptomonedas",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS necesario para que el frontend pueda consumir la API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # cambiar por la URL del frontend en produccion
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(backtests.router, prefix="/api/backtests", tags=["Backtests"])
app.include_router(series.router, prefix="/api/backtests", tags=["Series"])

@app.get("/", tags=["Health"])
def health() -> dict[str, str]:
    return {"status": "ok", "message": "Crypto Analysis API running"}