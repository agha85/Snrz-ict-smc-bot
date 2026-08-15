"""
MTAPI.io Client
----------------
پۆشەیەک بۆ mt5.mtapi.io — REST API ی سادە بۆ MT5، بەبێ هیچ SDKیەکی تایبەت.
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
        self.client = httpx.AsyncClient(timeout=30.0)

    async def connect(self):
        params = {"user": self.login, "password": self.password, "server": self.server}
        resp = await self.client.get(f"{BASE_URL}/ConnectEx", params=params)
        resp.raise_for_status()
        self.token = resp.text.strip().strip('"')
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

    async def get_balance(self) -> float:
        resp = await self.client.get(f"{BASE_URL}/AccountSummary", params={"id": self.token})
        resp.raise_for_status()
        data = resp.json()
        return float(data.get("balance", 0))

    async def get_symbol_specification(self, symbol: str) -> Dict:
        try:
            resp = await self.client.get(
                f"{BASE_URL}/SymbolParams", params={"id": self.token, "symbol": symbol}
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "contractSize": float(data.get("contractSize", data.get("ContractSize", 100))),
                "volumeStep": float(data.get("volumeStep", data.get("VolumeStep", 0.01))),
                "minVolume": float(data.get("volumeMin", data.get("VolumeMin", 0.01))),
                "maxVolume": float(data.get("volumeMax", data.get("VolumeMax", 100))),
            }
        except Exception:
            logger.warning("نەتوانرا SymbolParams وەربگیرێت — نرخی بنەڕەت بەکاردێت.")
            return {"contractSize": 100, "volumeStep": 0.01, "minVolume": 0.01, "maxVolume": 100}

    async def get_open_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        resp = await self.client.get(f"{BASE_URL}/OpenedOrders", params={"id": self.token})
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            return []
        if symbol:
            data = [p for p in data if p.get("symbol") == symbol]
        return data

    async def place_order(self, bias: str, symbol: str, volume: float, sl: float, tp: float):
        if config.DRY_RUN:
            logger.info(
                "🧪 DRY_RUN چالاکە — ئۆردەری ڕاستەقینە نانێردرێت: %s %s vol=%.2f sl=%.2f tp=%.2f",
                bias, symbol, volume, sl, tp,
            )
            return {"dry_run": True}

        operation = 0 if bias == "BUY" else 1
        params = {
            "id": self.token,
            "symbol": symbol,
            "operation": operation,
            "volume": volume,
            "stoploss": sl,
            "takeprofit": tp,
        }
        resp = await self.client.get(f"{BASE_URL}/OrderSendSafe", params=params)
        resp.raise_for_status()
        result = resp.json()
        logger.info("✅ ئۆردەر نێردرا: %s", result)
        return result