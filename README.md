# LLM Paper Trader

> 📘 New here? Start with **[READ_THIS_OVERVIEW.md](READ_THIS_OVERVIEW.md)** for a plain-English walkthrough.

A crypto trading agent where a local model makes the call and hard-coded risk rules keep it honest — paper trading by default.

## Workflow

![Workflow diagram](docs/workflow.png)

> **Diagram key:** blue = input · purple = AI model · grey = processing · amber = storage · red = safety / guard rail · green = output

<details><summary>Diagram source (renders on GitHub)</summary>

```mermaid
flowchart TD
  T([Every 30 seconds, per trading pair]):::input --> C[Fetch price candles]:::step
  C --> I[Calculate indicators · RSI · MACD · Bollinger Bands]:::step
  I --> L[[Local LLM decides<br/>BUY / SELL / HOLD + stop-loss + take-profit]]:::ai
  L --> P{Is the answer valid?}:::guard
  P -->|no| H[Default to HOLD]:::guard
  P -->|yes| R{{"Risk rules<br/>size cap · % risked per trade"}}:::guard
  R -->|approved| O[Place order · paper money by default]:::step
  O --> PM[(Open positions)]:::store
  PM -->|price hits stop-loss or take-profit| O
  L --> W([Dashboard · live AI reasoning + profit / loss]):::output
  PM --> W

  classDef input fill:#e8f1ff,stroke:#3b82f6,color:#0b2a5b,stroke-width:1.5px
  classDef ai fill:#f1e8ff,stroke:#8b5cf6,color:#2e1065,stroke-width:1.5px
  classDef step fill:#f4f4f5,stroke:#71717a,color:#18181b,stroke-width:1.2px
  classDef store fill:#fff6e0,stroke:#d97706,color:#5a3300,stroke-width:1.2px
  classDef output fill:#e7f8ee,stroke:#16a34a,color:#073b1c,stroke-width:1.5px
  classDef guard fill:#ffecec,stroke:#dc2626,color:#5c0a0a,stroke-width:1.2px
```
</details>

## What it does
- Watches each pair on a loop and computes RSI, MACD and Bollinger Bands itself.
- Hands the model a compact market picture and asks for a structured decision with entry, stop-loss and take-profit.
- Rejects malformed answers (falls back to HOLD) and applies position-size and risk caps the model can't override.
- Manages open positions and closes them automatically on stop-loss or take-profit.
- Paper trading with a simulated balance is the default; live mode needs exchange keys you add yourself.

## What this project demonstrates
- LLM as a decision-maker inside deterministic guardrails
- Async multi-pair orchestration
- Technical indicators implemented from scratch
- Exchange integration through a common trading library

## Quick start
1. Install Ollama and pull a model.
2. `bash install.sh` (Windows: `install.bat`)
3. `python main.py` — dashboard at `http://localhost:5050`. Pairs and risk settings live in `config.yaml`.

## Project layout
```
main.py                 ← orchestrator
config.yaml             ← pairs, risk, model (keys left blank)
core/llm_brain.py       ← prompt + decision parsing
core/indicators.py      ← RSI / MACD / Bollinger
core/position_manager.py← SL / TP / limits
core/exchange.py        ← exchange + paper mode
dashboard/              ← live view
```

## Notes
Experimental. Keep it in paper mode unless you understand the risks. Not financial advice.

## License
MIT — see [LICENSE](LICENSE).
