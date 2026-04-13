import numpy as np
import pandas as pd
from database.schemas import ADXSnapshot
from indicators.atr import compute_atr, true_range

def smoothing(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(alpha=1/n, adjust=False).mean()

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

    # Cálculo del ATR reutilizando indicators.atr (evita duplicación)
    atr = compute_atr(high, low, close, n=n)
    plus_dm_smoothed = smoothing(plus_dm, n)
    minus_dm_smoothed = smoothing(minus_dm, n)

    # Cálculo de +DI, -DI, DX y ADX
    plus_di = 100.0 * (plus_dm_smoothed / atr).replace({0: np.nan})
    minus_di = 100.0 * (minus_dm_smoothed / atr).replace({0: np.nan})

    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace({0: np.nan})
    adx = smoothing(dx, n)

    return pd.DataFrame({"+DI": plus_di, "-DI": minus_di, "DX": dx, "ADX": adx})

def build_adx_snapshots(
    symbol: str,
    interval: str,
    adx_df: pd.DataFrame,
    times: pd.DatetimeIndex,
) -> list[ADXSnapshot]:
    """Construye una lista de ADXSnapshot a partir del DataFrame de compute_adx."""
    snapshots = []
    for i in range(len(adx_df)):
        snapshots.append(ADXSnapshot(
            symbol=symbol,
            interval=interval,
            timestamp=times[i].to_pydatetime(),
            plus_di=float(adx_df["+DI"].iloc[i]) if not np.isnan(adx_df["+DI"].iloc[i]) else 0.0,
            minus_di=float(adx_df["-DI"].iloc[i]) if not np.isnan(adx_df["-DI"].iloc[i]) else 0.0,
            dx=float(adx_df["DX"].iloc[i]) if not np.isnan(adx_df["DX"].iloc[i]) else 0.0,
            adx=float(adx_df["ADX"].iloc[i]) if not np.isnan(adx_df["ADX"].iloc[i]) else 0.0,
        ))
    return snapshots

