# Crypto Analysis

Plataforma de análisis técnico y backtesting para criptoactivos. Descarga velas desde Binance, calcula indicadores, detecta tendencias por regresión lineal, persiste todo en MongoDB y ejecuta simulaciones long con observabilidad completa.

Dos modos de uso:

- **CLI interactivo** — pipeline de análisis, backtests manuales y gráficos locales.
- **API FastAPI** — backtests por HTTP, consulta de histórico y series para visualización externa (p. ej. una UI en React).

---

## Tabla de contenidos

- [Qué hace el proyecto](#qué-hace-el-proyecto)
- [Arquitectura](#arquitectura)
- [Stack tecnológico](#stack-tecnológico)
- [Requisitos](#requisitos)
- [Configuración](#configuración)
- [Instalación](#instalación)
- [Quickstart](#quickstart)
- [Uso por CLI](#uso-por-cli)
- [Uso por API](#uso-por-api)
- [Estrategia de backtesting](#estrategia-de-backtesting)
- [Indicadores](#indicadores)
- [MongoDB](#mongodb)
- [Parámetros de estrategia](#parámetros-de-estrategia)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Troubleshooting](#troubleshooting)

---

## Qué hace el proyecto

1. **Ingesta** — descarga OHLC desde Binance (`/klines`, máx. 1000 velas por request).
2. **Indicadores** — EMA, ADX (+DI/−DI), Squeeze Momentum (SMI), soportes/resistencias y segmentación de tendencias (UP / DOWN / SIDE) vía regresión lineal con R².
3. **Persistencia** — guarda candles, snapshots de indicadores y un registro consolidado `analysis` en MongoDB.
4. **Backtesting** — estrategia long basada en cruce EMA 10/55 con filtros opcionales (pendiente, gap, ADX) y gestión de riesgo con stops ATR dinámicos.
5. **Observabilidad** — cada backtest incluye `alerts_feed` (eventos narrativos), `signals_timeline` (debug por vela), `trade_markers` (marcadores para gráficos) y métricas agregadas.
6. **Reportes** — generación de PDF con matplotlib (interactivo en CLI, en background vía API).

---

## Arquitectura

```text
Binance API
    │
    ▼
scripts/save_analysis ──► indicators/ + classify_trends
    │
    ▼
MongoDB (crypto_data)
    │
    ├── scripts/run_backtest (CLI)
    └── API (FastAPI)
            │
            ├── Routers   → validación HTTP, códigos de error
            ├── Services  → orquestación de dominio
            ├── Mappers   → documentos / records → schemas Pydantic
            └── database/repository → acceso a MongoDB
```

### Capas de la API

| Capa | Responsabilidad | Ubicación |
|------|-----------------|-----------|
| Router | Endpoints HTTP, query params, manejo de errores | `API/routers/` |
| Service | Lógica de negocio y orquestación | `API/services/` |
| Repository | Queries y persistencia MongoDB | `database/repository.py` |
| Schema | Contratos request/response (Pydantic) | `API/schemas/` |
| Mapper | Conversión entre dominio y API | `API/mappers/` |

### Flujo de datos

```text
save_analysis  →  candles + trends + snapshots + analysis
run_backtest   →  señales → simulador → backtests (+ PDF)
POST /run      →  mismo motor que CLI, PDF en background
GET /series    →  OHLC + indicadores alineados al rango del backtest
```

---

## Stack tecnológico

- **Python 3.10+**
- **FastAPI** + **Uvicorn** — API REST
- **MongoDB** (driver async `pymongo`) — persistencia
- **NumPy / Pandas** — series temporales
- **Matplotlib** — gráficos y PDFs
- **Pydantic v2** — validación de schemas

---

## Requisitos

- Python 3.10 o superior
- MongoDB accesible desde la máquina de ejecución
- Conexión a internet para la API pública de Binance

---

## Configuración

Crear un archivo `.env` en la raíz del proyecto:

```env
MONGO_URI=mongodb://localhost:27017
BINANCE_API=https://api.binance.com/api/v3/
BACKTEST_PDF_DIR=reports/backtests
```

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `MONGO_URI` | Sí | URI de conexión a MongoDB |
| `BINANCE_API` | Sí | Base URL de Binance; debe terminar en `/api/v3/` |
| `BACKTEST_PDF_DIR` | No | Directorio donde se guardan los PDF (default: `reports/backtests`) |

---

## Instalación

```bash
# Desde la raíz del proyecto
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
pip install -e .
```

---

## Quickstart

```bash
source venv/bin/activate

# 1. Cargar velas e indicadores en MongoDB (interactivo)
python -m scripts.save_analysis

# 2a. Backtest por CLI
python -m scripts.run_backtest

# 2b. O levantar la API
cd API/
fastapi dev
```

Documentación interactiva de la API (con el servidor levantado):

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

---

## Uso por CLI

### `scripts/save_analysis` — pipeline de análisis

Descarga velas, calcula indicadores y persiste en MongoDB.

```bash
python -m scripts.save_analysis
```

El script solicita de forma interactiva: símbolo, intervalo y rango UTC.

**Qué calcula y guarda:**

| Paso | Módulo | Salida |
|------|--------|--------|
| Velas OHLCV | `services/binance.py` | colección `candles` |
| Tendencias (regresión lineal) | `scripts/classify_trends.py` | `trends` |
| EMA 10 y 55 | `indicators/emas.py` | `ema_snapshots` |
| ADX (periodo 14) | `indicators/adx.py` | `adx_snapshots` |
| Squeeze Momentum | `indicators/smi.py` | `smi_snapshots` |
| Soportes / resistencias | `indicators/levels.py` | `sr_levels` |
| Registro consolidado | `database/schemas.py` | `analysis` |

Parámetros internos de tendencias en este script: ventana máxima 10, mínimo 5 velas, R² ≥ 0.65, pendiente mínima 0.05%.

### `scripts/run_backtest` — backtest interactivo

```bash
python -m scripts.run_backtest
```

Flujo:

1. Lee candles desde MongoDB para el rango ingresado.
2. Genera señales EMA(10/55) con filtros configurables.
3. Ejecuta el simulador long (`backtesting/simulator.py`).
4. Construye `alerts_feed` y `signals_timeline`.
5. Imprime resumen, debug de señales y alertas en consola.
6. Abre gráfico interactivo y guarda PDF en `BACKTEST_PDF_DIR`.
7. Persiste el resultado en `backtests` (incluye `report_pdf_filename`, `trade_markers`, `series_start_time`, `series_end_time`).

### Otros scripts

| Script | Propósito |
|--------|-----------|
| `scripts/classify_trends.py` | Algoritmo de segmentación de tendencias; también usable como módulo |
| `dashboard/dashboard.py` | Exploración visual local (EMAs, tendencias) sin persistir |
| `dashboard/chart_full.py`, `chart_sr.py` | Gráficos auxiliares |

---

## Uso por API

### Health check

```http
GET /
```

Respuesta: `{"status": "ok", "message": "Crypto Analysis API running"}`

### Backtests

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/api/backtests/run` | Ejecuta un backtest sobre candles ya persistidas |
| `GET` | `/api/backtests` | Lista backtests (filtros opcionales: `symbol`, `interval`, `strategy_name`, `limit`) |
| `GET` | `/api/backtests/{backtest_id}` | Detalle completo de un backtest (trades, config, alertas, timeline) |

**Diferencia CLI vs API en PDF:** en CLI el PDF se genera antes de guardar; en API el backtest se persiste de inmediato y el PDF se genera en **background** (el campo `report_pdf_filename` se actualiza después).

**Prerequisito:** deben existir candles en MongoDB para el rango solicitado. Si no, `POST /run` responde **404**.

### Series (para gráficos en UI)

```http
GET /api/backtests/{backtest_id}/series
```

Devuelve `SeriesDataResponse`: candles OHLC + tendencias + EMAs + ADX + SMI + niveles S/R alineados al rango del backtest (`series_start_time` → `series_end_time`).

### Estrategias guardadas

Permite persistir configuraciones de backtest reutilizables (independientes de ejecutar un backtest).

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/api/strategies` | Guarda una configuración |
| `GET` | `/api/strategies` | Lista estrategias (`symbol`, `interval`, `limit` opcionales) |
| `GET` | `/api/strategies/{strategy_id}` | Obtiene una estrategia |
| `DELETE` | `/api/strategies/{strategy_id}` | Elimina una estrategia |

### Body JSON — ejemplo mínimo (`POST /api/backtests/run`)

```json
{
  "symbol": "BTCUSDT",
  "interval": "4h",
  "start_time": "2026-03-01",
  "end_time": null,
  "initial_capital": 100000,
  "leverage": 1,
  "min_slope_pct": 0.03,
  "exit_slope_periods": 2,
  "ema_gap_min_pct": 0.5,
  "adx_min": 23,
  "adx_require_di": true
}
```

### Body JSON — ejemplo completo

```json
{
  "symbol": "BTCUSDT",
  "interval": "4h",
  "start_time": "2026-03-01",
  "end_time": null,
  "initial_capital": 100000,
  "leverage": 1,
  "stop_loss_pct": null,
  "take_profit_pct": null,
  "breakeven_trigger_pct": null,
  "min_slope_pct": 0.03,
  "exit_slope_periods": 2,
  "ema_gap_min_pct": 0.5,
  "adx_min": 23,
  "adx_require_di": true,
  "atr_period": 14,
  "atr_stop_mult": 1.8,
  "atr_trailing_mult": 2.2
}
```

### Semántica de porcentajes en la API

| Campo | Formato | Ejemplo |
|-------|---------|---------|
| `stop_loss_pct`, `take_profit_pct`, `breakeven_trigger_pct` | Valor entero = % | `2` → 2% |
| `min_slope_pct`, `ema_gap_min_pct` | Valor directo en % | `0.08` → 0.08% |

Más ejemplos en Swagger (`/docs`) gracias a `API/openapi_examples/backtests_examples.py`.

---

## Estrategia de backtesting

Implementada en `backtesting/strategies.py` → `build_ema_long_signals`.

### Señal base (EMA 10 / 55)

- **Entrada:** cruce alcista EMA10 > EMA55 + pendiente EMA10 ≥ `min_slope_pct` + precio por encima de EMA10. También entradas en tendencia ya establecida si se cumplen pendiente y precio.
- **Salida:** `exit_slope_periods` velas consecutivas con pendiente EMA10 ≤ −`min_slope_pct` y precio por debajo de EMA10.

### Filtros opcionales

| Filtro | Condición |
|--------|-----------|
| Gap EMA | `(EMA10 − EMA55) / EMA55 × 100 ≥ ema_gap_min_pct` |
| ADX | `ADX ≥ adx_min` |
| DI | Si `adx_require_di`: `+DI > −DI` |

El nombre de estrategia persistido es dinámico, p. ej. `ema_modular_10_55_long` o `ema_vertical_10_55_long`.

### Simulador (`backtesting/simulator.py`)

- Posiciones **long**, una a la vez.
- Stops: ATR inicial y trailing ATR (configurables en `BacktestConfig`).
- Métricas finales: retorno total, drawdown máximo, win rate, profit factor, etc. (`backtesting/metrics.py`).

---

## Indicadores

| Indicador | Módulo | Uso |
|-----------|--------|-----|
| EMA + pendiente | `indicators/emas.py` | Señales, snapshots, gráficos |
| ADX, +DI, −DI | `indicators/adx.py` | Filtro de tendencia |
| Squeeze Momentum (SMI) | `indicators/smi.py` | Análisis / visualización |
| ATR | `indicators/atr.py` | Stops dinámicos en backtest |
| Soportes / resistencias | `indicators/levels.py` | Niveles por toques y ATR |
| Tendencias (regresión) | `scripts/classify_trends.py` | Segmentos UP/DOWN/SIDE con R² |

---

### Colecciones

| Colección | Contenido |
|-----------|-----------|
| `candles` | OHLC por símbolo, intervalo y `open_time` |
| `trends` | Segmentos de tendencia (regresión lineal) |
| `ema_snapshots` | Puntos EMA por span (10, 55, …) y timestamp |
| `adx_snapshots` | ADX, +DI, −DI por vela |
| `smi_snapshots` | Squeeze Momentum por vela |
| `sr_levels` | Soportes y resistencias |
| `analysis` | Registro consolidado de un rango analizado |
| `backtests` | Resultados de simulaciones |
| `strategies` | Configuraciones de estrategia guardadas vía API |

### Documento `backtests` — campos principales

- Identificación: `symbol`, `interval`, `strategy_name`, `start_time`, `end_time`, `created_at`
- Métricas: `initial_capital`, `final_capital`, `total_return_pct`, `max_drawdown_pct`, `win_rate_pct`, `profit_factor`, …
- Detalle: `trades[]`, `trade_markers[]`, `config`, `alerts_feed[]`, `signals_timeline[]`
- Series: `series_start_time`, `series_end_time`, `loaded_candles_count`
- Reporte: `report_pdf_filename` (nombre del PDF, no la ruta absoluta)

Los índices únicos se crean al ejecutar `ensure_indexes()` (llamado desde `save_analysis`).

---

## Parámetros de estrategia

Parámetros clave para calidad vs. frecuencia de operaciones:

| Parámetro | Efecto |
|-----------|--------|
| `min_slope_pct` | Pendiente mínima de EMA10 para validar entrada |
| `ema_gap_min_pct` | Separación mínima EMA10–EMA55 (%) |
| `adx_min` | Fuerza mínima de tendencia |
| `adx_require_di` | Exige `+DI > −DI` en entrada |
| `exit_slope_periods` | Velas con pendiente negativa para confirmar salida |
| `atr_stop_mult` / `atr_trailing_mult` | Multiplicadores ATR para stop loss dinámicos |

**Regla práctica:** subir filtros (`min_slope_pct`, `ema_gap_min_pct`, `adx_min`) reduce operaciones y prioriza señales más selectivas.

---

## Estructura del proyecto

```text
crypto_analysis/
├── API/
│   ├── main.py                 # App FastAPI, CORS, lifespan MongoDB
│   ├── routers/                # backtests, series, strategies
│   ├── services/               # Orquestación de dominio
│   ├── schemas/                # Pydantic request/response
│   ├── mappers/                # Conversión records ↔ API
│   ├── utils/                  # Marcadores, rangos temporales, estrategias
│   └── openapi_examples/       # Ejemplos para Swagger
├── backtesting/
│   ├── strategies.py           # Generación de señales
│   ├── simulator.py            # Motor de simulación long
│   ├── metrics.py              # Métricas agregadas
│   ├── alerts.py               # alerts_feed + signals_timeline
│   ├── backtest_plot.py        # Gráfico y export PDF
│   ├── backtest_reporting.py   # Resumen CLI y debug
│   ├── series.py               # Payload de series para API/UI
│   └── records.py              # Dataclasses de dominio
├── database/
│   ├── database.py             # Conexión async MongoDB
│   ├── repository.py           # Capa de acceso a datos
│   └── schemas.py              # Dataclasses de persistencia
├── indicators/                 # EMA, ADX, SMI, ATR, S/R
├── scripts/
│   ├── save_analysis.py        # Pipeline principal de ingestión de velas
│   ├── run_backtest.py         # Backtest CLI
│   └── classify_trends.py      # Segmentación de tendencias
├── services/
│   └── binance.py              # Cliente HTTP Binance /klines
├── dashboard/                  # Visualizaciones exploratorias
├── utils/
│   └── utils.py                # Parsing UTC, prompts CLI
├── reports/                    # PDFs generados (gitignored)
├── requirements.txt
└── pyproject.toml
```

---

## Troubleshooting

### 404 al correr `POST /api/backtests/run`

No hay candles en MongoDB para ese rango. Ejecuta primero:

```bash
python -m scripts.save_analysis
```

Asegúrate de usar el mismo `symbol`, `interval` y un rango temporal cubierto por las velas cargadas.

### Error de conexión a MongoDB

- Verifica `MONGO_URI` en `.env`.
- Confirma que MongoDB esté levantado (`mongosh` o cliente equivalente).
- La API conecta al iniciar (`lifespan` en `API/main.py`); los scripts CLI llaman `connectDB()` explícitamente.

### No aparece `report_pdf_filename` tras correr backtest por API

El PDF se genera en background. Consulta de nuevo `GET /api/backtests/{id}` unos segundos después. Revisa logs del servidor si sigue vacío (errores de matplotlib o permisos en `BACKTEST_PDF_DIR`).

### En CLI el PDF sí se guarda pero no en API

En CLI, `plot_backtest(..., show=True)` corre de forma síncrona antes del insert. En API, la generación es asíncrona y el filename se persiste en un segundo paso.

### Rango largo trae menos velas de las esperadas

El endpoint `/klines` de Binance limita a **1000 velas por request**. Para ventanas más largas hay que paginar por rango de tiempo (no implementado aún en `get_klines`).

### CORS en producción

`API/main.py` tiene `allow_origins=["*"]`. Restringir al dominio del frontend antes de desplegar.
