---
name: investment-strategy
description: >-
  Plan a thematic stock/ETF portfolio for a U.S. retail investor, with a tilt
  toward AI/compute and space (SpaceX-exposure) themes. Turns a lump sum into a
  risk-profiled allocation, a curated watchlist with a thesis per holding, a
  dollar-cost-averaging entry schedule, and a monitoring checklist. Use when a
  user asks how to allocate money across stocks/ETFs, how much to put where,
  when/what to buy, how to get SpaceX or AI exposure, or how to track positions.
  Educational only — NOT financial, tax, or investment advice.
---

# investment-strategy

A money-safe (Decimal) portfolio planner for a beginner U.S. investor who wants
exposure to the AI and space themes without betting everything on one stock.

## When to use

A request involves: dividing a lump sum across stocks/ETFs, position sizing,
AI or SpaceX exposure, entry timing, or monitoring a portfolio.

## Hard rules (always apply)

1. **Not advice.** Always state that output is educational, not financial/tax/
   investment advice, and that the user should do their own research or consult
   a licensed advisor.
2. **SpaceX is private.** It cannot be bought directly on a public exchange.
   Exposure comes only through regulated funds (e.g. ARK Venture `ARKVX`,
   crossover ETF `XOVR`) or public proxies (e.g. Rocket Lab `RKLB`). Never imply
   a user can buy SpaceX shares directly.
3. **No price/return predictions.** Don't promise gains or call a market top/
   bottom. Frame entries as dollar-cost averaging and emphasize diversification,
   position limits, and pre-written sell rules.
4. **Risk first.** Confirm the money is long-term (not an emergency fund or cash
   needed within ~3-5 years) before recommending risk-on sleeves.

## Helper script

```bash
# Full plan: allocation + DCA schedule + monitoring checklist
python .claude/skills/investment-strategy/scripts/advisor.py plan 100000 --risk balanced

# Just the dollar allocation
python .claude/skills/investment-strategy/scripts/advisor.py allocate 100000 --risk aggressive

# Curated watchlist with a thesis + what-to-watch per holding
python .claude/skills/investment-strategy/scripts/advisor.py watchlist --theme ai

# Monitoring checklist
python .claude/skills/investment-strategy/scripts/advisor.py monitor
```

Risk profiles (fraction of lump sum): `core / ai / space / cash`
- `conservative` — 50 / 20 / 5 / 25
- `balanced` — 40 / 30 / 10 / 20  (default)
- `aggressive` — 25 / 45 / 20 / 10

The script reconciles every sleeve and the grand total exactly to the cent.

## For pairing with live prices / math

- Live quotes: use web search/fetch (this skill ships no market-data feed).
- Compound growth, savings projections, IRR/NPV: use the sibling
  `financial-services` skill (`scripts/finance.py`).
