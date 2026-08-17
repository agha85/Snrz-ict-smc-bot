"""
Main (Grid + Trailing Strategy — SNRZ only)
---------------------------------------------
  ١. کاندڵی 30m/5m + کۆنفیرمەیشنی 1m وەردەگرێت، تەنها بەپێی SNRZ
  ٢. ئۆردەرەکان دابەش دەکات بۆ:
       - "پڕکراوە" (filled)   -> پۆزیشنی ڕاستەقینە، trailing بۆی جێبەجێ دەکرێت
       - "چاوەڕوان" (pending) -> ئۆردەری Limit کە هێشتا نەگاتووەتە نرخی خۆی
  ٣. ئەگەر پۆزیشنی پڕکراوە هەبوو -> trailing، پاشماوەی pendingـەکان هەڵدەگیردرێن
  ٤. ئەگەر تەنها pending هەبوو و (بایاسی نوێ جیاواز بوو یان کاتی زۆر
     تێپەڕیبوو) -> پاک دەکرێنەوە و لە زۆنی نوێدا دووبارە دادەنرێن
  ٥. ئەگەر هیچ نەبوو و کۆنفیرمەیشن هەبوو -> گریدی نوێ دادەنرێت
"""

import asyncio
import time
import traceback

import config
from utils.logger import get_logger
from broker.mtapi_client import MtApiClient
from strategies.confirmation import get_overall_confirmation

logger = get_logger("main")

_active_grid_state = {}

PENDING_TYPES_BUY = (2, 4)
PENDING_TYPES_SELL = (3, 5)
FILLED_TYPES = (0, 1)


def _get_type(pos):
    return pos.get("type", pos.get("cmd", pos.get("Type")))


def classify_positions(positions):
    filled, pending = [], []
    for p in positions:
        t = _get_type(p)
        try:
            t = int(t)
        except (TypeError, ValueError):
            t = None
        if t in FILLED_TYPES:
            filled.append(p)
        elif t in PENDING_TYPES_BUY or t in PENDING_TYPES_SELL:
            pending.append(p)
    return filled, pending


def infer_pending_bias(pending_positions):
    for p in pending_positions:
        try:
            t = int(_get_type(p))
        except (TypeError, ValueError):
            continue
        if t in PENDING_TYPES_BUY:
            return "BUY"
        if t in PENDING_TYPES_SELL:
            return "SELL"
    return None


def extract_zone_bounds(zone, fallback_price: float):
    if zone and isinstance(zone, dict) and "low" in zone and "high" in zone:
        return float(zone["low"]), float(zone["high"])
    return fallback_price * 0.997, fallback_price * 1.003


def generate_grid_prices(zone_low: float, zone_high: float, count: int):
    if count <= 1:
        return [(zone_low + zone_high) / 2]
    step = (zone_high - zone_low) / (count - 1)
    return [zone_low + i * step for i in range(count)]


async def cancel_all_pending(client: MtApiClient, symbol: str, pending_positions):
    for p in pending_positions:
        ticket = p.get("ticket", p.get("Ticket"))
        if ticket is None:
            continue
        try:
            await client.cancel_pending_order(ticket)
        except Exception:
            logger.error("[%s] هەڵە لە هەڵگرتنی ئۆردەری چاوەڕوان:\n%s", symbol, traceback.format_exc())


async def place_grid_orders(client: MtApiClient, symbol: str, bias: str, zone_low: float, zone_high: float):
    pip = config.PIP_SIZES.get(symbol, config.DEFAULT_PIP_SIZE)
    prices = generate_grid_prices(zone_low, zone_high, config.GRID_ORDERS_COUNT)

    logger.info(
        "🚀 [%s] دانانی گریدی %s — %d ئۆردەر لە نێوان %.2f و %.2f",
        symbol, bias, len(prices), zone_low, zone_high,
    )

    for price in prices:
        sl = price - config.GRID_SL_PIPS * pip if bias == "BUY" else price + config.GRID_SL_PIPS * pip
        try:
            await client.place_limit_order(symbol, bias, price, config.GRID_LOT_SIZE, sl)
        except Exception:
            logger.error("[%s] هەڵە لە ناردنی ئۆردەرێکی گرید:\n%s", symbol, traceback.format_exc())

    _active_grid_state[symbol] = {"bias": bias, "placed_at": time.time()}


