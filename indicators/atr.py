import pandas as pd

def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    high = high.astype(float)
    low = low.astype(float)
    close = close.astype(float)

    prev_close = close.shift(1)
    return pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    tr = true_range(high, low, close)

    return tr.ewm(alpha=1 / n, adjust=False).mean()
