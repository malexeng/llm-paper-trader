"""
main.py — LLM Paper Trader orchestrator
Connects LLM brain, indicators, exchange, position manager.
"""

import asyncio
import logging
import os
import sys
import threading
import time
import yaml

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(LOG_DIR, "trader.log"), encoding="utf-8")
    ]
)
logger = logging.getLogger("main")


def load_config() -> dict:
    path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(path) as f:
        return yaml.safe_load(f)


def start_dashboard(state: dict, config: dict):
    from dashboard.app import create_app
    app = create_app(state)
    app.run(
        host=config.get("host", "0.0.0.0"),
        port=config.get("port", 5050),
        debug=False, use_reloader=False
    )


async def analysis_loop(pair: str, state: dict, config: dict):
    """Per-pair analysis loop: fetch candles → compute indicators → LLM decides → execute."""
    from core.indicators import build_market_context
    interval = config.get("analysis_interval_secs", 60)

    logger.info(f"Analysis loop started for {pair}")

    while state.get("running"):
        if state.get("paused"):
            await asyncio.sleep(2)
            continue

        try:
            exchange = state["exchange"]
            brain    = state["brain"]
            pm       = state["position_manager"]

            # Fetch latest candles
            candles = await exchange.get_candles(pair)
            if not candles:
                logger.warning(f"No candles for {pair}, retrying...")
                await asyncio.sleep(10)
                continue

            current_price = candles[-1]["close"]

            # Check existing positions for SL/TP
            exits = pm.check_exits(pair, current_price)
            for ex_pos in exits:
                # Execute the exit order
                exit_side = "sell" if ex_pos.side == "long" else "buy"
                await exchange.place_order(pair, exit_side, ex_pos.size_usdc, current_price)

            # Update price feed for dashboard
            state["prices"][pair] = {
                "price": current_price,
                "ts": int(time.time() * 1000)
            }

            # Build technical context
            context = build_market_context(
                pair, candles,
                rsi_period=config.get("rsi_period", 14),
                macd_fast=config.get("macd_fast", 12),
                macd_slow=config.get("macd_slow", 26),
                macd_signal_period=config.get("macd_signal", 9),
                bb_period=config.get("bb_period", 20),
                bb_std=config.get("bb_std", 2.0)
            )

            # Ask LLM
            logger.info(f"Asking LLM about {pair} @ ${current_price:,.4f}...")
            decision = brain.analyze(pair, context, current_price)
            logger.info(
                f"  {pair}: {decision.action} | conf={decision.confidence}% | "
                f"{decision.reasoning[:80]}..."
            )

            # Update reasoning log for dashboard
            state["reasoning"] = brain.reasoning_log

            # Execute if actionable
            if decision.action in ("BUY", "SELL"):
                can, reason = pm.can_open(pair)
                if can:
                    # Calculate position size
                    balance = await exchange.get_balance()
                    quote = pair.split("/")[1]
                    available = balance.get(quote, 0)
                    risk_pct = config.get("risk_per_trade_pct", 2.0) / 100
                    max_size = config.get("max_position_usdc", 100)
                    size_usdc = min(
                        available * risk_pct * (decision.size_pct / 100),
                        max_size
                    )
                    size_usdc = max(size_usdc, 5)  # minimum $5

                    amount_base = size_usdc / current_price
                    order_side  = "buy" if decision.action == "BUY" else "sell"

                    order = await exchange.place_order(pair, order_side, size_usdc, current_price)
                    if order:
                        pm.open_position(decision, size_usdc, amount_base)
                else:
                    logger.info(f"  Skipping trade — {reason}")

            # Update shared state for dashboard
            state["stats"]       = pm.get_stats()
            state["positions"]   = pm.get_open_list()
            state["history"]     = pm.get_history_list()
            state["llm_status"]  = "online" if brain.is_available() else "offline"

        except Exception as e:
            logger.error(f"Analysis loop error ({pair}): {e}")

        await asyncio.sleep(interval)


async def run_bot(config: dict, state: dict):
    from core.exchange import KrakenMarket
    from core.llm_brain import LLMBrain
    from core.position_manager import PositionManager

    exchange = KrakenMarket(config)
    await exchange.load()

    brain = LLMBrain(config)
    pm    = PositionManager(config)

    state["exchange"]          = exchange
    state["brain"]             = brain
    state["position_manager"]  = pm

    # Check LLM
    if brain.is_available():
        logger.info(f"LLM online: {config['llm_model']} via {config['llm_provider']} ✓")
    else:
        logger.warning(f"LLM not reachable at {config['llm_host']} — will retry per analysis cycle")

    pairs = config.get("pairs", ["BTC/USDT"])
    logger.info(f"Watching pairs: {', '.join(pairs)}")
    logger.info("Bot initialized. Click START on the dashboard.")

    while True:
        if state.get("start_signal"):
            state["start_signal"] = False
            if not state.get("running"):
                state["running"] = True
                state["paused"]  = False
                for pair in pairs:
                    asyncio.create_task(analysis_loop(pair, state, config))
                logger.info("Bot STARTED")

        if state.get("stop_signal"):
            state["stop_signal"] = False
            state["running"] = False
            logger.info("Bot STOPPED")

        if state.get("pause_signal"):
            state["pause_signal"] = False
            state["paused"] = True
            logger.info("Bot PAUSED")

        if state.get("resume_signal"):
            state["resume_signal"] = False
            state["paused"] = False
            pm.resume()
            logger.info("Bot RESUMED")

        state["stats"]     = pm.get_stats()
        state["positions"] = pm.get_open_list()
        state["history"]   = pm.get_history_list()

        await asyncio.sleep(1)


async def main():
    config = load_config()
    log_level = getattr(logging, config.get("log_level", "INFO"), logging.INFO)
    logging.getLogger().setLevel(log_level)

    logger.info("=" * 55)
    logger.info("  LLM PAPER TRADER — AI CRYPTO TRADING AGENT")
    logger.info(f"  Model : {config.get('llm_model')} ({config.get('llm_provider')})")
    logger.info(f"  Mode  : {'PAPER 📄' if config.get('paper_trading') else 'LIVE 🔴'}")
    logger.info(f"  URL   : http://localhost:{config.get('port', 5050)}")
    logger.info("=" * 55)

    state = {
        "running": False, "paused": False,
        "start_signal": False, "stop_signal": False,
        "pause_signal": False, "resume_signal": False,
        "prices": {}, "stats": {}, "positions": [],
        "history": [], "reasoning": [],
        "llm_status": "checking",
        "uptime_start": time.time(),
        "config": config,
    }

    t = threading.Thread(
        target=start_dashboard, args=(state, config), daemon=True
    )
    t.start()

    await run_bot(config, state)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Trader shutting down.")
