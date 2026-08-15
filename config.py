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
RISK_REWARD_RATIO = float(os.getenv("RISK_REWARD_RATIO", "1.5"))

# --- Confirmation rules (Scalping) ---
STRATEGY_MIN_AGREE = int(os.getenv("STRATEGY_MIN_AGREE", "2"))
MIN_AGREEING_TIMEFRAMES = int(os.getenv("MIN_AGREEING_TIMEFRAMES", "2"))

# --- Timeframes (بۆ سکاڵپ — خێراتر لە Weekly/Daily) ---
ANALYSIS_TIMEFRAMES = ["1H", "30m", "15m", "5m"]
CONFIRMATION_TIMEFRAME = "1m"

# --- Loop ---
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "20"))

# --- Safety ---
DRY_RUN = _get_bool("DRY_RUN", default=True)