"""
core/position_manager.py
Tracks open positions, enforces stop-loss / take-profit, daily risk limits.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from core.llm_brain import TradeDecision

logger = logging.getLogger("position_manager")


@dataclass
class Position:
    position_id: str
    pair: str
    side: str                    # "long" or "short"
    entry_price: float
    size_usdc: float
    amount_base: float
    stop_loss: float
    take_profit: float
    confidence: int
    reasoning: str
    paper: bool = True
    status: str = "OPEN"         # OPEN, CLOSED_TP, CLOSED_SL, CLOSED_MANUAL
    exit_price: Optional[float] = None
    pnl_usdc: Optional[float] = None
    pnl_pct: Optional[float] = None
    opened_at: int = field(default_factory=lambda: int(time.time() * 1000))
    closed_at: Optional[int] = None


class PositionManager:

    def __init__(self, config: dict):
        self.config = config
        self.max_open    = config.get("max_open_positions", 3)
        self.max_daily_loss = config.get("max_daily_loss_usdc", 150)
        self.max_daily_trades = config.get("max_daily_trades", 20)
        self.max_consec_loss  = config.get("stop_on_consecutive_loss", 4)
        self.paper = config.get("paper_trading", True)

        self.positions: Dict[str, Position] = {}   # position_id -> Position
        self.history: List[Position] = []
        self._counter = 0
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.consecutive_losses = 0
        self.halted = False

    def can_open(self, pair: str) -> tuple[bool, str]:
        """Returns (True, '') or (False, reason)."""
        if self.halted:
            return False, "Bot halted by risk controls"
        open_count = sum(1 for p in self.positions.values() if p.status == "OPEN")
        if open_count >= self.max_open:
            return False, f"Max open positions ({self.max_open}) reached"
        if self.daily_pnl <= -self.max_daily_loss:
            self.halted = True
            return False, f"Daily loss limit ${self.max_daily_loss} hit"
        if self.daily_trades >= self.max_daily_trades:
            return False, f"Daily trade limit ({self.max_daily_trades}) reached"
        if self.consecutive_losses >= self.max_consec_loss:
            self.halted = True
            return False, f"{self.max_consec_loss} consecutive losses — halted"
        # Don't double-open same pair
        for p in self.positions.values():
            if p.pair == pair and p.status == "OPEN":
                return False, f"Already have open position on {pair}"
        return True, ""

    def open_position(
        self, decision: TradeDecision, size_usdc: float, amount_base: float
    ) -> Optional[Position]:
        self._counter += 1
        pid = f"P{self._counter:04d}"
        side = "long" if decision.action == "BUY" else "short"

        pos = Position(
            position_id=pid,
            pair=decision.pair,
            side=side,
            entry_price=decision.entry_price,
            size_usdc=size_usdc,
            amount_base=amount_base,
            stop_loss=decision.stop_loss,
            take_profit=decision.take_profit,
            confidence=decision.confidence,
            reasoning=decision.reasoning,
            paper=self.paper
        )
        self.positions[pid] = pos
        self.daily_trades += 1
        logger.info(
            f"Position OPENED [{pid}] {side.upper()} {decision.pair} @ "
            f"${decision.entry_price:,.4f} | SL: ${decision.stop_loss:,.4f} "
            f"TP: ${decision.take_profit:,.4f}"
        )
        return pos

    def check_exits(self, pair: str, current_price: float) -> List[Position]:
        """Check all open positions for stop-loss / take-profit triggers."""
        triggered = []
        for pos in list(self.positions.values()):
            if pos.pair != pair or pos.status != "OPEN":
                continue

            hit_sl = hit_tp = False
            if pos.side == "long":
                hit_sl = current_price <= pos.stop_loss
                hit_tp = current_price >= pos.take_profit
            else:
                hit_sl = current_price >= pos.stop_loss
                hit_tp = current_price <= pos.take_profit

            if hit_tp:
                self._close_position(pos, current_price, "CLOSED_TP")
                triggered.append(pos)
            elif hit_sl:
                self._close_position(pos, current_price, "CLOSED_SL")
                triggered.append(pos)

        return triggered

    def _close_position(self, pos: Position, exit_price: float, status: str):
        if pos.side == "long":
            pnl = (exit_price - pos.entry_price) * pos.amount_base
        else:
            pnl = (pos.entry_price - exit_price) * pos.amount_base

        pnl_pct = (pnl / pos.size_usdc) * 100

        pos.status     = status
        pos.exit_price = exit_price
        pos.pnl_usdc   = round(pnl, 4)
        pos.pnl_pct    = round(pnl_pct, 4)
        pos.closed_at  = int(time.time() * 1000)

        self.daily_pnl += pnl
        self.history.append(pos)
        del self.positions[pos.position_id]

        if pnl > 0:
            self.consecutive_losses = 0
            logger.info(f"✅ [{pos.position_id}] {status} +${pnl:.4f} ({pnl_pct:+.2f}%)")
        else:
            self.consecutive_losses += 1
            logger.warning(f"❌ [{pos.position_id}] {status} ${pnl:.4f} ({pnl_pct:+.2f}%)")

    def close_manual(self, position_id: str, price: float) -> bool:
        pos = self.positions.get(position_id)
        if not pos:
            return False
        self._close_position(pos, price, "CLOSED_MANUAL")
        return True

    def resume(self):
        self.halted = False
        self.consecutive_losses = 0
        logger.info("Position manager resumed")

    def get_stats(self) -> dict:
        all_closed = self.history
        wins  = [p for p in all_closed if p.pnl_usdc and p.pnl_usdc > 0]
        losses = [p for p in all_closed if p.pnl_usdc and p.pnl_usdc <= 0]
        total_pnl = sum(p.pnl_usdc for p in all_closed if p.pnl_usdc)
        return {
            "open_positions": len(self.positions),
            "total_closed": len(all_closed),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / max(len(all_closed), 1) * 100, 1),
            "total_pnl": round(total_pnl, 4),
            "daily_pnl": round(self.daily_pnl, 4),
            "daily_trades": self.daily_trades,
            "consecutive_losses": self.consecutive_losses,
            "halted": self.halted,
        }

    def get_open_list(self) -> list:
        return [
            {
                "id": p.position_id,
                "pair": p.pair,
                "side": p.side,
                "entry": p.entry_price,
                "sl": p.stop_loss,
                "tp": p.take_profit,
                "size": p.size_usdc,
                "confidence": p.confidence,
                "reasoning": p.reasoning[:100],
                "paper": p.paper,
            }
            for p in self.positions.values() if p.status == "OPEN"
        ]

    def get_history_list(self, n=30) -> list:
        return [
            {
                "id": p.position_id,
                "pair": p.pair,
                "side": p.side,
                "entry": p.entry_price,
                "exit": p.exit_price,
                "pnl": p.pnl_usdc,
                "pnl_pct": p.pnl_pct,
                "status": p.status,
                "confidence": p.confidence,
            }
            for p in reversed(self.history[-n:])
        ]
