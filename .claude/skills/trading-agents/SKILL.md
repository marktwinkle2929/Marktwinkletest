---
name: trading-agents
description: >-
  Install, configure, and run TauricResearch/TradingAgents — a multi-agent LLM
  financial-trading framework where analyst, researcher, trader, and
  risk-management agents collaborate (via LangGraph) to produce a trading
  decision for a ticker on a date. Use when a request involves setting up or
  running TradingAgents, multi-agent stock/crypto analysis, agent debate-based
  trade decisions, or wiring up the CLI / Python API and its API keys.
---

# TradingAgents

A multi-agent trading framework (https://github.com/TauricResearch/TradingAgents)
that mirrors a real trading firm: LLM-powered **analyst**, **researcher**,
**trader**, and **risk-management** agents collaborate — including structured
bull/bear debates — to evaluate a ticker and emit a BUY / HOLD / SELL decision.
Orchestrated with LangGraph.

## When to use this skill

Trigger on requests like:

- "Set up / install TradingAgents."
- "Run a multi-agent analysis on NVDA for 2026-01-15."
- "Use the TradingAgents Python API / CLI."
- "Configure TradingAgents to use Claude / Ollama / DeepSeek."
- "Change the number of debate rounds / which model the agents use."

## Important — read first

- **Not financial advice.** TradingAgents produces research-style, LLM-generated
  decisions for analysis and education. It is **not** investment advice and makes
  no guarantee of returns. Surface this in any output that looks like a
  recommendation.
- **It calls paid APIs.** Each run makes many LLM calls plus market-data calls,
  which cost money. Prefer a "quick-think" model and few debate rounds while
  testing. Keep all API keys in environment variables / `.env`, never in code or
  commits.
- **The framework is a separate Python project**, not Python packaged with this
  skill. Install it in its own environment as below.

## Install

Requires Python 3.12+ (conda recommended).

```bash
git clone https://github.com/TauricResearch/TradingAgents.git
cd TradingAgents
conda create -n tradingagents python=3.12 -y
conda activate tradingagents
pip install .
```

Docker alternative (from the cloned repo):

```bash
cp .env.example .env   # then fill in your keys
docker compose run --rm tradingagents
```

## API keys

Export the keys for whichever LLM provider you choose, plus a market-data key:

```bash
export ANTHROPIC_API_KEY=...      # Claude (recommended default provider)
export OPENAI_API_KEY=...         # OpenAI / GPT
export GOOGLE_API_KEY=...         # Gemini
export DEEPSEEK_API_KEY=...       # DeepSeek
export ALPHA_VANTAGE_API_KEY=...  # market data
```

Other supported providers: XAI (Grok), DashScope (Qwen), GLM, MiniMax,
OpenRouter, AWS Bedrock, and local models via **Ollama** (no key needed).

## Run — CLI

```bash
tradingagents          # interactive CLI (prompts for ticker, date, config)
python -m cli.main     # equivalent, run from the source tree
```

Tickers span multiple markets, e.g. `AAPL`, `NVDA`, `0700.HK`, `600519.SS`,
`BTC-USD`.

## Run — Python API

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "anthropic"
config["deep_think_llm"] = "claude-opus-4-8"
config["quick_think_llm"] = "claude-haiku-4-5-20251001"
config["max_debate_rounds"] = 1        # keep low while testing to save cost

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)
```

## Configuration (via `DEFAULT_CONFIG`)

- `llm_provider` — `openai` | `anthropic` | `google` | `deepseek` | `ollama` | …
- `deep_think_llm` / `quick_think_llm` — model ids for the slow/fast paths.
- `max_debate_rounds` — number of bull/bear research debate rounds (more =
  deeper but slower and more costly).
- `temperature` — lower for more reproducible runs.
- `checkpoint_enabled` — persist/recover run state.

See `tradingagents/default_config.py` in the cloned repo for the full list.

## Workflow

1. Clone and install into the `tradingagents` env (above).
2. Choose a provider and export its API key + `ALPHA_VANTAGE_API_KEY`.
3. Start with a cheap config: fast model, `max_debate_rounds=1`, one ticker.
4. Run via CLI or the Python API; read the per-agent logs to see the reasoning.
5. Present the decision **with** the not-financial-advice disclaimer and a note
   on which models / how many debate rounds produced it.
