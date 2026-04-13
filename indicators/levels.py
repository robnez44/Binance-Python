import numpy as np
import pandas as pd
from typing import List, Tuple
from indicators.atr import true_range
from database.schemas import SRLevel

def _count_touches(
    price: float,
    level_type: str,
    highs: np.ndarray,
    lows: np.ndarray,
    tol: float,
    exclude_idx: int,
) -> int:
    touches = 0
    for j in range(len(highs)):
        if j == exclude_idx:
            continue

        # Un toque debe ocurrir cerca del extremo relevante de la vela.
        # - soporte    -> la mecha inferior debe acercarse al nivel
        # - resistencia -> la mecha superior debe acercarse al nivel
        # Esto evita contar como "toque" cualquier vela cuyo rango simplemente
        # atraviese el nivel en medio del cuerpo, lo que inflaba muchísimo el conteo.
        if level_type == "support":
            touched = abs(lows[j] - price) <= tol
        else:
            touched = abs(highs[j] - price) <= tol

        if touched:
            touches += 1
    return touches

def find_support_resistance(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    times: pd.DatetimeIndex,
    symbol: str,
    interval: str,
    atr_n: int = 14,
    tol_mult: float = 0.75,
    touch_tol_mult: float = 0.3,
    min_touches: int = 1,
) -> List[SRLevel]:
    """Detecta soportes y resistencias usando fractales de 5 velas.

    Cada fractal necesita 2 velas a cada lado.
    Luego cuenta cuántas velas tocan cada nivel en TODA la serie (pasado
    y futuro) para medir la fuerza del nivel. Se filtran niveles con
    menos de `min_touches` toques.

    Parameters
    ----------
    high, low, close : pd.Series  – OHLC con index = times.
    times            : DatetimeIndex
    symbol, interval : str
    atr_n            : int   – periodo del ATR para tolerancia (default 14).
    tol_mult         : float – multiplicador de ATR para de-duplicar niveles
                               cercanos (default 0.75).
    touch_tol_mult   : float – multiplicador de ATR para contar toques reales
                               sobre la mecha relevante (default 0.3).
    min_touches      : int   – mínimo de toques para considerar un nivel válido
                               (default 1, 0 = sin filtro).

    Returns
    -------
    list[SRLevel]  – niveles ordenados cronológicamente, con touches calculado.
    """
    hi = high.to_numpy().astype(float)
    lo = low.to_numpy().astype(float)
    n = len(hi)

    # ATR para tolerancia de de-duplicación
    tr = true_range(high, low, close)
    atr = tr.rolling(atr_n).mean().bfill().to_numpy()

    # ── 1. Detectar fractales (clásico: 2 velas a cada lado) ─────────────
    candidates: List[Tuple[int, float, str]] = []  # (idx, price, type)

    for i in range(2, n - 2):
        # Soporte: mínimo local (la vela central es menor que sus 4 vecinas)
        is_sup = (
            lo[i] < lo[i - 1] and lo[i] < lo[i - 2] and
            lo[i] < lo[i + 1] and lo[i] < lo[i + 2]
        )
        # Resistencia: máximo local
        is_res = (
            hi[i] > hi[i - 1] and hi[i] > hi[i - 2] and
            hi[i] > hi[i + 1] and hi[i] > hi[i + 2]
        )

        if is_sup:
            candidates.append((i, float(lo[i]), "support"))
        if is_res:
            candidates.append((i, float(hi[i]), "resistance"))

    # ── 2. De-duplicar niveles cercanos ───────────────────────────────────
    deduped: List[Tuple[int, float, str]] = []
    for idx, price, ltype in candidates:
        tol = tol_mult * float(atr[idx])
        if all(abs(price - p) > tol for _, p, _ in deduped):
            deduped.append((idx, price, ltype))

    # ── 3. Contar toques y construir SRLevel ─────────────────────────────
    levels: List[SRLevel] = []
    for idx, price, ltype in deduped:
        touch_tol = touch_tol_mult * float(atr[idx])
        touches = _count_touches(price, ltype, hi, lo, touch_tol, exclude_idx=idx)

        if touches < min_touches:
            continue

        levels.append(SRLevel(
            symbol=symbol,
            interval=interval,
            idx=idx,
            timestamp=times[idx].to_pydatetime(),
            price=price,
            level_type=ltype,
            touches=touches,
        ))

    return levels
