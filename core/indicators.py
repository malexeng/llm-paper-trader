"""
core/indicators.py
Computes RSI, MACD, Bollinger Bands from raw OHLCV candle data.
No external TA library needed — pure Python/math for portability.
"""

import logging
import math
from typing import List, Dict, Optional

logger = logging.getLogger("indicators")


def sma(values: List[float], period: int) -> List[Optional[float]]:
    result = [None] * len(values)
    for i in range(period - 1, len(values)):
        result[i] = sum(values[i - period + 1:i + 1]) / period
    return result


def ema(values: List[float], period: int) -> List[Optional[float]]:
    result = [None] * len(values)
    k = 2 / (period + 1)
    for i in range(len(values)):
        if i < period - 1:
            continue
        if i == period - 1:
            result[i] = sum(values[:period]) / period
        else:
            result[i] = values[i] * k + result[i - 1] * (1 - k)
    return result


def rsi(closes: List[float], period: int = 14) -> List[Optional[float]]:
    result = [None] * len(closes)
    if len(closes) < period + 1:
        return result

    gains, losses = [], []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(0, delta))
        losses.append(max(0, -delta))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(closes)):
        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100 - (100 / (1 + rs))

        idx = i - period
        avg_gain = (avg_gain * (period - 1) + gains[idx]) / period
        avg_loss = (avg_loss * (period - 1) + losses[idx]) / period

    return result


def macd(closes: List[float], fast=12, slow=26, signal=9):
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)

    macd_line = []
    for f, s in zip(ema_fast, ema_slow):
        if f is None or s is None:
            macd_line.append(None)
        else:
            macd_line.append(f - s)

    valid = [v for v in macd_line if v is not None]
    if len(valid) < signal:
        return macd_line, [None] * len(macd_line), [None] * len(macd_line)

    # Signal line EMA
    signal_line = [None] * len(macd_line)
    k = 2 / (signal + 1)
    valid_start = next(i for i, v in enumerate(macd_line) if v is not None)
    sig_start = valid_start + signal - 1

    if sig_start < len(macd_line):
        signal_line[sig_start] = sum(
            macd_line[valid_start:valid_start + signal]
        ) / signal

        for i in range(sig_start + 1, len(macd_line)):
            if macd_line[i] is not None and signal_line[i - 1] is not None:
                signal_line[i] = macd_line[i] * k + signal_line[i - 1] * (1 - k)

    histogram = []
    for m, s in zip(macd_line, signal_line):
        if m is None or s is None:
            histogram.append(None)
        else:
            histogram.append(m - s)

    return macd_line, signal_line, histogram


def bollinger_bands(closes: List[float], period=20, std_dev=2.0):
    upper = [None] * len(closes)
    middle = [None] * len(closes)
    lower = [None] * len(closes)

    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1:i + 1]
        avg = sum(window) / period
        variance = sum((x - avg) ** 2 for x in window) / period
        std = math.sqrt(variance)
        middle[i] = avg
        upper[i]  = avg + std_dev * std
        lower[i]  = avg - std_dev * std

    return upper, middle, lower


