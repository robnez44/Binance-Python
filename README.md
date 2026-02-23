# Crypto Project

## Requisitos

- Python 3.10+

## Instalación

```bash
# Clonar el repositorio

# Crear entorno virtual
python -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Instalar el proyecto en modo editable
pip install -e .
```

## Estructura del proyecto

```
Binance-Python/
├── models/
│   └── metrics.py            # Dataclass SegmentMetrics
├── scripts/
│   ├── classify_trends.py    # Detección y gráfico de tendencias
│   ├── dashboard.py           # Vista combinada: tendencias + EMAs + pendientes
│   ├── ema_analysis.py       # Cálculo y gráfico de EMAs con pendiente
│   └── prices.py             # Descarga y visualización de precios desde Binance
├── services/
│   └── binance.py            # Cliente de la API de Binance
├── utils/
│   └── utils.py              # Funciones auxiliares
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Uso

```bash
# Ejecutar el detector de tendencias
python -m scripts.classify_trends

# Ejecutar descarga de precios
python -m scripts.prices

# Ejecutar análisis de EMAs
python -m scripts.ema_analysis

# Ejecutar dashboard combinado
python -m scripts.dashboard
```

### Salida esperada

#### classify_trends.py

Una tabla con las tendencias detectadas:

```
 #  Régimen  Inicio →    Fin  Long    P.Inicio     P.Final             a   pct_slope        R²  Rango temporal
──────────────────────────────────────────────────────────────────────────────────────────────────────────────────
 1  DOWN          0 →      9    10    98234.50    95123.80    -1160.4064    -1.6143%    0.9521  2026/02/04 07:59 → 2026/02/05 19:59
 2  UP           10 →     18     9    95500.20    97800.10     +941.8293    +1.3953%    0.7276  2026/02/05 23:59 → 2026/02/07 07:59
 3  SIDE         19 →     32    14    97650.00    97890.30     +117.0872    +0.1675%    0.2183  2026/02/07 11:59 → 2026/02/09 15:59
```

Y un gráfico con:
- Serie completa de precios
- Zonas sombreadas (verde = UP, rojo = DOWN, gris = SIDE)
- Recta de regresión sobre cada segmento

#### ema_analysis.py

Información de las EMAs:

```
Total de velas: 48
  EMA  10:  Ultimo valor =     96542.30   Pendiente = +0.1523 %   Δ slope = +146.92 USDT
  EMA  50:  Ultimo valor =     97010.85   Pendiente = +0.0312 %   Δ slope = +30.27 USDT
  EMA 200:  Ultimo valor =     97250.40   Pendiente = +0.0078 %   Δ slope = +7.58 USDT
```

Y un gráfico con dos subplots:
- **Superior**: precio de cierre + EMAs superpuestas
- **Inferior**: pendiente de cada EMA (cambio porcentual vela a vela)

#### dashboard.py

Combina todo en una sola ejecución (descarga datos una vez). Muestra:
- Tabla completa de tendencias
- Información de EMAs con pendiente porcentual y absoluta
- Gráfico con 3 subplots:
  1. Precio + tendencias (zonas sombreadas + rectas de regresión)
  2. Precio + EMAs (10, 50, 200)
  3. Pendientes de las EMAs