import os
import re
from datetime import datetime, timezone
from pathlib import Path

from backtesting.records import BacktestConfig, BacktestResult
from utils.utils import parse_utc

def slugify_filename(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(text).strip())
    cleaned = cleaned.strip("_")
    return cleaned or "na"

def build_pdf_path(result: BacktestResult, params: dict) -> Path:
    out_dir_raw = params.get("pdf_output_dir", "reports/backtests")
    out_dir = Path(out_dir_raw).expanduser()
    if not out_dir.is_absolute():
        out_dir = Path.cwd() / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    custom_filename = (params.get("pdf_filename") or "").strip()
    if custom_filename:
        filename = slugify_filename(custom_filename)
        if not filename.lower().endswith(".pdf"):
            filename = f"{filename}.pdf"
    else:
        start_label = params["start_time"].strftime("%Y%m%d")
        end_dt = params.get("end_time") or datetime.now(timezone.utc)
        end_label = end_dt.strftime("%Y%m%d")
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = (
            f"{slugify_filename(params['symbol'])}_"
            f"{slugify_filename(params['interval'])}_"
            f"{slugify_filename(result.strategy_name)}_"
            f"{start_label}_to_{end_label}_{ts}.pdf"
        )

    pdf_path = out_dir / filename
    if pdf_path.exists():
        dup_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        pdf_path = out_dir / f"{pdf_path.stem}_{dup_ts}{pdf_path.suffix}"
    return pdf_path

# ══════════════════════════════════════════════════════════════════════════════
#  Input
# ══════════════════════════════════════════════════════════════════════════════

def ask_backtest_params() -> dict:
    symbol = input("Símbolo (default BTCUSDT): ").strip() or "BTCUSDT"
    interval = input("Temporalidad (ej: 4h, 1d): ").strip()
    start_str = input("Start UTC (YYYY-MM-DD HH:MM or YYYY-MM-DD): ").strip()
    end_str = input("End UTC (opcional): ").strip()
    min_slope_pct = input("Pendiente mínima EMA10 % (default 0.08): ").strip()
    exit_slope_p = input("Velas negativas para salir (default 2): ").strip()
    ema_gap_min_str = input("Separación mínima EMA10-EMA55 % (opcional, Enter = 0): ").strip()
    adx_min_str = input("ADX mínimo para filtrar ruido (opcional, Enter = 0): ").strip()

    adx_min = float(adx_min_str) if adx_min_str else 0.0
    ema_gap_min_pct = float(ema_gap_min_str) if ema_gap_min_str else 0.0
    if adx_min > 0:
        adx_di_str = input("Filtro +DI > -DI en entrada (S/n): ").strip().lower()
        adx_require_di = adx_di_str != "n"
    else:
        adx_require_di = False

    leverage = input("Apalancamiento (default 1X): ").strip()
    capital = input("Capital inicial (default 10000): ").strip()
    pdf_filename = input("Nombre PDF (opcional, Enter = automático): ").strip()

    # Gestión de riesgo automática (sin pedir SL manual): ATR dinámico por defecto.
    atr_period = 14
    atr_stop_mult = 1.8
    atr_trailing_mult = 2.2
    atr_stop_confirm_on_close = True
    pdf_output_dir = os.getenv("BACKTEST_PDF_DIR", "reports/backtests")

    return {
        "symbol": symbol,
        "interval": interval,
        "start_time": parse_utc(start_str),
        "end_time": parse_utc(end_str) if end_str else None,
        "config": BacktestConfig(
            initial_capital=float(capital) if capital else 10_000.0,
            leverage=float(leverage) if leverage else 1.0,
            stop_loss_pct=None,
            take_profit_pct=None,
            breakeven_trigger_pct=None,
            min_slope_pct=float(min_slope_pct) if min_slope_pct else 0.08,
            exit_slope_periods=int(exit_slope_p) if exit_slope_p else 2,
            ema_gap_min_pct=ema_gap_min_pct,
            adx_min=adx_min,
            adx_require_di=adx_require_di,
            atr_period=atr_period,
            atr_stop_mult=atr_stop_mult,
            atr_trailing_mult=atr_trailing_mult,
            atr_stop_confirm_on_close=atr_stop_confirm_on_close,
        ),
        "min_slope_pct": float(min_slope_pct) if min_slope_pct else 0.08,
        "exit_slope_periods": int(exit_slope_p) if exit_slope_p else 2,
        "ema_gap_min_pct": ema_gap_min_pct,
        "adx_min": adx_min,
        "adx_require_di": adx_require_di,
        "use_adx": adx_min > 0.0,
        "use_atr_stop": True,
        "atr_stop_confirm_on_close": atr_stop_confirm_on_close,
        "pdf_output_dir": pdf_output_dir,
        "pdf_filename": pdf_filename,
    }
