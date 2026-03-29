# Crypto Analysis

## Requisitos

- Python 3.10+

## Instalación

```bash
# Clonar el repositorio

# Crear entorno virtual
python -m venv venv

# Desde la raíz del proyecto
python3 -m venv venv

# Activarlo
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Instalar el proyecto en modo editable
pip install -e .
```

## Qué hace el proyecto

- Descarga velas OHLCV desde Binance
- Calcula EMAs de 10, 55 y 200 periodos
- Calcula ADX
- Calcula SMI / Squeeze Momentum
- Detecta tendencias por segmentos
- Detecta soportes y resistencias por fractales con tolerancia basada en ATR
- Cuenta cuántas velas tocan cada nivel S/R para medir su fuerza
- Ejecuta backtesting long (EMA 10/55)
- Guarda velas, indicadores y análisis completos en MongoDB
- Guarda resultados de backtesting (trades + métricas) en MongoDB
- Genera gráficos combinados y gráficos específicos de soportes/resistencias

## Estructura actual del proyecto

```
crypto_analysis/
├── backtesting/
│   ├── metrics.py            # Métricas: retorno, win rate, profit factor, max drawdown
│   ├── records.py            # Dataclasses: BacktestConfig, Trade, StrategySignals, BacktestResult
│   ├── simulator.py          # Motor de simulación (ejecución al open siguiente)
│   └── strategies.py         # Estrategia EMA 10/55
├── dashboard/
│   ├── chart_full.py         # Gráfico completo: velas + EMAs + S/R + tendencias + SMI + ADX
│   ├── chart_sr.py           # Gráfico standalone de velas + soportes/resistencias
│   └── dashboard.py          # Vista combinada original (tendencias + EMAs + pendientes)
├── database/
│   ├── __init__.py
│   ├── database.py           # Conexión a MongoDB
│   ├── repository.py         # Persistencia, índices y upserts
│   └── schemas.py            # Dataclasses: Candle, trends, EMA, ADX, SMI, SR, AnalysisRecord
├── indicators/
│   ├── adx.py                # Cálculo de ADX y snapshots
│   ├── emas.py               # Cálculo de EMAs y snapshots
│   ├── levels.py             # Detección de soportes y resistencias con ATR y conteo de toques
│   ├── prices.py             # Descarga y gráfico simple de precios
│   └── smi.py                # Cálculo de Squeeze Momentum Indicator (SMI)
├── scripts/
│   ├── classify_trends.py    # Detección y visualización de tendencias
│   ├── run_backtest.py       # Backtesting long + resumen + gráfico + guardado en MongoDB
│   └── save_analysis.py      # Pipeline completo + guardado en MongoDB
├── services/
│   └── binance.py            # Cliente de Binance
├── utils/
│   ├── __init__.py
│   └── utils.py              # Conversión de datos y utilidades de fechas/parámetros
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Cómo ejecutar

Activa el entorno virtual antes de correr cualquier módulo:

```bash
source venv/bin/activate
```

### Gráficos y análisis

```bash
# Detección y gráfico de tendencias
python -m scripts.classify_trends

# Dashboard original: tendencias + EMAs + pendientes
python -m dashboard.dashboard

# Gráfico completo: velas + EMAs + S/R + tendencias + SMI + ADX
python -m dashboard.chart_full

# Gráfico velas + soportes/resistencias
python -m dashboard.chart_sr
```

### Pipeline de guardado

```bash
# Descarga velas, calcula tendencias, EMAs, ADX, SMI, S/R
# y guarda todo en MongoDB
python -m scripts.save_analysis
```

### Backtesting

```bash
# Ejecuta backtesting long (EMA 10/55), imprime resumen detallado,
# grafica trades/equity y guarda el resultado en MongoDB
python -m scripts.run_backtest
```

Notas de uso para backtesting:

- `scripts.run_backtest` lee velas desde MongoDB (`candles`) en el rango indicado.
- Si no hay velas para el rango, primero ejecuta `python -m scripts.save_analysis`.
- El script pide parámetros interactivos: símbolo, temporalidad, rango UTC,
  breakeven, pendiente mínima y ajustes de filtro de tendencia/riesgo adaptativo.

### Módulos de indicadores

```bash
# EMAs y pendientes
python -m indicators.emas

# Descarga y gráfico básico de precios
python -m indicators.prices
```

## Persistencia en MongoDB

El pipeline guarda información en colecciones separadas para poder consultar o reconstruir el análisis después:

- `candles`
- `trends`
- `ema_snapshots`
- `adx_snapshots`
- `smi_snapshots`
- `sr_levels`
- `analysis`
- `backtests`

`AnalysisRecord` incluye el análisis consolidado del rango, junto con velas, tendencias, EMAs, ADX, SMI y soportes/resistencias.

La colección `backtests` guarda cada ejecucion con:

- configuración usada (`BacktestConfig`)
- lista completa de operaciones (`trades`)
- métricas agregadas (capital final, retorno, win rate, profit factor, max drawdown)

## Notas

- Los scripts interactivos piden símbolo, temporalidad y rango de fechas en UTC.
- `scripts.save_analysis` requiere una conexión a MongoDB configurada.
- `scripts.run_backtest` también requiere MongoDB y datos de velas previamente guardados.