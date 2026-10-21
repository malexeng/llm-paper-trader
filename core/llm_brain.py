"""
core/llm_brain.py
The "thinking machine" — sends market data to local LLM, gets structured trading decisions.
Works with Ollama (recommended) or LM Studio.
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional
import requests

logger = logging.getLogger("llm_brain")


@dataclass
class TradeDecision:
    pair: str
    action: str                  # "BUY", "SELL", "HOLD"
    confidence: int              # 0-100
    reasoning: str               # LLM's explanation
    entry_price: float
    stop_loss: float
    take_profit: float
    size_pct: float              # % of available balance to use
    raw_response: str = ""
    ts: int = field(default_factory=lambda: int(time.time() * 1000))


SYSTEM_PROMPT = """You are a disciplined crypto trading analyst.
Your job is to analyze market data and make clear, structured trading decisions.

RULES:
- Be decisive. Never be vague.
- Only recommend BUY or SELL when confidence is 70 or above.
- Otherwise recommend HOLD.
- Base decisions on technical indicators, not speculation.
- Always set stop_loss BELOW entry (for BUY) or ABOVE entry (for SELL).
- Take profit should be 2x the risk distance minimum.
- size_pct is what % of available balance to use (max 100).

RESPOND ONLY WITH VALID JSON. No extra text. No markdown. Example:
{
  "action": "BUY",
  "confidence": 82,
  "reasoning": "RSI oversold at 28, MACD bullish crossover forming, price bouncing off lower Bollinger Band. Strong setup.",
  "stop_loss_pct": 1.8,
  "take_profit_pct": 4.2,
  "size_pct": 50
}"""


class LLMBrain:

    def __init__(self, config: dict):
        self.provider   = config.get("llm_provider", "ollama")
        self.host       = config.get("llm_host", "http://localhost:11434")
        self.model      = config.get("llm_model", "qwen2.5:14b")
        self.timeout    = config.get("llm_timeout", 30)
        self.temperature = config.get("llm_temperature", 0.2)
        self.min_confidence = config.get("min_confidence", 70)
        self.stop_loss_pct  = config.get("stop_loss_pct", 2.0)
        self.take_profit_pct = config.get("take_profit_pct", 4.0)
        self.reasoning_log: list = []   # Store all LLM thoughts for dashboard

    def is_available(self) -> bool:
        """Check if LLM backend is reachable."""
        try:
            url = f"{self.host}/api/tags" if self.provider == "ollama" else f"{self.host}/v1/models"
            r = requests.get(url, timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def analyze(self, pair: str, market_context: str, current_price: float) -> TradeDecision:
        """
        Send market data to LLM and get a trading decision.
        Returns a HOLD decision if LLM fails or confidence is too low.
        """
        prompt = f"""Analyze this crypto market data and give a trading decision.

Pair: {pair}
Current Price: ${current_price:,.4f}

{market_context}

Based on this data, what is your trading decision?"""

        raw = self._call_llm(prompt)

        if not raw:
            logger.warning(f"LLM returned empty response for {pair}")
            return self._hold_decision(pair, current_price, "LLM unavailable")

        decision = self._parse_response(raw, pair, current_price)

        # Log for dashboard
        self.reasoning_log.insert(0, {
            "pair": pair,
            "action": decision.action,
            "confidence": decision.confidence,
            "reasoning": decision.reasoning,
            "ts": decision.ts,
            "price": current_price
        })
        if len(self.reasoning_log) > 50:
            self.reasoning_log = self.reasoning_log[:50]

        return decision

    def _call_llm(self, prompt: str) -> Optional[str]:
        """Call the LLM API."""
        try:
            if self.provider == "ollama":
                return self._call_ollama(prompt)
            else:
                return self._call_lmstudio(prompt)
        except requests.Timeout:
            logger.warning(f"LLM timeout after {self.timeout}s")
            return None
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None

    def _call_ollama(self, prompt: str) -> str:
        url = f"{self.host}/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt}
            ],
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": 300,
            }
        }
        r = requests.post(url, json=payload, timeout=self.timeout)
        r.raise_for_status()
        return r.json()["message"]["content"]

    def _call_lmstudio(self, prompt: str) -> str:
        url = f"{self.host}/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt}
            ],
            "temperature": self.temperature,
            "max_tokens": 300,
        }
        r = requests.post(url, json=payload, timeout=self.timeout)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def _parse_response(self, raw: str, pair: str, price: float) -> TradeDecision:
        """Parse LLM JSON response into a TradeDecision."""
        try:
            # Strip markdown fences if present
            clean = re.sub(r'```(?:json)?', '', raw).strip()
            # Find first JSON object
            match = re.search(r'\{.*\}', clean, re.DOTALL)
            if not match:
                raise ValueError("No JSON found in response")

            data = json.loads(match.group())
            action     = data.get("action", "HOLD").upper()
            confidence = int(data.get("confidence", 0))
            reasoning  = data.get("reasoning", "No reasoning provided")
            sl_pct     = float(data.get("stop_loss_pct", self.stop_loss_pct))
            tp_pct     = float(data.get("take_profit_pct", self.take_profit_pct))
            size_pct   = float(data.get("size_pct", 50))

            # Enforce minimum confidence
            if confidence < self.min_confidence and action != "HOLD":
                logger.info(f"  Confidence {confidence}% < {self.min_confidence}% threshold → forcing HOLD")
                action = "HOLD"

            # Calculate stop loss and take profit prices
            if action == "BUY":
                stop_loss   = price * (1 - sl_pct / 100)
                take_profit = price * (1 + tp_pct / 100)
            elif action == "SELL":
                stop_loss   = price * (1 + sl_pct / 100)
                take_profit = price * (1 - tp_pct / 100)
            else:
                stop_loss   = price * (1 - sl_pct / 100)
                take_profit = price * (1 + tp_pct / 100)

            return TradeDecision(
                pair=pair,
                action=action,
                confidence=confidence,
                reasoning=reasoning,
                entry_price=price,
                stop_loss=round(stop_loss, 4),
                take_profit=round(take_profit, 4),
                size_pct=min(100, max(1, size_pct)),
                raw_response=raw
            )

        except Exception as e:
            logger.warning(f"LLM parse error: {e} | Raw: {raw[:200]}")
            return self._hold_decision(pair, price, f"Parse error: {e}")

    def _hold_decision(self, pair: str, price: float, reason: str) -> TradeDecision:
        return TradeDecision(
            pair=pair,
            action="HOLD",
            confidence=0,
            reasoning=reason,
            entry_price=price,
            stop_loss=price * 0.98,
            take_profit=price * 1.04,
            size_pct=0,
            raw_response=""
        )
