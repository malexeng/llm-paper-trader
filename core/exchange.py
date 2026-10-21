"""
core/exchange.py
Kraken connector — fetches OHLCV candles, current prices, places orders.
ccxt-based, paper trading by default.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional
import ccxt.async_support as ccxt

logger = logging.getLogger("exchange")

TIMEFRAME_MAP = {
    "1m": 1, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "4h": 240, "1d": 1440
}


class KrakenMarket:

    def __init__(self, config: dict):
        self.paper = config.get("paper_trading", True)
        self.timeframe = config.get("candle_timeframe", "5m")
        self.lookback  = config.get("candles_lookback", 50)

        opts = {"enableRateLimit": True, "rateLimit": 300}
        if not self.paper:
            opts["apiKey"]  = config.get("api_key", "")
            opts["secret"]  = config.get("api_secret", "")

        self.client = ccxt.kraken(opts)
        self._markets_loaded = False
        self._paper_balance = {"USDT": 2000.0, "USD": 2000.0,
                               "BTC": 0.0, "ETH": 0.0, "SOL": 0.0}

    async def load(self):
        await self.client.load_markets()
        self._markets_loaded = True
        logger.info("Kraken markets loaded ✓")

    async def get_candles(self, pair: str) -> List[Dict]:
        """Fetch OHLCV candles. Returns list of dicts."""
        try:
            raw = await self.client.fetch_ohlcv(
                pair, self.timeframe, limit=self.lookback
            )
            return [
                {
                    "timestamp": c[0],
                    "open":   float(c[1]),
                    "high":   float(c[2]),
                    "low":    float(c[3]),
                    "close":  float(c[4]),
                    "volume": float(c[5])
                }
                for c in raw
            ]
        except Exception as e:
            logger.error(f"Candle fetch failed ({pair}): {e}")
            return []

    async def get_price(self, pair: str) -> Optional[float]:
        try:
            t = await self.client.fetch_ticker(pair)
            return float(t["last"])
        except Exception as e:
            logger.debug(f"Price fetch error {pair}: {e}")
            return None

    async def get_balance(self) -> Dict[str, float]:
        if self.paper:
            return dict(self._paper_balance)
        try:
            bal = await self.client.fetch_balance()
            return {k: float(v["free"]) for k, v in bal.items()
                    if isinstance(v, dict) and float(v.get("free", 0)) > 0}
        except Exception as e:
            logger.error(f"Balance error: {e}")
            return {}

    async def place_order(
        self, pair: str, side: str, amount_usdc: float, price: float
    ) -> Optional[Dict]:
        """
        Places an order. Returns order dict or None.
        side: "buy" or "sell"
        amount_usdc: value in USDT/USD to trade
        """
        base = pair.split("/")[0]
        amount_base = amount_usdc / price
        fee_pct = 0.0026  # Kraken taker ~0.26%

        if self.paper:
            # Simulate paper fill
            if side == "buy":
                cost = amount_base * price * (1 + fee_pct)
                quote = pair.split("/")[1]
                if self._paper_balance.get(quote, 0) < cost:
                    logger.warning(f"Paper: insufficient {quote} balance")
                    return None
                self._paper_balance[quote] = self._paper_balance.get(quote, 0) - cost
                self._paper_balance[base]  = self._paper_balance.get(base, 0) + amount_base
            else:
                proceeds = amount_base * price * (1 - fee_pct)
                if self._paper_balance.get(base, 0) < amount_base:
                    logger.warning(f"Paper: insufficient {base} balance")
                    return None
                self._paper_balance[base]  = self._paper_balance.get(base, 0) - amount_base
                quote = pair.split("/")[1]
                self._paper_balance[quote] = self._paper_balance.get(quote, 0) + proceeds

            return {
                "id": f"PAPER_{int(time.time()*1000)}",
                "symbol": pair, "side": side,
                "amount": round(amount_base, 8),
                "price": price,
                "cost": round(amount_base * price, 4),
                "paper": True, "status": "closed"
            }

        # Live order
        try:
            order = await self.client.create_market_order(pair, side, amount_base)
            return order
        except Exception as e:
            logger.error(f"Live order failed ({side} {pair}): {e}")
            return None

    async def close(self):
        await self.client.close()