async def manage_trailing_stops(client: MtApiClient, symbol: str, filled_positions):
    if not filled_positions:
        return
    pip = config.PIP_SIZES.get(symbol, config.DEFAULT_PIP_SIZE)
    try:
        quote = await client.get_last_quote(symbol)
    except Exception:
        logger.warning("[%s] نەتوانرا نرخی ئێستا وەربگیرێت بۆ trailing.", symbol)
        return

    for pos in filled_positions:
        ticket = pos.get("ticket", pos.get("Ticket"))
        entry = pos.get("openPrice", pos.get("OpenPrice", pos.get("price")))
        current_sl = pos.get("sl", pos.get("stopLoss", pos.get("StopLoss", 0))) or 0
        t = _get_type(pos)
        try:
            t = int(t)
        except (TypeError, ValueError):
            t = 0
        is_buy = t == 0

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

    all_positions = await client.get_open_positions(symbol)
    filled, pending = classify_positions(all_positions)

    result = get_overall_confirmation(
        candles_by_analysis_tf=candles_by_tf,
        candles_confirmation_tf=confirmation_candles,
    )
    logger.info(
        "[%s] بایاسی ئێستا: %s | هۆکار: %s | filled=%d pending=%d",
        symbol, result["bias"], result["reason"], len(filled), len(pending),
    )

    if filled:
        if pending:
            logger.info("[%s] پۆزیشن پڕکراوەتەوە — پاشماوەی %d ئۆردەری چاوەڕوان هەڵدەگیردرێن.", symbol, len(pending))
            await cancel_all_pending(client, symbol, pending)
        await manage_trailing_stops(client, symbol, filled)
        return

    entry_price = confirmation_candles[-1]["close"]
    new_bias = result["bias"]

    if pending:
        tracked = _active_grid_state.get(symbol)
        pending_bias = infer_pending_bias(pending)
        age_minutes = (time.time() - tracked["placed_at"]) / 60 if tracked else None

        bias_changed = new_bias != "NONE" and new_bias != pending_bias
        too_old = age_minutes is not None and age_minutes >= config.GRID_MAX_AGE_MINUTES

        if bias_changed or too_old:
            logger.info(
                "[%s] گریدی چاوەڕوان کۆن/نادروستە (bias_changed=%s, age=%s) — پاکی دەکەینەوە.",
                symbol, bias_changed, f"{age_minutes:.0f}m" if age_minutes is not None else "?",
            )
            await cancel_all_pending(client, symbol, pending)
            _active_grid_state.pop(symbol, None)
            if new_bias != "NONE":
                zone = result.get("confirmation_detail", {}).get("snrz", {}).get("zone")
                zone_low, zone_high = extract_zone_bounds(zone, entry_price)
                await place_grid_orders(client, symbol, new_bias, zone_low, zone_high)
        return

    if new_bias == "NONE":
        return

    zone = result.get("confirmation_detail", {}).get("snrz", {}).get("zone")
    zone_low, zone_high = extract_zone_bounds(zone, entry_price)
    await place_grid_orders(client, symbol, new_bias, zone_low, zone_high)


async def run_cycle(client: MtApiClient):
    for symbol in config.SYMBOLS:
        try:
            await run_cycle_for_symbol(client, symbol)
        except Exception:
            logger.error("[%s] هەڵەیەک ڕوویدا:\n%s", symbol, traceback.format_exc())


async def main():
    logger.info("=" * 60)
    logger.info(
        "SNRZ Grid Bot — symbols=%s mode=%s dry_run=%s grid=%d lot=%.2f sl=%.0fpip trail=%.0f->%.0fpip max_age=%.0fm",
        config.SYMBOLS, config.ACCOUNT_MODE, config.DRY_RUN,
        config.GRID_ORDERS_COUNT, config.GRID_LOT_SIZE, config.GRID_SL_PIPS,
        config.GRID_TRAIL_TRIGGER_PIPS, config.GRID_TRAIL_SL_PIPS, config.GRID_MAX_AGE_MINUTES,
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