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


# --- MT5 (mtapi.io) ---
MT5_LOGIN = os.getenv("MT5_LOGIN", "")
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")
ACCOUNT_MODE = os.getenv("ACCOUNT_MODE", "demo").lower()

# --- Trading ---
SYMBOLS = [s.strip() for s in os.getenv("SYMBOLS", "XAUUSD,BTCUSD").split(",") if s.strip()]

RISK_PERCENT_PER_TRADE = float(os.getenv("RISK_PERCENT_PER_TRADE", "30"))
MAX_OPEN_TRADES = int(os.getenv("MAX_OPEN_TRADES", "1"))
SL_BUFFER_USD = float(os.getenv("SL_BUFFER_USD", "1.5"))
RISK_REWARD_RATIO = float(os.getenv("RISK_REWARD_RATIO", "2.0"))

# --- Timeframes ---
ANALYSIS_TIMEFRAMES = ["1W", "1D", "4H", "1H"]
CONFIRMATION_TIMEFRAME = "15m"

# --- Loop ---
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))

# --- Safety ---
DRY_RUN = _get_bool("DRY_RUN", default=True)