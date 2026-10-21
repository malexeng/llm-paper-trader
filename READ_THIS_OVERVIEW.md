# Read This — LLM Paper Trader Overview

*A plain-English guide so you can explain this project in an interview, a demo or a talk.*

## In one sentence
An AI trading agent where the AI makes the call but hard-coded safety rules have the final say. It trades with pretend money by default.

## The problem it solves
Letting an AI trade freely is reckless. AI models can be confidently wrong or give garbled answers. The interesting question is how you use AI judgement *safely* inside a system with real consequences.

## How it works, step by step
1. Every 30 seconds, for each trading pair, it pulls fresh price data.
2. Plain code calculates standard indicators (RSI, MACD, Bollinger Bands), the same signals human traders use.
3. The AI gets a compact market picture and must answer in a strict format: buy, sell or hold, plus stop-loss and take-profit levels.
4. Guard rail 1: if the answer is malformed or doesn't make sense, it defaults to HOLD.
5. Guard rail 2: risk rules cap position size and how much can be risked per trade. The AI can't override them.
6. Open positions are watched and closed automatically when they hit stop-loss or take-profit. A dashboard shows the AI's reasoning live.

See the diagram: [docs/workflow.png](docs/workflow.png)

## The everyday comparison
A talented but impulsive junior trader who has to get every trade signed off by a strict compliance officer, and who only trades with Monopoly money until they've earned trust.

## Why it works
The AI does what it's good at, which is weighing several signals together. Ordinary code does what it's good at: precise maths and rules that never bend. Neither one gets the whole job, so the weak points of each are covered.

## What makes it impressive
- "AI inside guard rails" is exactly how companies are deploying AI in high-stakes settings.
- Fails safe: if anything breaks, it holds instead of acting.
- Indicators are written from scratch, not borrowed from a black box.
- Paper mode makes it safe to demo and test.

## Your 30-second pitch
> "This is an AI trading agent built around one idea: the AI decides, but code enforces the rules. Indicators are calculated in code, the model returns a structured decision, and bad output defaults to hold. Risk limits the model can't override control position size. It's a working example of using AI judgement safely where mistakes cost money."

## Questions you'll likely get, and good answers
**Q: Does it make money?**  
A: That isn't the claim. It's a safe framework for testing AI decision-making, which is why paper trading is the default.

**Q: Why not let the AI do everything?**  
A: Models can hallucinate. Hard limits mean one bad answer can't do real damage.

**Q: How does this transfer to other jobs?**  
A: Any AI that approves, flags or routes things, like fraud checks or support triage, needs the same guard-rail design.

## Words to know
- **Paper trading**: simulated trading with fake money
- **Stop-loss / take-profit**: automatic exit prices for cutting losses or locking in gains
- **RSI / MACD / Bollinger**: common indicators for momentum, trend and volatility
- **Guard rail**: a fixed rule the AI can't break

## Honest limits (say these before someone else does)
Experimental and not financial advice. Local models are slow, so this suits slower timeframes, not split-second trading.
