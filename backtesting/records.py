from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
import numpy as np

@dataclass
class BacktestConfig:
    """
    Parámetros de configuración del backtest.
    Define cómo se ejecuta la simulación.
    """
    initial_capital:        float = 10_000.0        # Capital inicial en USDT
    leverage:               float = 1.0             # Apalancamiento usado en cada operación. 1.0 = sin apalancamiento
    stop_loss_pct:          Optional[float] = 0.02  # Stop Loss: si el precio cae este %, se cierra la posición
    take_profit_pct:        Optional[float] = 0.04  # Take Profit: si el precio sube este %, se cierra con ganancia (0.04 = 4%). None = sin take profit
    breakeven_trigger_pct:  Optional[float] = None  # Breakeven: cuando el precio sube este % desde la entrada, el stop se mueve al precio de entrada (riesgo cero).
    min_slope_pct:          float = 0.08            # Pendiente mínima de EMA 10 (en %) para validar señales
    exit_slope_periods:     int = 2                 # Velas consecutivas con pendiente negativa para confirmar salida

@dataclass
class Trade:
    """
    Representa una operación completa (entrada + salida).
    Se crea cuando se cierra una posición.
    """
    entry_time:     datetime    # Fecha/hora de entrada (cuando se compró)
    exit_time:      datetime    # Fecha/hora de salida (cuando se vendió)
    side:           str         # Tipo de operación: "long" o "short"
    entry_index:    int         # Índice de la vela donde entró (para referencia en el array de candles)
    exit_index:     int         # Indice de la vela donde salió
    entry_price:    float       # Precio al que se compró 
    exit_price:     float       # Precio al que se vendió 
    quantity:       float       # Cantidad de activo comprado (ej: 0.15 BTC)
    pnl:            float       # Ganancia o pérdida neta en USDT (después de comisiones)
    return_pct:     float       # Retorno porcentual
    candles_held:   int         # Cuantas velas duró la posición abierta
    exit_reason:    str         # Por que salio: stop loss, take profit, señal de salida o fin de datos
    equity_before:  float       # Capital que se tenía antes de este trade
    equity_after:   float       # Capital que se tiene después de este trade (equity_before + pnl)

@dataclass
class StrategySignals:
    """
    Señales de la estrategia para cada vela.
    Generadas por una función de estrategia (ej: ema_cross_long_strategy).
    """
    entry_long: np.ndarray  # Array booleano: True en velas donde hay señal de compra
    exit_long:  np.ndarray  # Array booleano: True en velas donde hay señal de venta
    ema_fast:   np.ndarray  # Valores de la EMA rápida (para debug/gráficos)
    ema_slow:   np.ndarray  # Valores de la EMA lenta (para debug/gráficos)
    name:       str = ""    # Nombre de la estrategia (ej: "ema_cross_long", "adx_smi_strategy", etc.)

@dataclass
class BacktestResult:
    """
    Resultado final del backtest con todas las métricas.
    Es lo que se guarda en MongoDB y se muestra en consola.
    """
    # Identificadores del backtest (para MongoDB)
    symbol:                 str = ""                                    # "BTCUSDT"
    interval:               str = ""                                    # "4h", "1d"
    start_time:             Optional[datetime] = None                   # Inicio del rango testeado
    end_time:               Optional[datetime] = None                   # Fin del rango testeado
    trades:                 List[Trade] = field(default_factory=list)   # Lista de todos los trades ejecutados
    initial_capital:        float = 0.0                                 # Capital inicial usado
    final_capital:          float = 0.0                                 # Capital final después de cerrar todas las posiciones
    total_return_pct:       float = 0.0                                 # Retorno total en % ((final - inicial) / inicial * 100)
    total_trades:           int = 0                                     # Cantidad total de operaciones ejecutadas
    winning_trades:         int = 0                                     # Operaciones donde pnl > 0 (ganadoras)
    losing_trades:          int = 0                                     # Operaciones donde pnl < 0 (perdedoras)
    win_rate_pct:           float = 0.0                                 # Porcentaje de operaciones ganadoras (winning / total * 100)     
    profit_factor:          float = 0.0                                 # Profit Factor = suma(ganancias) / suma(pérdidas) # > 1 es rentable, > 1.5 es bueno, > 2 es muy bueno
    avg_trade_return_pct:   float = 0.0                                 # Retorno promedio por trade en %
    max_drawdown_pct:       float = 0.0                                 # Maxima caída desde un pico de capital (peor momento) # Ej: si llegaste a 12,000 y cayó a 10,000, el drawdown fue 16.67%
    strategy_name:          str = ""                                    # Nombre de la estrategia (ej: "ema_cross_long", "adx_smi_strategy", etc.)
    config:                 Optional[BacktestConfig] = None             # Configuracion usada (para reproducibilidad)
    created_at:             Optional[datetime] = None                   # Fecha en que se corrio el backtest