"""
Main
----
لووپی سەرەکی بۆتەکە — بۆ هەموو ئەسێتەکانی SYMBOLS.
"""

import asyncio
import traceback

import config
from utils.logger import get_logger
from broker.mtapi_client import MtApiClient
from strategies.confirmation import get_overall_confirmation
from risk_manager import calculate_sl_tp, calculate_lot_size

logger = get_logger("main")


async def run_cycle_for_symbol(client: MtApiClient, symbol: str):
    candles_by_tf = {}
    for tf in config.ANALYSIS_TIMEFRAMES:
        candles_by_tf[tf] = await client.fetch_candles(symbol, tf, limit=200)

    confirmation_candles = await client.fetch_candles(
        symbol, config.CONFIRMATION_TIMEFRAME, limit=200
    )

    result = get_overall_confirmation(
        candles_by_analysis_tf=candles_by_tf,
        candles_confirmation_tf=confirmation_candles,
    )

    logger.info("[%s] بایاسی ئێستا: %s | هۆکار: %s", symbol, result["bias"], result["reason"])

    if result["bias"] == "NONE":
        return

    open_positions = await client.get_open_positions(symbol)
    if len(open_positions) >= config.MAX_OPEN_TRADES:
        logger.info("[%s] پۆزیشنی کراوە هەیە (%d) — ترەیدی نوێ ناکرێت.", symbol, len(open_positions))
        return

    entry_price = confirmation_candles[-1]["close"]
    zone = result.get("confirmation_detail", {}).get("snrz", {}).get("zone")
    sl_tp = calculate_sl_tp(entry_price, result["bias"], zone)

    balance = await client.get_balance()
    spec = await client.get_symbol_specification(symbol)
    contract_size = float(spec.get("contractSize", 100))
    volume_step = float(spec.get("volumeStep", 0.01))
    min_volume = float(spec.get("minVolume", 0.01))
    max_volume = float(spec.get("maxVolume", 100))

    lot = calculate_lot_size(
        balance=balance,
        entry_price=entry_price,
        sl_price=sl_tp["sl"],
        contract_size=contract_size,
        volume_step=volume_step,
        min_volume=min_volume,
        max_volume=max_volume,
    )

    if lot <= 0:
        logger.warning("[%s] قەبارەی لۆت سفرە — ترەید ناکرێت.", symbol)
        return

    logger.info(
        "🚀 [%s] %s | entry=%.2f sl=%.2f tp=%.2f lot=%.2f balance=%.2f",
        symbol, result["bias"], entry_price, sl_tp["sl"], sl_tp["tp"], lot, balance,
    )

    await client.place_order(result["bias"], symbol, lot, sl_tp["sl"], sl_tp["tp"])


async def run_cycle(client: MtApiClient):
    for symbol in config.SYMBOLS:
        try:
            await run_cycle_for_symbol(client, symbol)
        except Exception:
            logger.error("[%s] هەڵەیەک ڕوویدا:\n%s", symbol, traceback.format_exc())


async def main():
    logger.info("=" * 60)
    logger.info(
        "SNRZ + ICT + SMC Bot — symbols=%s mode=%s dry_run=%s",
        config.SYMBOLS, config.ACCOUNT_MODE, config.DRY_RUN,
    )
    if config.RISK_PERCENT_PER_TRADE >= 20:
        logger.warning(
            "⚠️⚠️⚠️ ڕیسکی %.1f%% لە هەر ترەیدێکدا دانراوە — زۆر مەترسیدارە.",
            config.RISK_PERCENT_PER_TRADE,
        )
    logger.info("=" * 60)

    client = MtApiClient()
    await client.connect()

    while True:
        try:
            await run_cycle(client)
        except Exception:
            logger.error("هەڵەیەک ڕوویدا لە run_cycle:\n%s", traceback.format_exc())
        await asyncio.sleep(config.POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())