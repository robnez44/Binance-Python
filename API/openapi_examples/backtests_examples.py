"""OpenAPI examples for backtests endpoints.

Keep examples short and modular so routers stay clean.
"""
OPENAPI_EXAMPLES = {
    "corto": {
        "summary": "Ejemplo corto",
        "description": "Usa solo los parámetros mínimos obligatorios y algunos ajustes comunes.",
        "value": {
            "symbol": "BTCUSDT",
            "interval": "4h",
            "start_time": "2026-03-01",
            "end_time": None,
            "initial_capital": 100000,
            "leverage": 1,
            "min_slope_pct": 0.11,
            "exit_slope_periods": 2,
            "ema_gap_min_pct": 0.0,
            "adx_min": 23,
            "adx_require_di": True,
            "adx_require_rising": False,
        },
    },
    "largo": {
        "summary": "Ejemplo largo",
        "description": "Incluye todos los campos del request para mostrar el payload completo.",
        "value": {
            "symbol": "BTCUSDT",
            "interval": "4h",
            "start_time": "2026-03-01",
            "end_time": None,
            "initial_capital": 100000,
            "leverage": 1,
            "stop_loss_pct": None,
            "take_profit_pct": None,
            "breakeven_trigger_pct": None,
            "min_slope_pct": 0.11,
            "exit_slope_periods": 2,
            "ema_gap_min_pct": 0.0,
            "adx_min": 23,
            "adx_require_di": True,
            "adx_require_rising": False,
            "atr_period": 14,
            "atr_stop_mult": 1.8,
            "atr_trailing_mult": 2.2,
        },
    },
}
