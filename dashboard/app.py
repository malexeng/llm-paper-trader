"""dashboard/app.py"""
import time
from flask import Flask, render_template, jsonify, request


def create_app(state: dict) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/status")
    def api_status():
        cfg = state.get("config", {})
        up  = int(time.time() - state.get("uptime_start", time.time()))
        h, r = divmod(up, 3600); m, s = divmod(r, 60)
        prices = state.get("prices", {})
        fmt_prices = {sym: {"price": f"{d['price']:,.4f}", "raw": d["price"]}
                      for sym, d in prices.items()}
        return jsonify({
            "uptime":     f"{h}h {m}m {s}s",
            "mode":       "PAPER" if cfg.get("paper_trading", True) else "LIVE",
            "running":    state.get("running", False),
            "paused":     state.get("paused", False),
            "llm_status": state.get("llm_status", "unknown"),
            "llm_model":  cfg.get("llm_model", "—"),
            "stats":      state.get("stats", {}),
            "prices":     fmt_prices,
        })

    @app.route("/api/reasoning")
    def api_reasoning():
        return jsonify(state.get("reasoning", []))

    @app.route("/api/positions")
    def api_positions():
        return jsonify(state.get("positions", []))

    @app.route("/api/history")
    def api_history():
        return jsonify(state.get("history", []))

    @app.route("/api/control", methods=["POST"])
    def api_control():
        action = request.json.get("action")
        state[f"{action}_signal"] = True
        return jsonify({"ok": True, "action": action})

    return app
