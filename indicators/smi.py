import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from indicators.atr import true_range
from database.schemas import SMISnapshot

def compute_squeeze(
    high: pd.Series, low: pd.Series, close: pd.Series, bb_len: int = 20, bb_mult: float = 2.0, kc_len: int = 20, kc_mult: float = 1.5, mom_len: int = 20
) -> pd.DataFrame:
    high, low, close = high.astype(float), low.astype(float), close.astype(float)

    # calcular Bollinger Bands
    basis = close.rolling(bb_len).mean()
    dev = close.rolling(bb_len).std(ddof=0)
    upper_bb = basis + bb_mult * dev
    lower_bb = basis - bb_mult * dev

    # calcular Keltner Channels
    kc_mid = close.ewm(span=kc_len, adjust=False).mean()
    atr = true_range(high, low, close).rolling(kc_len).mean()
    upper_kc = kc_mid + kc_mult * atr
    lower_kc = kc_mid - kc_mult * atr

    # 'squeeze' flags
    squeeze_on = (upper_bb < upper_kc) & (lower_bb > lower_kc)
    squeeze_off = (upper_bb > upper_kc) | (lower_bb < lower_kc)

    # momentum (LazyBear / TradingView)
    # delta = close - avg(avg(highest(high, kc_len), lowest(low, kc_len)), sma(close, bb_len))
    # mom   = linreg(delta, kc_len, 0)  →  valor de la recta en el punto actual
    hl_mid = (high.rolling(kc_len).max() + low.rolling(kc_len).min()) / 2.0
    delta  = close - (hl_mid + basis) / 2.0

    def rolling_linreg_value(series: pd.Series, window: int) -> pd.Series:
        """linreg(series, window, 0) — valor de la recta de regresión en el último punto."""
        x = np.arange(window, dtype=float)
        x_mean = x.mean()
        denom = ((x - x_mean) ** 2).sum()
        if denom == 0:
            return pd.Series(index=series.index, dtype=float)

        def _val(y: np.ndarray) -> float:
            y_mean = y.mean()
            a = ((x - x_mean) * (y - y_mean)).sum() / denom
            b = y_mean - a * x_mean
            return float(a * (window - 1) + b)

        return series.rolling(window).apply(lambda arr: _val(np.asarray(arr)), raw=True)

    mom = rolling_linreg_value(delta, mom_len)

    return pd.DataFrame({
        "BB_basis": basis, "BB_up": upper_bb, "BB_dn": lower_bb,
        "KC_mid": kc_mid, "KC_up": upper_kc, "KC_dn": lower_kc,
        "squeeze_on": squeeze_on.astype(int),
        "squeeze_off": squeeze_off.astype(int),
        "mom": mom
    })

def build_smi_snapshots(
    symbol: str,
    interval: str,
    sqz_df: pd.DataFrame,
    times: pd.DatetimeIndex,
) -> list[SMISnapshot]:
    """Construye una lista de SMISnapshot a partir del DataFrame de compute_squeeze."""
    snapshots = []
    for i in range(len(sqz_df)):
        mom_val = float(sqz_df["mom"].iloc[i])
        snapshots.append(SMISnapshot(
            symbol=symbol,
            interval=interval,
            timestamp=times[i].to_pydatetime(),
            smi=mom_val if not np.isnan(mom_val) else 0.0,
        ))
    return snapshots
