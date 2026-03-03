import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def smoothing(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(alpha=1/n, adjust=False).mean()

def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr

def compute_adx(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.DataFrame:
    high, low, close = high.astype(float), low.astype(float), close.astype(float)

    # ΔH y ΔL
    delta_h = high.diff()
    delta_l = -low.diff()

    # Reglas para +DM y -DM
    plus_dm = np.where((delta_h > delta_l) & (delta_h > 0), delta_h, 0.0)
    minus_dm = np.where((delta_l > delta_h) & (delta_l > 0), delta_l, 0.0)
    plus_dm = pd.Series(plus_dm, index=high.index)
    minus_dm = pd.Series(minus_dm, index=high.index)

    # Cálculo del ATR y suavizado de +DM y -DM
    tr = true_range(high, low, close)
    atr = smoothing(tr, n)
    plus_dm_smoothed = smoothing(plus_dm, n)
    minus_dm_smoothed = smoothing(minus_dm, n)

    # Cálculo de +DI, -DI, DX y ADX
    plus_di = 100.0 * (plus_dm_smoothed / atr).replace({0: np.nan})
    minus_di = 100.0 * (minus_dm_smoothed / atr).replace({0: np.nan})

    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace({0: np.nan})
    adx = smoothing(dx, n)

    return pd.DataFrame({"+DI": plus_di, "-DI": minus_di, "DX": dx, "ADX": adx})
