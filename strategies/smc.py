"""
SMC Concepts (Smart Money Concepts)
------------------------------------
  - Premium / Discount Zone (OTE 61.8%-79%) — بەپێی ڕەیشۆی Fibonacci
  - Equal Highs / Equal Lows (Liquidity Pools)
  - Structure break هاوشێوەی ICT بەڵام بە فۆکەسی premium/discount
"""

from typing import List, Dict, Optional
from utils.candles import find_swing_points


def get_range_and_ote(candles: List[Dict], lookback: int = 50) -> Optional[Dict]:
    window = candles[-lookback:] if len(candles) > lookback else candles
    if len(window) < 10:
        return None

    high = max(c["high"] for c in window)
    low = min(c["low"] for c in window)
    rng = high - low
    if rng <= 0:
        return None

    return {
        "range_high": high,
        "range_low": low,
        "discount_zone": (low, low + rng * 0.382),
        "premium_zone": (low + rng * 0.618, high),
        "ote_buy": (low + rng * 0.21, low + rng * 0.382),
        "ote_sell": (low + rng * 0.618, low + rng * 0.79),
    }


def find_liquidity_pools(candles: List[Dict], tolerance_pct: float = 0.001) -> List[Dict]:
    swings = find_swing_points(candles, left=2, right=2)
    pools = []
    highs = [s for s in swings if s["type"] == "high"]
    lows = [s for s in swings if s["type"] == "low"]

    for group, kind in ((highs, "equal_highs"), (lows, "equal_lows")):
        group_sorted = sorted(group, key=lambda s: s["price"])
        i = 0
        while i < len(group_sorted) - 1:
            a, b = group_sorted[i], group_sorted[i + 1]
            if abs(a["price"] - b["price"]) / a["price"] <= tolerance_pct:
                pools.append({"type": kind, "level": (a["price"] + b["price"]) / 2})
                i += 2
            else:
                i += 1
    return pools


def get_smc_signal(candles: List[Dict]) -> Dict:
    if len(candles) < 30:
        return {"bias": "NONE", "reason": "کاندڵی پێویست کەمە"}

    ote = get_range_and_ote(candles)
    if not ote:
        return {"bias": "NONE", "reason": "ناتوانرێت ڕەنج دیاری بکرێت"}

    last_price = candles[-1]["close"]
    lo, hi = ote["ote_buy"]
    if lo <= last_price <= hi:
        return {"bias": "BUY", "reason": f"discount_OTE({lo:.2f}-{hi:.2f})"}

    lo, hi = ote["ote_sell"]
    if lo <= last_price <= hi:
        return {"bias": "SELL", "reason": f"premium_OTE({lo:.2f}-{hi:.2f})"}

    return {"bias": "NONE", "reason": "نرخ لە دەرەوەی OTE zoneـە"}