"""
فەنکشنە هاوبەشەکان بۆ شیکاریکردنی کاندڵ — بەکاردێت لە هەر سێ ستراتیژیەکە
(SNRZ / ICT / SMC) تاوەکو یەک جۆر دیتنی سویمنگ بەکاربێت و ئەنجامەکان
لەگەڵ یەکتری بگونجێن.

هەر کاندڵێک بریتیە لە dict: {"time", "open", "high", "low", "close"}
لیستی کاندڵەکان بە ڕیزبەندی کات (کۆنترین یەکەم) دەبێت.
"""

from typing import List, Dict


def find_swing_points(candles: List[Dict], left: int = 2, right: int = 2):
    """
    دۆزینەوەی سویمنگ های/لۆ (fractal) — خاڵێک بە بەراورد لەگەڵ N کاندڵی
    چەپ و N کاندڵی ڕاستەوە خۆی بەرزترین/نزمترینە.

    دەگەڕێتەوە: لیستی dict {"index", "price", "type": "high"/"low", "time"}
    """
    swings = []
    n = len(candles)
    for i in range(left, n - right):
        window = candles[i - left : i + right + 1]
        high_i = candles[i]["high"]
        low_i = candles[i]["low"]

        if high_i == max(c["high"] for c in window):
            swings.append(
                {"index": i, "price": high_i, "type": "high", "time": candles[i]["time"]}
            )
        if low_i == min(c["low"] for c in window):
            swings.append(
                {"index": i, "price": low_i, "type": "low", "time": candles[i]["time"]}
            )
    return swings


def is_bullish(candle: Dict) -> bool:
    return candle["close"] > candle["open"]


def is_bearish(candle: Dict) -> bool:
    return candle["close"] < candle["open"]


def body_range(candle: Dict):
    return min(candle["open"], candle["close"]), max(candle["open"], candle["close"])


def zones_overlap(z1_low, z1_high, z2_low, z2_high) -> bool:
    return z1_low <= z2_high and z2_low <= z1_high