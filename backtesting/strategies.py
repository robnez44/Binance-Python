import numpy as np
import pandas as pd
from backtesting.records import StrategySignals
from indicators.emas import compute_ema, ema_pct_slope
from indicators.adx import compute_adx

def _build_base_ema_signals(
    prices: np.ndarray,
    fast_span: int,
    slow_span: int,
    min_slope_pct: float,
    exit_slope_periods: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    ema_fast = compute_ema(prices, fast_span)
    ema_slow = compute_ema(prices, slow_span)
    fast_slope_pct = ema_pct_slope(ema_fast)

    entry_base_long = np.zeros(len(prices), dtype=bool)
    entry_long = np.zeros(len(prices), dtype=bool)
    exit_long = np.zeros(len(prices), dtype=bool)

    for i in range(1, len(prices)):
        cross_up = ema_fast[i - 1] <= ema_slow[i - 1] and ema_fast[i] > ema_slow[i]
        strong_up = fast_slope_pct[i] >= min_slope_pct
        above_ema = prices[i] > ema_fast[i]
        entry_base_long[i] = cross_up and strong_up and above_ema
        bullish_trend = ema_fast[i] > ema_slow[i]
        entry_long[i] = entry_base_long[i] or (bullish_trend and strong_up and above_ema)

        if i >= exit_slope_periods:
            sustained_down = all(
                fast_slope_pct[j] <= -min_slope_pct
                for j in range(i - exit_slope_periods + 1, i + 1)
            )
            below_ema = prices[i] < ema_fast[i]
            exit_long[i] = sustained_down and below_ema

    return ema_fast, ema_slow, fast_slope_pct, entry_base_long, entry_long, exit_long

def _build_ema_gap_mask(
    ema_fast: np.ndarray,
    ema_slow: np.ndarray,
    ema_gap_min_pct: float,
) -> tuple[np.ndarray, np.ndarray]:
    gap_pct = np.zeros(len(ema_fast), dtype=float)
    non_zero = ema_slow != 0
    gap_pct[non_zero] = ((ema_fast[non_zero] - ema_slow[non_zero]) / ema_slow[non_zero]) * 100
    gap_mask = gap_pct >= ema_gap_min_pct
    return gap_mask, gap_pct

def _build_adx_arrays(
    prices: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    adx_period: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    idx = pd.RangeIndex(len(prices))
    high_s = pd.Series(highs, index=idx)
    low_s = pd.Series(lows, index=idx)
    close_s = pd.Series(prices, index=idx)
    adx_df = compute_adx(high_s, low_s, close_s, n=adx_period)
    adx_vals = adx_df["ADX"].fillna(0.0).to_numpy()
    plus_di = adx_df["+DI"].fillna(0.0).to_numpy()
    minus_di = adx_df["-DI"].fillna(0.0).to_numpy()
    return adx_vals, plus_di, minus_di

def build_ema_long_signals(
    prices: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray | None = None,
    fast_span: int = 10,
    slow_span: int = 55,
    min_slope_pct: float = 0.05,
    exit_slope_periods: int = 2,
    ema_gap_min_pct: float = 0.0,
    adx_min: float = 0.0,
    adx_period: int = 14,
    require_di_confirmation: bool = True,
) -> StrategySignals:
    """
    Constructor modular de señales:
    1) Señal base EMA (cruce + slope + precio)
    2) Filtros opcionales por indicador (gap EMA, ADX)

    No crea funciones por combinación de indicadores; activa solo los filtros necesarios.
    """
    ema_fast, ema_slow, _, entry_base_long, entry_long, exit_long = _build_base_ema_signals(
        prices=prices,
        fast_span=fast_span,
        slow_span=slow_span,
        min_slope_pct=min_slope_pct,
        exit_slope_periods=exit_slope_periods,
    )

    n = len(prices)
    filter_total_count = np.zeros(n, dtype=int)
    filter_pass_count = np.zeros(n, dtype=int)
    active_filters: list[str] = []

    adx_vals: np.ndarray | None = None
    plus_di: np.ndarray | None = None
    minus_di: np.ndarray | None = None

    if ema_gap_min_pct > 0:
        gap_mask, _ = _build_ema_gap_mask(ema_fast, ema_slow, ema_gap_min_pct)
        entry_long &= gap_mask
        filter_total_count += 1
        filter_pass_count += gap_mask.astype(int)
        active_filters.append(f"ema_gap>={ema_gap_min_pct:.4f}%")

    use_adx_filter = adx_min > 0
    if use_adx_filter:
        if lows is None:
            raise ValueError("lows es obligatorio cuando el filtro ADX está activo")

        adx_vals, plus_di, minus_di = _build_adx_arrays(
            prices=prices,
            highs=highs,
            lows=lows,
            adx_period=adx_period,
        )

        adx_mask = adx_vals >= adx_min
        if require_di_confirmation:
            adx_mask &= plus_di > minus_di

        entry_long &= adx_mask
        filter_total_count += 1
        filter_pass_count += adx_mask.astype(int)
        active_filters.append(f"adx>={adx_min:.2f}")
        if require_di_confirmation:
            active_filters.append("+DI>-DI")

    if active_filters:
        strategy_name = f"ema_modular_{fast_span}_{slow_span}_long"
    else:
        strategy_name = f"ema_vertical_{fast_span}_{slow_span}_long"

    return StrategySignals(
        entry_long=entry_long,
        exit_long=exit_long,
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        name=strategy_name,
        adx_values=adx_vals,
        plus_di=plus_di,
        minus_di=minus_di,
        entry_base_long=entry_base_long,
        filter_total_count=filter_total_count if active_filters else None,
        filter_pass_count=filter_pass_count if active_filters else None,
        active_filters=active_filters,
    )

def ema_vertical_cross_long_strategy(
    prices: np.ndarray,
    highs: np.ndarray,
    fast_span: int = 10,
    slow_span: int = 55,
    min_slope_pct: float = 0.05,
    exit_slope_periods: int = 2,
) -> StrategySignals:
    return build_ema_long_signals(
        prices=prices,
        highs=highs,
        lows=None,
        fast_span=fast_span,
        slow_span=slow_span,
        min_slope_pct=min_slope_pct,
        exit_slope_periods=exit_slope_periods,
        ema_gap_min_pct=0.0,
        adx_min=0.0,
    )

def ema_adx_long_strategy(
    prices: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    fast_span: int = 10,
    slow_span: int = 55,
    min_slope_pct: float = 0.05,
    exit_slope_periods: int = 2,
    ema_gap_min_pct: float = 0.0,
    adx_min: float = 23.0,
    adx_period: int = 14,
    require_di_confirmation: bool = True,
) -> StrategySignals:
    return build_ema_long_signals(
        prices=prices,
        highs=highs,
        lows=lows,
        fast_span=fast_span,
        slow_span=slow_span,
        min_slope_pct=min_slope_pct,
        exit_slope_periods=exit_slope_periods,
        ema_gap_min_pct=ema_gap_min_pct,
        adx_min=adx_min,
        adx_period=adx_period,
        require_di_confirmation=require_di_confirmation,
    )