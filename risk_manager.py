"""
Risk Manager
------------
حیسابکردنی SL / TP / قەبارەی لۆت بەپێی ڕیسکی دیاریکراو.

⚠️ ئاگاداری: RISK_PERCENT_PER_TRADE لە config.py بە شێوەیەکی بنەڕەتی ٣٠٪ دانراوە
(بەپێی داوای بەکارهێنەر). ئەمە زۆر بەرزە — چاوپۆشی لێ مەکە.
"""

from typing import Dict, Optional
from utils.logger import get_logger
import config

logger = get_logger("risk_manager")


def calculate_sl_tp(entry_price: float, bias: str, zone: Optional[Dict] = None) -> Dict:
    buffer = config.SL_BUFFER_USD

    if zone and "low" in zone and "high" in zone:
        zone_low, zone_high = zone["low"], zone["high"]
    else:
        zone_low = entry_price * 0.997
        zone_high = entry_price * 1.003

    if bias == "BUY":
        sl = zone_low - buffer
        risk = entry_price - sl
        tp = entry_price + risk * config.RISK_REWARD_RATIO
    else:
        sl = zone_high + buffer
        risk = sl - entry_price
        tp = entry_price - risk * config.RISK_REWARD_RATIO

    return {"sl": round(sl, 2), "tp": round(tp, 2), "risk_per_unit": abs(entry_price - sl)}


def calculate_lot_size(
    balance: float,
    entry_price: float,
    sl_price: float,
    contract_size: float,
    volume_step: float = 0.01,
    min_volume: float = 0.01,
    max_volume: float = 100.0,
) -> float:
    risk_percent = config.RISK_PERCENT_PER_TRADE
    if risk_percent >= 20:
        logger.warning(
            "⚠️ ڕیسکی %.1f%% لە هەر ترەیدێکدا زۆر بەرزە — مەترسی لادانی هەژمار هەیە.",
            risk_percent,
        )

    risk_amount = balance * (risk_percent / 100.0)
    price_diff = abs(entry_price - sl_price)
    if price_diff <= 0:
        logger.error("جیاوازی نرخی entry/SL سفرە یان نێگەتیڤە — لۆت حیساب ناکرێت.")
        return 0.0

    risk_per_lot = price_diff * contract_size
    if risk_per_lot <= 0:
        return 0.0

    lot = risk_amount / risk_per_lot
    lot = round(lot / volume_step) * volume_step
    lot = max(min_volume, min(lot, max_volume))
    return round(lot, 2)