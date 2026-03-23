import numpy as np
from backtesting.records import StrategySignals
from indicators.emas import compute_ema, ema_pct_slope

def ema_vertical_cross_long_strategy(
    prices: np.ndarray,
    highs: np.ndarray,
    fast_span: int = 10,
    slow_span: int = 55,
    min_slope_pct: float = 0.05,
    exit_slope_periods: int = 2,
) -> StrategySignals:
    """
    Estrategia long EMA 10/55 con filtro de verticalidad.

    ENTRADA — las 3 condiciones deben cumplirse en la misma vela:
      1. EMA 10 cruza ARRIBA de EMA 55  (cruce alcista confirmado)
      2. Pendiente EMA 10 >= +min_slope_pct
      3. Precio de cierre por encima de EMA 10

    SALIDA — las 2 condiciones deben cumplirse en la misma vela:
      1. Pendiente EMA 10 negativa sostenida durante N velas consecutivas
         (exit_slope_periods velas seguidas con slope <= -min_slope_pct)
      2. Precio de cierre por debajo de EMA 10

    Importante sobre el range del loop:
      El loop de ENTRADA empieza en i=1 (necesita i-1 para el cruce).
      El loop de SALIDA necesita mirar exit_slope_periods velas hacia atrás,
      por lo que su condición se protege con un max(0, ...) en el range.
      Ambas condiciones se evalúan en el mismo loop para evitar el bug
      de empezar el loop en exit_slope_periods y saltarse cruces tempranos.

    Parámetros
    ----------
    prices             : array de precios de cierre
    highs              : array de precios máximos
    fast_span          : periodo EMA rápida  (default 10)
    slow_span          : periodo EMA lenta   (default 55)
    min_slope_pct      : pendiente mínima en % (default 0.05)
    exit_slope_periods : velas consecutivas con pendiente negativa
                         necesarias para confirmar la salida (default 2)
    """
    ema_fast       = compute_ema(prices, fast_span)
    ema_slow       = compute_ema(prices, slow_span)
    fast_slope_pct = ema_pct_slope(ema_fast)

    entry_long = np.zeros(len(prices), dtype=bool)
    exit_long  = np.zeros(len(prices), dtype=bool)

    # El loop empieza siempre en i=1 para no saltarse ningún cruce.
    # La condición de salida maneja internamente el lookback necesario.
    for i in range(1, len(prices)):

        # ── ENTRADA ─────────────────────────────────────────────────────
        # Cruce: en i-1 la EMA 10 estaba por debajo, en i ya está por encima.
        # La señal queda en la vela i → ejecución al open de i+1.
        cross_up  = ema_fast[i - 1] <= ema_slow[i - 1] and ema_fast[i] > ema_slow[i]
        strong_up = fast_slope_pct[i] >= min_slope_pct
        above_ema = prices[i] > ema_fast[i]
        entry_long[i] = cross_up and strong_up and above_ema

        # ── SALIDA ──────────────────────────────────────────────────────
        # Necesitamos exit_slope_periods velas hacia atrás.
        # Si i < exit_slope_periods no hay suficiente historia → False.
        if i >= exit_slope_periods:
            sustained_down = all(
                fast_slope_pct[j] <= -min_slope_pct
                for j in range(i - exit_slope_periods + 1, i + 1)
            )
            below_ema = prices[i] < ema_fast[i]
            exit_long[i] = sustained_down and below_ema
        # Si i < exit_slope_periods, exit_long[i] queda False (inicializado)

    return StrategySignals(
        entry_long=entry_long,
        exit_long=exit_long,
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        name=f"ema_vertical_{fast_span}_{slow_span}_long",
    )