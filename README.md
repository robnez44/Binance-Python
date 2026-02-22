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
│   └── prices.py             # Descarga y visualizacion de precios desde Binance
├── utils/
│   └── utils.py              # Funciones auxiliares
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Uso

```bash
# Ejecutar el detector de tendencias
python scripts/classify_trends.py
```

### Salida esperada

Una tabla con las tendencias detectadas:

```
 #  Régimen   Inicio →    Fin  Length       a   pct_slope       R²
──────────────────────────────────────────────────────────────────────
 1  DOWN           0 →     11      12  -5.12    -0.052%    0.9521
 2  UP            12 →     17       6  +3.45    +0.031%    0.8834
 3  SIDE          18 →     29      12  +0.12    +0.001%    0.2183
```

Y un gráfico con:
- Serie completa de precios
- Zonas sombreadas (verde = UP, rojo = DOWN, gris = SIDE)
- Recta de regresión sobre cada segmento