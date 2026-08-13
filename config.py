"""
Config
------
هەموو ڕێکخستنەکان لێرەوە دەخوێندرێنەوە، لە Railway Environment Variables یان
لە فایلی .env (بۆ تێستکردنی لۆکاڵ).

# هەرگیز تۆکن/پاسۆردەکانت لە کۆدەکەدا هارد-کۆد مەکە، هەمیشە لە Environment Variables.
"""

import os
from dotenv import load_dotenv

load_dotenv()

def _get_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")

# --- MetaApi ---
METAAPI_TOKEN = os.getenv("METAAPI_TOKEN", "")

ACCOUNT_MODE = os.getenv("ACCOUNT_MODE", "demo").lower()
METAAPI_ACCOUNT_ID_DEMO = os.getenv("METAAPI_ACCOUNT_ID_DEMO", "")
METAAPI_ACCOUNT_ID_REAL = os.getenv("METAAPI_ACCOUNT_ID_REAL", "")

METAAPI_ACCOUNT_ID = (
    METAAPI_ACCOUNT_ID_REAL if ACCOUNT_MODE == "real" else METAAPI_ACCOUNT_ID_DEMO
)

# --- Trading ---
SYMBOL = os.getenv("SYMBOL", "XAUUSD")

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
