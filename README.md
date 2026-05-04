# Crypto Analysis

Plataforma de analisis tecnico y backtesting para crypto con dos modos principales:

- Flujo CLI interactivo para analisis y ejecucion manual.
- API FastAPI para correr backtests por HTTP y consultar historico.

El proyecto descarga velas de Binance, calcula indicadores (EMA, ADX, SMI, S/R), persiste en MongoDB y ejecuta un simulador long con observabilidad completa (`alerts_feed` + `signals_timeline`).

## Tabla de contenidos

- [Arquitectura](#arquitectura)
- [Requisitos](#requisitos)
- [Configuracion](#configuracion)
- [Instalacion](#instalacion)
- [Quickstart](#quickstart)
- [Uso por CLI](#uso-por-cli)
- [Uso por API](#uso-por-api)
- [Colecciones MongoDB](#colecciones-mongodb)
- [Parametros de estrategia](#parametros-de-estrategia)
- [Troubleshooting](#troubleshooting)
- [Estructura del proyecto](#estructura-del-proyecto)

## Arquitectura

1. Ingestion:
    `scripts/save_analysis` llama a Binance (`services/binance.py`) y construye candles + indicadores.
2. Persistencia:
    Se guardan candles e indicadores por coleccion en MongoDB.
3. Backtest:
    `scripts/run_backtest` (CLI) o `POST /api/backtests/run` (API) leen candles desde Mongo, generan senales y ejecutan simulacion.
4. Observabilidad:
    Se construyen y persisten `alerts_feed` y `signals_timeline` junto con el resultado.
5. Reporte:
    En CLI se genera PDF del grafico y el nombre queda persistido en `report_pdf_filename`.

## Requisitos

- Python 3.10+
- MongoDB accesible desde la maquina de ejecucion
- Dependencias del proyecto instaladas

## Configuracion

Crear un archivo `.env` en la raiz del proyecto con:

```env
MONGO_URI=mongodb://localhost:27017
BINANCE_API=https://api.binance.com/api/v3/
BACKTEST_PDF_DIR=reports/backtests
```

Notas:

- `MONGO_URI` es obligatorio para scripts y API.
- `BINANCE_API` debe terminar en `/api/v3/`.
- `BACKTEST_PDF_DIR` es opcional (default: `reports/backtests`).

## Instalacion

```bash
# Clonar el repositorio

# Desde la raíz del proyecto, crear entorno virtual
python3 -m venv venv

# Activarlo
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Instalar el proyecto en modo editable
pip install -e .
```

## Quickstart

1. Cargar candles + indicadores en MongoDB.
2. Correr backtest (CLI o API).

```bash
source venv/bin/activate
python -m scripts.save_analysis
python -m scripts.run_backtest
```

Si preferis API:

```bash
source venv/bin/activate
python -m scripts.save_analysis
uvicorn fastapi dev
```

## Uso por CLI

### 1) Pipeline de analisis y guardado

```bash
python -m scripts.save_analysis
```

Este script:

- Descarga velas desde Binance (`/klines`, limite maximo por request: 1000).
- Calcula tendencias, EMAs (10/55/200), ADX, SMI y niveles S/R.
- Hace upsert en colecciones de analisis y guarda un `analysis` consolidado.

### 2) Backtest interactivo

```bash
python -m scripts.run_backtest
```

Flujo del backtest CLI:

1. Lee candles desde MongoDB para el rango ingresado.
2. Genera senales EMA(10/55) + filtros (slope, gap, ADX/DI).
3. Ejecuta simulacion long.
4. Construye `alerts_feed` y `signals_timeline`.
5. Genera grafico PDF.
6. Guarda el resultado completo en `backtests` (incluyendo `report_pdf_filename`).

## Uso por API

### Levantar servidor

```bash
fastapi dev
```

### Probar endpoints sin Bash

Con FastAPI ya tenes documentacion interactiva:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

Tambien podes probar los endpoints en Postman importando la spec OpenAPI desde:

- `http://localhost:8000/openapi.json`

### Endpoints

- `POST /api/backtests/run`: corre un backtest nuevo usando candles ya persistidas.
- `GET /api/backtests?limit=20`: lista backtests guardados.
- `GET /api/backtests/{backtest_id}`: obtiene un backtest por id.

### Body JSON minimo (para Swagger o Postman)

```json
{
    "symbol": "BTCUSDT",
    "interval": "4h",
    "start_time": "2026-03-01",
    "end_time": null,
    "min_slope_pct": 0.11,
    "exit_slope_periods": 2,
    "ema_gap_min_pct": 0.0,
    "adx_min": 23,
    "adx_require_di": true,
    "adx_require_rising": false,
    "leverage": 1,
    "initial_capital": 100000
}
```

### Body JSON completo (para Swagger o Postman)

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
    "min_slope_pct": 0.11,
    "exit_slope_periods": 2,
    "ema_gap_min_pct": 0.0,
    "adx_min": 23,
    "adx_require_di": true,
    "adx_require_rising": false,
    "atr_period": 14,
    "atr_stop_mult": 1.8,
    "atr_trailing_mult": 2.2
}
```

## Colecciones MongoDB

El proyecto utiliza estas colecciones:

- `candles`
- `trends`
- `ema_snapshots`
- `adx_snapshots`
- `smi_snapshots`
- `sr_levels`
- `analysis`
- `backtests`

En `backtests` se persisten:

- Metricas agregadas de performance.
- Lista de `trades`.
- `config` de ejecucion.
- `alerts_feed` (mensajes narrativos de eventos).
- `signals_timeline` (debug detallado de condiciones por vela relevante).
- `report_pdf_filename` (cuando aplica en CLI).

## Parametros de estrategia

Los parametros mas importantes para controlar calidad/frecuencia de senales son:

- `min_slope_pct`: pendiente minima de EMA10 para validar entrada.
- `ema_gap_min_pct`: gap minimo entre EMA10 y EMA55.
- `adx_min`: fuerza minima de tendencia.
- `adx_require_di`: exige `+DI > -DI` en entrada.
- `adx_require_rising`: exige ADX no decreciente.
- `exit_slope_periods`: confirma salida por pendiente negativa sostenida.

Regla practica:

- Subir filtros (`min_slope_pct`, `ema_gap_min_pct`, `adx_min`) reduce cantidad de operaciones y prioriza calidad.

## Troubleshooting

### 404 al correr `POST /api/backtests/run`

No hay candles en Mongo para ese rango. Ejecuta primero:

```bash
python -m scripts.save_analysis
```

### Error de conexion a MongoDB

- Verifica `MONGO_URI` en `.env`.
- Verifica que Mongo este levantado y accesible.

### No se guarda nombre de PDF

En flujo CLI actual, el guardado del backtest ocurre despues de generar el PDF, por lo que `report_pdf_filename` queda persistido en una sola insercion.

### Rango largo trae menos velas de las esperadas

`/klines` de Binance tiene limite por request (`limit <= 1000`). Si necesitas ventanas mas largas, hay que paginar por rango de tiempo.

## Estructura del proyecto

```text
crypto_analysis/
├── API/                # FastAPI (routers, schemas, servicios)
├── backtesting/        # Estrategias, simulador, reportes, alertas
├── dashboard/          # Visualizaciones
├── database/           # Conexion y repositorio MongoDB
├── indicators/         # Indicadores tecnicos
├── scripts/            # Entrypoints CLI
├── services/           # Integraciones externas (Binance)
├── utils/              # Helpers de parsing/conversion
├── requirements.txt
└── pyproject.toml
```