def build_market_context(
    pair: str,
    candles: List[Dict],
    rsi_period: int = 14,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal_period: int = 9,
    bb_period: int = 20,
    bb_std: float = 2.0
) -> str:
    """
    Takes raw candles and returns a formatted string for the LLM to analyze.
    candles: list of {timestamp, open, high, low, close, volume}
    """
    if len(candles) < max(rsi_period, macd_slow, bb_period) + 5:
        return f"Insufficient candle data: only {len(candles)} candles available."

    closes  = [c["close"] for c in candles]
    highs   = [c["high"]  for c in candles]
    lows    = [c["low"]   for c in candles]
    volumes = [c["volume"] for c in candles]

    rsi_vals = rsi(closes, rsi_period)
    macd_line, sig_line, histogram = macd(closes, macd_fast, macd_slow, macd_signal_period)
    bb_upper, bb_mid, bb_lower = bollinger_bands(closes, bb_period, bb_std)

    # Get last N valid values
    def last_valid(lst, n=3):
        vals = [v for v in lst if v is not None]
        return vals[-n:] if len(vals) >= n else vals

    last_rsi  = last_valid(rsi_vals, 3)
    last_macd = last_valid(macd_line, 3)
    last_sig  = last_valid(sig_line, 3)
    last_hist = last_valid(histogram, 3)
    last_bbu  = last_valid(bb_upper, 1)
    last_bbm  = last_valid(bb_mid, 1)
    last_bbl  = last_valid(bb_lower, 1)

    current_price = closes[-1]
    price_change_5  = ((closes[-1] / closes[-5]) - 1) * 100 if len(closes) >= 5 else 0
    price_change_20 = ((closes[-1] / closes[-20]) - 1) * 100 if len(closes) >= 20 else 0
    avg_volume = sum(volumes[-20:]) / min(20, len(volumes))
    last_volume = volumes[-1]
    volume_ratio = last_volume / avg_volume if avg_volume > 0 else 1

    recent_high = max(highs[-20:])
    recent_low  = min(lows[-20:])

    # Trend summary
    rsi_now = last_rsi[-1] if last_rsi else None
    rsi_status = ""
    if rsi_now is not None:
        if rsi_now < 30:
            rsi_status = "OVERSOLD"
        elif rsi_now > 70:
            rsi_status = "OVERBOUGHT"
        elif rsi_now < 45:
            rsi_status = "bearish territory"
        elif rsi_now > 55:
            rsi_status = "bullish territory"
        else:
            rsi_status = "neutral"

    macd_cross = ""
    if len(last_macd) >= 2 and len(last_sig) >= 2:
        if last_macd[-1] > last_sig[-1] and last_macd[-2] <= last_sig[-2]:
            macd_cross = "⚡ BULLISH CROSSOVER just occurred"
        elif last_macd[-1] < last_sig[-1] and last_macd[-2] >= last_sig[-2]:
            macd_cross = "⚡ BEARISH CROSSOVER just occurred"
        elif last_macd[-1] > last_sig[-1]:
            macd_cross = "MACD above signal (bullish momentum)"
        else:
            macd_cross = "MACD below signal (bearish momentum)"

    bb_position = ""
    if last_bbu and last_bbl and last_bbm:
        bbu, bbm, bbl = last_bbu[0], last_bbm[0], last_bbl[0]
        bb_width = (bbu - bbl) / bbm * 100
        if current_price >= bbu:
            bb_position = f"Price AT/ABOVE upper band (potential reversal/breakout)"
        elif current_price <= bbl:
            bb_position = f"Price AT/BELOW lower band (potential reversal/bounce)"
        else:
            pct_in_band = (current_price - bbl) / (bbu - bbl) * 100
            bb_position = f"Price {pct_in_band:.0f}% through the band | Width: {bb_width:.2f}%"

    context = f"""=== MARKET DATA: {pair} ===

PRICE ACTION:
  Current:  ${current_price:,.4f}
  5-candle change:  {price_change_5:+.2f}%
  20-candle change: {price_change_20:+.2f}%
  20-candle high:   ${recent_high:,.4f}
  20-candle low:    ${recent_low:,.4f}

RSI ({rsi_period}):
  Current: {f"{rsi_now:.1f}" if rsi_now else "N/A"} — {rsi_status}
  Recent:  {[round(v,1) for v in last_rsi]}

MACD ({macd_fast}/{macd_slow}/{macd_signal_period}):
  {macd_cross}
  MACD line: {[round(v,6) for v in last_macd]}
  Signal:    {[round(v,6) for v in last_sig]}
  Histogram: {[round(v,6) for v in last_hist]}

BOLLINGER BANDS ({bb_period}):
  {bb_position}
  Upper: ${last_bbu[0]:,.4f if last_bbu else 'N/A'}
  Mid:   ${last_bbm[0]:,.4f if last_bbm else 'N/A'}
  Lower: ${last_bbl[0]:,.4f if last_bbl else 'N/A'}

VOLUME:
  Current vs 20-avg: {volume_ratio:.2f}x {"(HIGH VOLUME)" if volume_ratio > 1.5 else "(normal)"}

LAST 10 CLOSES:
  {[round(c, 4) for c in closes[-10:]]}
"""
    return context
