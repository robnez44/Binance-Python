import numpy as np
from backtesting.records import StrategySignals
from indicators.emas import compute_ema, ema_pct_slope

def ema_cross_long_strategy(
    prices: np.ndarray,
    fast_span: int = 10,
    slow_span: int = 55,
) -> StrategySignals:
    """Señales long simples basadas en cruce de EMA rápida sobre EMA lenta."""
    ema_fast = compute_ema(prices, fast_span)
    ema_slow = compute_ema(prices, slow_span)

    entry_long = np.zeros(len(prices), dtype=bool)
    exit_long  = np.zeros(len(prices), dtype=bool)

    for i in range(1, len(prices)):
        entry_long[i] = ema_fast[i - 1] <= ema_slow[i - 1] and ema_fast[i] > ema_slow[i]
        exit_long[i]  = ema_fast[i - 1] >= ema_slow[i - 1] and ema_fast[i] < ema_slow[i]

    return StrategySignals(
        entry_long=entry_long,
        exit_long=exit_long,
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        name=f"ema_{fast_span}_{slow_span}_cross_long",
    )

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

    SALIDA — las 3 condiciones deben cumplirse en la misma vela:
      1. Pendiente EMA 10 negativa durante N velas consecutivas
         (exit_slope_periods velas seguidas con slope <= -min_slope_pct)
         → detecta debilidad sostenida, no un retroceso de una sola vela
      2. Pendiente EMA 10 <= -min_slope_pct en la vela actual
      3. Precio de cierre por debajo de EMA 10

    Por qué NO se usa el cruce inverso para salir:
      El cruce de EMA 10 bajo EMA 55 ocurre mucho después de que el precio
      ya cayó — cuando cruzan, la EMA 10 lleva varias velas descendiendo y
      el precio ya perdió buena parte de las ganancias o incluso entró en
      pérdida. La salida por pendiente sostenida reacciona antes: en cuanto
      la EMA 10 muestra debilidad real (N velas negativas) y el precio está
      bajo ella, se cierra. El stop loss sigue siendo la red de seguridad
      para caídas abruptas.

    Parámetros
    ----------
    prices             : array de precios de cierre
    highs              : array de precios máximos
    fast_span          : periodo EMA rápida  (default 10)
    slow_span          : periodo EMA lenta   (default 55)
    min_slope_pct      : pendiente mínima en % (default 0.05)
    exit_slope_periods : número de velas consecutivas con pendiente negativa
                         necesarias para confirmar la salida (default 2)
                         · 1 = salida más rápida (más señales, puede ser ruido)
                         · 2 = balance entre rapidez y confirmación
                         · 3+ = más conservador, sale más tarde
    """
    ema_fast       = compute_ema(prices, fast_span)
    ema_slow       = compute_ema(prices, slow_span)
    fast_slope_pct = ema_pct_slope(ema_fast)

    entry_long = np.zeros(len(prices), dtype=bool)
    exit_long  = np.zeros(len(prices), dtype=bool)

    for i in range(exit_slope_periods, len(prices)):

        # ── ENTRADA ─────────────────────────────────────────────────────
        cross_up  = ema_fast[i - 1] <= ema_slow[i - 1] and ema_fast[i] > ema_slow[i]
        strong_up = fast_slope_pct[i] >= min_slope_pct
        above_ema = prices[i] > ema_fast[i]
        entry_long[i] = cross_up and strong_up and above_ema

        # ── SALIDA ──────────────────────────────────────────────────────
        # Condición 1: pendiente negativa sostenida en las últimas N velas
        # Se verifica que TODAS las velas desde [i - exit_slope_periods + 1]
        # hasta [i] tengan pendiente <= -min_slope_pct.
        # Esto filtra retrocesos de una sola vela y solo sale cuando la
        # debilidad es real y continuada.
        sustained_down = all(
            fast_slope_pct[j] <= -min_slope_pct
            for j in range(i - exit_slope_periods + 1, i + 1)
        )

        # Condición 2: precio por debajo de EMA 10
        below_ema = prices[i] < ema_fast[i]

        exit_long[i] = sustained_down and below_ema

    return StrategySignals(
        entry_long=entry_long,
        exit_long=exit_long,
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        name=f"ema_vertical_{fast_span}_{slow_span}_long",
    )