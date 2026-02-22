from dataclasses import dataclass
import numpy as np

# Clase para almacenar las métricas de cada tendencia identificada
@dataclass
class SegmentMetrics:
    start_idx: int      # índice global (sobre toda la serie)
    end_idx: int        # índice global (inclusivo)
    length: int         # cantidad de velas en la subventana
    a: float            # pendiente de la recta y = a·x + b
    b: float            # intercepto
    r2: float           # coeficiente de determinación R²
    pct_slope: float    # pendiente porcentual: 100 * a / mean(y)
    mean_price: float   # precio medio del segmento
    regime: str         # 'UP' / 'DOWN' / 'SIDE'