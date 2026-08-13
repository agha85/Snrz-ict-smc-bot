"""
ICT Concepts
------------
  - Market Structure : BOS (Break of Structure) / CHoCH (Change of Character)
  - Order Block       : دواین کاندڵی پێچەوانە پێش موومێنتێکی بەهێز
  - Fair Value Gap    : بۆشایی نرخ لە نێوان ٣ کاندڵ (imbalance)
  - Kill Zones        : کاتی سیشنی لەندەن/نیویۆرک
"""

from typing import List, Dict, Optional
from datetime import datetime, timezone
from utils.candles import find_swing_points, is_bullish, is_bearish


def market_structure_signal(candles: List[Dict]) -> Dict:
    swings = find_swing_points(candles, left=2, right=2)
    if len(swings) < 4:
        return {"bias": "NONE", "reason": "سویمنگی پێویست نییە"}

    highs = [s for s in swings if s["type"] == "high"][-3:]
    lows = [s for s in swings if s["type"] == "low"][-3:]
    if len(highs) < 2 or len(lows) < 2:
        return {"bias": "NONE", "reason": "سویمنگی high/low کەمە"}

    last_price = candles[-1]["close"]
    prev_structure = "bullish" if highs[-2]["price"] < highs[-1]["price"] and lows[-2]["price"] < lows[-1]["price"] else (
        "bearish" if highs[-2]["price"] > highs[-1]["price"] and lows[-2]["price"] > lows[-1]["price"] else "range"
    )

    if last_price > highs[-1]["price"]:
        tag = "CHoCH" if prev_structure == "bearish" else "BOS"
        return {"bias": "BUY", "reason": f"{tag}_bullish", "level": highs[-1]["price"]}
    if last_price < lows[-1]["price"]:
        tag = "CHoCH" if prev_structure == "bullish" else "BOS"
        return {"bias": "SELL", "reason": f"{tag}_bearish", "level": lows[-1]["price"]}

    return {"bias": "NONE", "reason": f"structure={prev_structure}, no break yet"}


def find_order_blocks(candles: List[Dict], impulse_pct: float = 0.004) -> List[Dict]:
    obs = []
    for i in range(1, len(candles) - 1):
        cur = candles[i]
        prev = candles[i - 1]
        move_pct = abs(cur["close"] - cur["open"]) / cur["open"]
        if move_pct < impulse_pct:
            continue
        if is_bullish(cur) and is_bearish(prev):
            obs.append(
                {"type": "bullish_ob", "low": prev["low"], "high": prev["high"], "index": i - 1}
            )
        elif is_bearish(cur) and is_bullish(prev):
            obs.append(
                {"type": "bearish_ob", "low": prev["low"], "high": prev["high"], "index": i - 1}
            )
    return obs[-10:]


def find_fair_value_gaps(candles: List[Dict]) -> List[Dict]:
    fvgs = []
    for i in range(2, len(candles)):
        c1, c3 = candles[i - 2], candles[i]
        if c1["high"] < c3["low"]:
            fvgs.append({"type": "bullish_fvg", "low": c1["high"], "high": c3["low"], "index": i})
        elif c1["low"] > c3["high"]:
            fvgs.append({"type": "bearish_fvg", "low": c3["high"], "high": c1["low"], "index": i})
    return fvgs[-10:]


def price_reacts_to_ob_or_fvg(candles: List[Dict], obs: List[Dict], fvgs: List[Dict]) -> Optional[Dict]:
    last = candles[-1]
    for ob in reversed(obs):
        if ob["low"] <= last["close"] <= ob["high"]:
            bias = "BUY" if ob["type"] == "bullish_ob" else "SELL"
            return {"bias": bias, "reason": ob["type"], "zone": ob}
    for fvg in reversed(fvgs):
        if fvg["low"] <= last["close"] <= fvg["high"]:
            bias = "BUY" if fvg["type"] == "bullish_fvg" else "SELL"
            return {"bias": bias, "reason": fvg["type"], "zone": fvg}
    return None


def is_kill_zone(now: Optional[datetime] = None) -> bool:
    now = now or datetime.now(timezone.utc)
    h = now.hour
    return (7 <= h < 10) or (12 <= h < 15)


def get_ict_signal(candles: List[Dict]) -> Dict:
    if len(candles) < 30:
        return {"bias": "NONE", "reason": "کاندڵی پێویست کەمە"}

    structure = market_structure_signal(candles)
    obs = find_order_blocks(candles)
    fvgs = find_fair_value_gaps(candles)
    reaction = price_reacts_to_ob_or_fvg(candles, obs, fvgs)

    if reaction and structure["bias"] == reaction["bias"]:
        return {
            "bias": structure["bias"],
            "reason": f"{structure['reason']}+{reaction['reason']}",
        }
    if reaction and structure["bias"] == "NONE":
        return {"bias": reaction["bias"], "reason": f"weak_{reaction['reason']}"}

    return {"bias": "NONE", "reason": structure["reason"]}