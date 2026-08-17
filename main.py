"""
Main (Grid + Trailing Strategy — SNRZ only)
---------------------------------------------
  ١. کاندڵی 30m/5m + کۆنفیرمەیشنی 1m وەردەگرێت، تەنها بەپێی SNRZ
  ٢. ئەگەر کۆنفیرم بوو و هیچ پۆزیشنێکی کراوە نییە بۆ ئەو ئەسێتە،
     GRID_ORDERS_COUNT ئۆردەری Limit بەسەر پانتایی زۆنەکەدا دادەنێت
  ٣. ئەگەر پۆزیشنی کراوە هەبوو، پشکنین دەکات ئایا پێویستە ستۆپەکان
     بگوازرێتەوە (trailing) دوای ئەوەی GRID_TRAIL_TRIGGER_PIPS چووە قازانج
"""

import asyncio
import traceback

import config
from utils.logger import get_logger
from broker.mtapi_client import MtApiClient
from strategies.confirmation import get_overall_confirmation

logger = get_logger("main")


def extract_zone_bounds(zone, fallback_price: float):
    if zone and isinstance(zone, dict) and "low" in zone and "high" in zone:
        return float(zone["low"]), float(zone["high"])
    return fallback_price * 0.997, fallback_price * 1.003


def generate_grid_prices(zone_low: float, zone_high: float, count: int):
    if count <= 1:
        return [(zone_low + zone_high) / 2]
    step = (zone_high - zone_low) / (count - 1)
    return [zone_low + i * step for i in range(count)]


async def place_grid_orders(client: MtApiClient, symbol: str, bias: str, zone_low: float, zone_high: float):
    pip = config.PIP_SIZES.get(symbol, config.DEFAULT_PIP_SIZE)
    prices = generate_grid_prices(zone_low, zone_high, config.GRID_ORDERS_COUNT)

    logger.info(
        "🚀 [%s] دانانی گریدی %s — %d ئۆردەر لە نێوان %.2f و %.2f",
        symbol, bias, len(prices), zone_low, zone_high,
    )

    for price in prices:
        if bias == "BUY":
            sl = price - config.GRID_SL_PIPS * pip
        else:
            sl = price + config.GRID_SL_PIPS * pip
        try:
            await client.place_limit_order(symbol, bias, price, config.GRID_LOT_SIZE, sl)
        except Exception:
            logger.error("[%s] هەڵە لە ناردنی ئۆردەرێکی گرید:\n%s", symbol, traceback.format_exc())


async def manage_trailing_stops(client: MtApiClient, symbol: str):
    positions = await client.get_open_positions(symbol)
    if not positions:
        return

    pip = config.PIP_SIZES.get(symbol, config.DEFAULT_PIP_SIZE)

    try:
        quote = await client.get_last_quote(symbol)
    except Exception:
        logger.warning("[%s] نەتوانرا نرخی ئێستا وەربگیرێت بۆ trailing.", symbol)
        return

    for pos in positions:
        ticket = pos.get("ticket", pos.get("Ticket"))
        entry = pos.get("openPrice", pos.get("OpenPrice", pos.get("price")))
        current_sl = pos.get("sl", pos.get("stopLoss", pos.get("StopLoss", 0))) or 0
        pos_type = pos.get("type", pos.get("cmd", pos.get("Type")))
        is_buy = pos_type in (0, "0", "buy", "Buy", "BUY")

        if ticket is None or entry is None:
            continue
        entry = float(entry)

        current_price = quote.get("bid") if is_buy else quote.get("ask")
        if current_price is None:
            continue

        profit_pips = (current_price - entry) / pip if is_buy else (entry - current_price) / pip

        if profit_pips >= config.GRID_TRAIL_TRIGGER_PIPS:
            target_sl = (
                entry + config.GRID_TRAIL_SL_PIPS * pip
                if is_buy
                else entry - config.GRID_TRAIL_SL_PIPS * pip
            )
            already_moved = (current_sl >= target_sl) if is_buy else (0 < current_sl <= target_sl)
            if not already_moved:
                logger.info(
                    "[%s] 🔒 گواستنەوەی ستۆپ بۆ ticket=%s | قازانج=%.1f پیپ -> SL نوێ=%.2f",
                    symbol, ticket, profit_pips, target_sl,
                )
                try:
                    await client.modify_stop_loss(ticket, target_sl)
                except Exception:
                    logger.error("[%s] هەڵە لە گواستنەوەی ستۆپ:\n%s", symbol, traceback.format_exc())


async def run_cycle_for_symbol(client: MtApiClient, symbol: str):
    candles_by_tf = {}
    for tf in config.ANALYSIS_TIMEFRAMES:
        candles_by_tf[tf] = await client.fetch_candles(symbol, tf, limit=200)

    confirmation_candles = await client.fetch_candles(symbol, config.CONFIRMATION_TIMEFRAME, limit=200)

    open_positions = await client.get_open_positions(symbol)

    if open_positions:
        logger.info("[%s] %d پۆزیشنی کراوە هەیە — پشکنینی trailing.", symbol, len(open_positions))
        await manage_trailing_stops(client, symbol)
        return

    result = get_overall_confirmation(
        candles_by_analysis_tf=candles_by_tf,
        candles_confirmation_tf=confirmation_candles,
    )
    logger.info("[%s] بایاسی ئێستا: %s | هۆکار: %s", symbol, result["bias"], result["reason"])

    if result["bias"] == "NONE":
        return

    entry_price = confirmation_candles[-1]["close"]
    zone = result.get("confirmation_detail", {}).get("snrz", {}).get("zone")
    zone_low, zone_high = extract_zone_bounds(zone, entry_price)

    await place_grid_orders(client, symbol, result["bias"], zone_low, zone_high)


async def run_cycle(client: MtApiClient):
    for symbol in config.SYMBOLS:
        try:
            await run_cycle_for_symbol(client, symbol)
        except Exception:
            logger.error("[%s] هەڵەیەک ڕوویدا:\n%s", symbol, traceback.format_exc())


async def main():
    logger.info("=" * 60)
    logger.info(
        "SNRZ Grid Bot — symbols=%s mode=%s dry_run=%s grid=%d lot=%.2f sl=%.0fpip trail=%.0f->%.0fpip",
        config.SYMBOLS, config.ACCOUNT_MODE, config.DRY_RUN,
        config.GRID_ORDERS_COUNT, config.GRID_LOT_SIZE, config.GRID_SL_PIPS,
        config.GRID_TRAIL_TRIGGER_PIPS, config.GRID_TRAIL_SL_PIPS,
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