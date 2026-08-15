"""
Confirmation Engine (Scalping Mode)
-------------------------------------
یاسا: ترەید کاتێک دەکرێت کە بەلایەنی کەم STRATEGY_MIN_AGREE (بنەڕەت: ٢) لە ٣
ستراتیژیەکان (SNRZ + ICT + SMC) لە هەمان ئاراستەدا کۆنفیرم بن — لە
تایمفرەیمە شیکاریەکاندا، پاشان لە تایمفرەیمی کۆنفیرمەیشندا.
"""

from typing import Dict, List
import config
from strategies.snrz import get_snrz_signal
from strategies.ict import get_ict_signal
from strategies.smc import get_smc_signal


def strategies_agree_on_timeframe(candles: List[Dict]) -> Dict:
    snrz = get_snrz_signal(candles)
    ict = get_ict_signal(candles)
    smc = get_smc_signal(candles)

    biases = [snrz["bias"], ict["bias"], smc["bias"]]
    detail = {"snrz": snrz, "ict": ict, "smc": smc}

    buy_count = sum(1 for b in biases if b == "BUY")
    sell_count = sum(1 for b in biases if b == "SELL")
    min_agree = config.STRATEGY_MIN_AGREE

    if buy_count >= min_agree and buy_count > sell_count:
        return {"bias": "BUY", "detail": detail}
    if sell_count >= min_agree and sell_count > buy_count:
        return {"bias": "SELL", "detail": detail}
    return {"bias": "NONE", "detail": detail}


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
            "reason": f"شیکاری تایمفرەیمەکان یەکناگرن (BUY={buy_votes}, SELL={sell_votes})",
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