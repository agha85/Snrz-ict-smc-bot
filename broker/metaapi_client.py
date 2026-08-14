"""
MetaApi Client
--------------
پۆشەیەک بۆ SDKـی metaapi-cloud-sdk — پەیوەندی، وەرگرتنی کاندڵ، وەرگرتنی
زانیاری هەژمار، و ناردنی ئۆردەر.

پێویستی بە ئەم Environment Variableـانەیە:
  METAAPI_TOKEN
  METAAPI_ACCOUNT_ID_DEMO / METAAPI_ACCOUNT_ID_REAL
  یان بۆ provisioning ئۆتۆماتیک: MT5_LOGIN, MT5_PASSWORD, MT5_SERVER
"""

import os
from typing import List, Dict, Optional
from metaapi_cloud_sdk import MetaApi
from utils.logger import get_logger
import config

logger = get_logger("metaapi_client")

_TF_MAP = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1H": "1h",
    "4H": "4h",
    "1D": "1d",
    "1W": "1w",
}


class MetaApiClient:
    def __init__(self):
        if not config.METAAPI_TOKEN:
            raise RuntimeError("METAAPI_TOKEN دانەنراوە لە Environment Variables")
        self.api = MetaApi(config.METAAPI_TOKEN)
        self.account = None
        self.connection = None

    async def _get_or_create_account(self):
        account_id = config.METAAPI_ACCOUNT_ID
        if account_id:
            logger.info("پەیوەندی بە هەژمارە هەبووەکە: %s", account_id)
            return await self.api.metatrader_account_api.get_account(account_id)

        login = os.getenv("MT5_LOGIN")
        password = os.getenv("MT5_PASSWORD")
        server = os.getenv("MT5_SERVER")
        if not (login and password and server):
            raise RuntimeError(
                "نە METAAPI_ACCOUNT_ID_* هەیە و نە MT5_LOGIN/PASSWORD/SERVER — "
                "یەکێکیان دابنێ لە Railway Environment Variables."
            )
        logger.info("دروستکردنی هەژمارێکی نوێ لە MetaApi بۆ login=%s server=%s", login, server)
        account = await self.api.metatrader_account_api.create_account(
            {
                "login": login,
                "password": password,
                "server": server,
                "platform": "mt5",
                "magic": 987654,
                "reliability": "regular",
                "name": f"snrz-ict-smc-bot-{config.ACCOUNT_MODE}",
            }
        )
        return account

    async def connect(self):
        self.account = await self._get_or_create_account()

        logger.info("دیپلۆیکردنی هەژمار (ئەگەر پێویست بێت)...")
        if self.account.state != "DEPLOYED":
            await self.account.deploy()

        logger.info("چاوەڕوانی پەیوەندیدانی هەژمار بە MT5...")
        await self.account.wait_connected()

        self.connection = self.account.get_rpc_connection()
        await self.connection.connect()
        logger.info("چاوەڕوانی هاوکاتکردنی داتا (synchronize)...")
        await self.connection.wait_synchronized()
        logger.info("✅ پەیوەندی بە MT5 سەرکەوتوو بوو.")

    async def fetch_candles(self, symbol: str, timeframe: str, limit: int = 200) -> List[Dict]:
        tf = _TF_MAP.get(timeframe, timeframe)
        raw = await self.account.get_historical_candles(symbol=symbol, timeframe=tf, start_time=None, limit=limit)
        candles = [
            {
                "time": c["time"],
                "open": c["open"],
                "high": c["high"],
                "low": c["low"],
                "close": c["close"],
            }
            for c in raw
        ]
        return candles

    async def get_balance(self) -> float:
        info = await self.connection.get_account_information()
        return float(info["balance"])

    async def get_symbol_specification(self, symbol: str) -> Dict:
        spec = await self.connection.get_symbol_specification(symbol)
        return spec

    async def get_open_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        positions = await self.connection.get_positions()
        if symbol:
            positions = [p for p in positions if p["symbol"] == symbol]
        return positions

    async def place_order(self, bias: str, symbol: str, volume: float, sl: float, tp: float):
        if config.DRY_RUN:
            logger.info(
                "🧪 DRY_RUN چالاکە — ئۆردەری ڕاستەقینە نانێردرێت: %s %s vol=%.2f sl=%.2f tp=%.2f",
                bias, symbol, volume, sl, tp,
            )
            return {"dry_run": True}

        if bias == "BUY":
            result = await self.connection.create_market_buy_order(
                symbol=symbol, volume=volume, stop_loss=sl, take_profit=tp
            )
        else:
            result = await self.connection.create_market_sell_order(
                symbol=symbol, volume=volume, stop_loss=sl, take_profit=tp
            )
        logger.info("✅ ئۆردەر نێردرا: %s", result)
        return result