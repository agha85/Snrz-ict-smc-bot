"""
MTAPI.io Client
----------------
پۆشەیەک بۆ mt5.mtapi.io — REST API ی سادە بۆ MT5، بەبێ هیچ SDKیەکی تایبەت.
تەنها داواکاری HTTP ئاسایی بەکاردێت (httpx).

پێویستی بە ئەم Environment Variableـانەیە:
  MT5_LOGIN, MT5_PASSWORD, MT5_SERVER
"""

import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
import httpx
from utils.logger import get_logger
import config

logger = get_logger("mtapi_client")

BASE_URL = "https://mt5.mtapi.io"

_TF_MINUTES = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1H": 60,
    "4H": 240,
    "1D": 1440,
    "1W": 10080,
}

OP_BUY = 0
OP_SELL = 1
OP_BUY_LIMIT = 2
OP_SELL_LIMIT = 3


class MtApiClient:
    def __init__(self):
        self.login = os.getenv("MT5_LOGIN")
        self.password = os.getenv("MT5_PASSWORD")
        self.server = os.getenv("MT5_SERVER")
        if not (self.login and self.password and self.server):
            raise RuntimeError(
                "MT5_LOGIN / MT5_PASSWORD / MT5_SERVER دانەنراون لە Environment Variables"
            )
        self.token: Optional[str] = None
        self.client = httpx.AsyncClient(timeout=60.0)

    async def connect(self):
        params = {"user": self.login, "password": self.password, "server": self.server}
        resp = await self.client.get(f"{BASE_URL}/ConnectEx", params=params)
        resp.raise_for_status()
        raw = resp.text.strip().strip('"')

        if raw.startswith("{"):
            logger.error("❌ لۆگیندان بۆ MT5 شکستی هێنا. وەڵامی سێرڤەر: %s", raw)
            raise RuntimeError(f"MT5 login failed: {raw}")

        self.token = raw
        logger.info("✅ پەیوەندی بە MT5 سەرکەوتوو بوو (mtapi.io). token=%s...", self.token[:8])

    async def fetch_candles(self, symbol: str, timeframe: str, limit: int = 200) -> List[Dict]:
        tf_minutes = _TF_MINUTES.get(timeframe, 60)
        now = datetime.now(timezone.utc)
        from_time = now - timedelta(minutes=tf_minutes * limit)

        params = {
            "id": self.token,
            "symbol": symbol,
            "from": from_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "to": now.strftime("%Y-%m-%dT%H:%M:%S"),
            "timeFrame": tf_minutes,
        }
        resp = await self.client.get(f"{BASE_URL}/PriceHistoryV2", params=params)
        resp.raise_for_status()
        data = resp.json()

        candles = [
            {
                "time": c.get("time"),
                "open": float(c.get("openPrice", 0)),
                "high": float(c.get("highPrice", 0)),
                "low": float(c.get("lowPrice", 0)),
                "close": float(c.get("closePrice", 0)),
            }
            for c in data
            if c.get("closePrice") not in (None, 0) or c.get("openPrice") not in (None, 0)
        ]
        return candles

    async def get_last_quote(self, symbol: str) -> Dict:
        resp = await self.client.get(f"{BASE_URL}/GetQuote", params={"id": self.token, "symbol": symbol})
        resp.raise_for_status()
        data = resp.json()
        bid = data.get("bid", data.get("Bid", data.get("bidPrice")))
        ask = data.get("ask", data.get("Ask", data.get("askPrice")))
        return {"bid": float(bid) if bid is not None else None, "ask": float(ask) if ask is not None else None}

    async def get_balance(self) -> float:
        resp = await self.client.get(f"{BASE_URL}/AccountSummary", params={"id": self.token})
        resp.raise_for_status()
        data = resp.json()
        return float(data.get("balance", 0))

    async def get_open_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        resp = await self.client.get(f"{BASE_URL}/OpenedOrders", params={"id": self.token})
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            return []
        if symbol:
            data = [p for p in data if p.get("symbol") == symbol]
        return data

    async def place_limit_order(
        self, symbol: str, bias: str, price: float, volume: float, sl: float
    ):
        if config.DRY_RUN:
            logger.info(
                "🧪 DRY_RUN — %s Limit نانێردرێت: %s price=%.2f vol=%.2f sl=%.2f",
                bias, symbol, price, volume, sl,
            )
            return {"dry_run": True}

        operation = OP_BUY_LIMIT if bias == "BUY" else OP_SELL_LIMIT
        params = {
            "id": self.token,
            "symbol": symbol,
            "operation": operation,
            "volume": volume,
            "price": price,
            "stoploss": sl,
            "takeprofit": 0,
        }
        resp = await self.client.get(f"{BASE_URL}/OrderSendSafe", params=params)
        resp.raise_for_status()
        result = resp.json()
        logger.info("✅ Limit نێردرا: %s @ %.2f -> %s", bias, price, result)
        return result

    async def cancel_pending_order(self, ticket):
        if config.DRY_RUN:
            logger.info("🧪 DRY_RUN — ئۆردەری چاوەڕوان هەڵناگیرێت: ticket=%s", ticket)
            return {"dry_run": True}

        params = {"id": self.token, "ticket": ticket}
        resp = await self.client.get(f"{BASE_URL}/OrderCancelTask", params=params)
        resp.raise_for_status()
        result = resp.json()
        logger.info("🗑️ ئۆردەری چاوەڕوان هەڵگیرا: ticket=%s | %s", ticket, result)
        return result

    async def modify_stop_loss(self, ticket, new_sl: float, take_profit: float = 0):
        if config.DRY_RUN:
            logger.info("🧪 DRY_RUN — SL ناگوازرێتەوە بۆ ticket=%s new_sl=%.2f", ticket, new_sl)
            return {"dry_run": True}

        params = {
            "id": self.token,
            "ticket": ticket,
            "stoploss": new_sl,
            "takeprofit": take_profit,
        }
        resp = await self.client.get(f"{BASE_URL}/OrderModifySafe", params=params)
        resp.raise_for_status()
        result = resp.json()
        logger.info("✅ SL گۆڕدرا: ticket=%s -> sl=%.2f | %s", ticket, new_sl, result)
        return result