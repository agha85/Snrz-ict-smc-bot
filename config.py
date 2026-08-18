"""
Config
------
هەموو ڕێکخستنەکان لێرەوە دەخوێندرێنەوە، لە Railway Environment Variables یان
لە فایلی .env (بۆ تێستکردنی لۆکاڵ).
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _get_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _parse_pip_sizes(raw: str) -> dict:
    result = {}
    for part in raw.split(","):
        if ":" in part:
            sym, val = part.split(":")
            try:
                result[sym.strip()] = float(val)
            except ValueError:
                pass
    return result


# --- MT5 (mtapi.io) ---
MT5_LOGIN = os.getenv("MT5_LOGIN", "")
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")
ACCOUNT_MODE = os.getenv("ACCOUNT_MODE", "demo").lower()

# --- Trading ---
SYMBOLS = [s.strip() for s in os.getenv("SYMBOLS", "XAUUSD,BTCUSD").split(",") if s.strip()]

# --- Timeframes (بۆ SNRZ) ---
ANALYSIS_TIMEFRAMES = ["5m"]
CONFIRMATION_TIMEFRAME = "5m"
MIN_AGREEING_TIMEFRAMES = int(os.getenv("MIN_AGREEING_TIMEFRAMES", "1"))

# --- Grid strategy (SNRZ only) ---
GRID_ORDERS_COUNT = int(os.getenv("GRID_ORDERS_COUNT", "10"))
GRID_LOT_SIZE = float(os.getenv("GRID_LOT_SIZE", "0.01"))
GRID_SL_PIPS = float(os.getenv("GRID_SL_PIPS", "10"))
GRID_TRAIL_TRIGGER_PIPS = float(os.getenv("GRID_TRAIL_TRIGGER_PIPS", "30"))
GRID_TRAIL_SL_PIPS = float(os.getenv("GRID_TRAIL_SL_PIPS", "10"))
# ئەگەر ئۆردەرە چاوەڕوانەکان (pending) لەم ماوەیەدا پڕ نەکرانەوە، پاک دەکرێنەوە
# و لە زۆنی نوێدا دووبارە دادەنرێن (ئەگەر بایاسی نوێ هەبوو)
GRID_MAX_AGE_MINUTES = float(os.getenv("GRID_MAX_AGE_MINUTES", "60"))

PIP_SIZES = _parse_pip_sizes(os.getenv("PIP_SIZES", "XAUUSD:0.1,BTCUSD:1.0"))
DEFAULT_PIP_SIZE = float(os.getenv("DEFAULT_PIP_SIZE", "0.1"))

MAX_OPEN_TRADES = int(os.getenv("MAX_OPEN_TRADES", "10"))  # بۆ هەر ئەسێت (گرید = ١٠)

# --- Loop ---
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "20"))

# --- Safety ---
DRY_RUN = _get_bool("DRY_RUN", default=True)