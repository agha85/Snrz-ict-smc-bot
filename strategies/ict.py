"""
SNRZ Strategy (Support & Resistance Zindan)
--------------------------------------------
جێبەجێکردنی چوونەژووری کوانتیتاتیڤی سەرەکی چەمکەکانی کۆرسی SNRZ:

  - S / R            : زۆنی پاڵپشتی/بەرگری، دروستکراو لە سویمنگ های/لۆکان
  - Valid S / Valid R : زۆنێک کە جارێک تاقیکراوەتەوە و ڕاگیراوە (نەشکاوە)
  - PO2               : دووەم جار دەستدان بە زۆنەکە (Power of 2nd touch)
  - SBR / RBS         : شکانی زۆن و گۆڕینی ڕۆڵی
  - Inversion (I.VS/I.VR): زۆنێکی شکاو کە دواتر بە هێلی نوێ کاردەکات
  - Liquidity Sweep    : تێپەڕینی نرخ بۆ دەرەوەی های/لۆیەکی گرنگ و گەڕانەوە

تێبینی: ئەمە خوێندنەوەیەکی ئۆتۆماتیکییە، نەک وەرگێڕانێکی ١٠٠٪. هیچ ستراتیژیەک
گەرەنتی قازانج ناکات.
"""

from typing import List, Dict, Optional
from utils.candles import find_swing_points, is_bullish, is_bearish


def build_zones(
    candles: List[Dict],
    left: int = 2,
    right: int = 2,
    merge_tolerance_pct: float = 0.0015,
) -> List[Dict]:
    swings = find_swing_points(candles, left=left, right=right)
    zones = []

    for s in swings:
        zone_type = "resistance" if s["type"] == "high" else "support"
        price = s["price"]
        merged = False
        for z in zones:
            if z["type"] != zone_type:
                continue
            mid = (z["low"] + z["high"]) / 2
            if abs(price - mid) / mid <= merge_tolerance_pct:
                z["low"] = min(z["low"], price)
                z["high"] = max(z["high"], price)
                z["touches"] += 1
                z["last_index"] = s["index"]
                merged = True
                break
        if not merged:
            zones.append(
                {
                    "type": zone_type,
                    "low": price,
                    "high": price,
                    "touches": 1,
                    "first_index": s["index"],
                    "last_index": s["index"],
                    "status": "fresh",
                }
            )
    return zones


def _mid(zone: Dict) -> float:
    return (zone["low"] + zone["high"]) / 2


def mark_zone_states(zones: List[Dict], candles: List[Dict]) -> List[Dict]:
    for zone in zones:
        touches_after_break = 0
        broken = False
        flipped = False
        for c in candles[zone["last_index"] + 1 :]:
            if zone["type"] == "support":
                if c["close"] < zone["low"]:
                    broken = True
                elif broken and zone["low"] <= c["close"] <= zone["high"]:
                    touches_after_break += 1
                elif broken and c["high"] >= zone["low"] and c["close"] > zone["high"]:
                    flipped = True
            else:
                if c["close"] > zone["high"]:
                    broken = True
                elif broken and zone["low"] <= c["close"] <= zone["high"]:
                    touches_after_break += 1
                elif broken and c["low"] <= zone["high"] and c["close"] < zone["low"]:
                    flipped = True

        if flipped:
            zone["status"] = "flipped"
            zone["new_role"] = "resistance" if zone["type"] == "support" else "support"
        elif broken:
            zone["status"] = "broken"
        elif zone["touches"] >= 2:
            zone["status"] = "po2"
        else:
            zone["status"] = "valid"

        zone["retest_after_break"] = touches_after_break
    return zones


def detect_liquidity_sweep(candles: List[Dict], lookback: int = 20) -> Optional[Dict]:
    if len(candles) < lookback + 1:
        return None

    last = candles[-1]
    window = candles[-(lookback + 1) : -1]
    recent_high = max(c["high"] for c in window)
    recent_low = min(c["low"] for c in window)

    if last["high"] > recent_high and last["close"] < recent_high:
        return {"type": "bearish_sweep", "level": recent_high, "bias": "SELL"}
    if last["low"] < recent_low and last["close"] > recent_low:
        return {"type": "bullish_sweep", "level": recent_low, "bias": "BUY"}
    return None


def get_snrz_signal(candles: List[Dict]) -> Dict:
    if len(candles) < 30:
        return {"bias": "NONE", "reason": "کاندڵی پێویست کەمە", "zone": None}

    zones = build_zones(candles)
    zones = mark_zone_states(zones, candles)
    last_price = candles[-1]["close"]

    sweep = detect_liquidity_sweep(candles)
    if sweep:
        return {"bias": sweep["bias"], "reason": f"liquidity_sweep@{sweep['level']:.2f}", "zone": sweep}

    for z in zones:
        if z["status"] == "flipped" and z.get("retest_after_break", 0) >= 1:
            if abs(last_price - _mid(z)) / last_price < 0.01:
                bias = "BUY" if z["new_role"] == "support" else "SELL"
                tag = "RBS" if bias == "BUY" else "SBR"
                return {"bias": bias, "reason": f"{tag}@{_mid(z):.2f}", "zone": z}

    for z in zones:
        if z["status"] == "po2" and abs(last_price - _mid(z)) / last_price < 0.01:
            bias = "BUY" if z["type"] == "support" else "SELL"
            return {"bias": bias, "reason": f"PO2@{_mid(z):.2f}", "zone": z}

    for z in zones:
        if z["status"] == "valid" and abs(last_price - _mid(z)) / last_price < 0.008:
            bias = "BUY" if z["type"] == "support" else "SELL"
            return {"bias": bias, "reason": f"valid_{z['type']}@{_mid(z):.2f}", "zone": z}

    return {"bias": "NONE", "reason": "هیچ زۆنێکی چالاک لە نزیکی نرخی ئێستادا نییە", "zone": None}