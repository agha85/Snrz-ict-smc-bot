"""
Confirmation Engine (SNRZ only)
---------------------------------
تەنها ستراتیژی SNRZ بەکاردێت (ICT و SMC لابران، بەپێی داواکاری).
"""

from typing import Dict, List
import config
from strategies.snrz import get_snrz_signal


def strategies_agree_on_timeframe(candles: List[Dict]) -> Dict:
    result = get_snrz_signal(candles)
    return {"bias": result["bias"], "detail": {"snrz": result}}


def get_overall_confirmation(
    candles_by_analysis_tf: Dict[str, List[Dict]],
    candles_confirmation_tf: List[Dict],
    min_agreeing_timeframes: int = None,
) -> Dict:
    if min_agreeing_timeframes is None:
        min_agreeing_timeframes = config.MIN_AGREEING_TIMEFRAMES

    votes = {}
    for tf, candles in candles_by_analysis_tf.items():
        if not candles or len(candles) < 30:
            votes[tf] = "NONE"
            continue
        result = strategies_agree_on_timeframe(candles)
        votes[tf] = result["bias"]

    buy_votes = sum(1 for v in votes.values() if v == "BUY")
    sell_votes = sum(1 for v in votes.values() if v == "SELL")

    bias_from_analysis = "NONE"
    if buy_votes >= min_agreeing_timeframes:
        bias_from_analysis = "BUY"
    elif sell_votes >= min_agreeing_timeframes:
        bias_from_analysis = "SELL"

    if bias_from_analysis == "NONE":
        return {
            "bias": "NONE",
            "reason": f"SNRZ تایمفرەیمەکان یەکناگرن (BUY={buy_votes}, SELL={sell_votes})",
            "votes": votes,
        }

    if not candles_confirmation_tf or len(candles_confirmation_tf) < 30:
        return {"bias": "NONE", "reason": "کاندڵی کۆنفیرمەیشن کەمە", "votes": votes}

    confirm_result = strategies_agree_on_timeframe(candles_confirmation_tf)
    if confirm_result["bias"] == bias_from_analysis:
        return {
            "bias": bias_from_analysis,
            "reason": f"analysis({votes}) + confirmation_tf کۆنفیرم کرا",
            "votes": votes,
            "confirmation_detail": confirm_result["detail"],
        }

    return {
        "bias": "NONE",
        "reason": f"بایاسی شیکاری {bias_from_analysis} بوو بەڵام تایمفرەیمی کۆنفیرمەیشن یەکناگرێت",
        "votes": votes,
    }