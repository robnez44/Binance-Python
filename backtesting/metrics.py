"""
Métricas de backtesting.

Funciones:
- summarize_backtest: calcula todas las métricas a partir de los trades
- _max_drawdown_pct: calcula el drawdown máximo
"""
from datetime import datetime, timezone
from typing import List, Optional
from backtesting.records import BacktestConfig, BacktestResult, Trade

def _max_drawdown_pct(equity_curve: List[float]) -> float:
    """
    Calcula el drawdown máximo en %.

    El drawdown es la caída desde el pico más alto hasta el valle más bajo.
    Ejemplo: si el capital subió a 12,000 y luego cayó a 10,000,
    el drawdown fue 16.67%.
    """
    if not equity_curve:
        return 0.0

    peak = equity_curve[0]
    max_dd = 0.0
    for equity in equity_curve:
        if equity > peak:
            peak = equity
        if peak > 0:
            drawdown = ((peak - equity) / peak) * 100
            if drawdown > max_dd:
                max_dd = drawdown
    return max_dd

def summarize_backtest(
    trades: List[Trade],
    initial_capital: float,
    strategy_name: str,
    symbol: str = "",
    interval: str = "",
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    config: Optional[BacktestConfig] = None,
) -> BacktestResult:
    """
    Calcula todas las métricas de backtesting a partir de los trades.

    Parámetros:
    - trades: lista de operaciones ejecutadas
    - initial_capital: capital inicial
    - strategy_name: nombre de la estrategia
    - symbol: símbolo testeado (ej: BTCUSDT)
    - interval: temporalidad (ej: 4h)
    - start_time: inicio del rango testeado
    - end_time: fin del rango testeado
    - config: configuración usada (para reproducibilidad)

    Retorna:
    - BacktestResult con todas las métricas calculadas
    """
    # Construir curva de equity (capital a lo largo del tiempo)
    equity_curve = [initial_capital]
    for trade in trades:
        equity_curve.append(trade.equity_after)

    final_capital = equity_curve[-1] if equity_curve else initial_capital

    # Retorno total
    total_return_pct = (
        ((final_capital - initial_capital) / initial_capital) * 100
        if initial_capital else 0.0
    )

    # Separar trades ganadores y perdedores
    winning = [t for t in trades if t.pnl > 0]
    losing = [t for t in trades if t.pnl < 0]

    # Profit factor = ganancias brutas / pérdidas brutas
    gross_profit = sum(t.pnl for t in winning)
    gross_loss = abs(sum(t.pnl for t in losing))
    profit_factor = (
        (gross_profit / gross_loss) if gross_loss > 0
        else (float("inf") if gross_profit > 0 else 0.0)
    )

    # Promedios
    avg_trade_return_pct = (
        (sum(t.return_pct for t in trades) / len(trades))
        if trades else 0.0
    )
    win_rate_pct = (len(winning) / len(trades) * 100) if trades else 0.0

    return BacktestResult(
        symbol=symbol,
        interval=interval,
        start_time=start_time,
        end_time=end_time,
        trades=trades,
        initial_capital=initial_capital,
        final_capital=final_capital,
        total_return_pct=total_return_pct,
        total_trades=len(trades),
        winning_trades=len(winning),
        losing_trades=len(losing),
        win_rate_pct=win_rate_pct,
        profit_factor=profit_factor,
        avg_trade_return_pct=avg_trade_return_pct,
        max_drawdown_pct=_max_drawdown_pct(equity_curve),
        strategy_name=strategy_name,
        config=config,
        created_at=datetime.now(timezone.utc),
    )
