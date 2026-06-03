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
2. **SpaceX / mega-IPO discipline.** Until a mega-IPO actually lists, exposure is
   only via regulated funds (`ARKVX`, `XOVR`) or proxies (`RKLB`) — never imply a
   user can buy private shares directly. Once such a name is public, treat a fresh,
   hyped mega-IPO with caution: don't chase day one, sanity-check valuation
   (price/sales, profitability), and cap any participation as a SMALL speculative
   position that averages in — never reallocate the whole book into it.
3. **No price/return predictions; filter hype.** Don't promise gains or call a
   market top/bottom. When a user brings influencer/news content, separate verified
   facts from speculation, cross-check key numbers, and ignore engagement-bait
   ("epic crash", "ultimate signal"). "Wait for the exact top signal" is market
   timing — frame instead as DCA, diversification, position limits, dry powder, and
   pre-written sell rules. Watch regime gauges (concentration, BofA Bull & Bear
   > 8, 30-yr yield > 5%, core CPI) as thermometers, not buy/sell buttons.
4. **Risk first.** Confirm the money is long-term (not an emergency fund or cash
   needed within ~3-5 years) before recommending risk-on sleeves.

## Helper script

```bash
# Full plan: allocation + DCA schedule + monitoring checklist
python .claude/skills/investment-strategy/scripts/advisor.py plan 100000 --risk balanced

# Live-price plan: same, but converts each dollar amount into whole shares at
# the current quote and stamps every price with its source + capture time
python .claude/skills/investment-strategy/scripts/advisor.py plan 100000 --live

# Just the dollar allocation (add --live for shares)
python .claude/skills/investment-strategy/scripts/advisor.py allocate 100000 --risk aggressive

# Live quotes for any tickers
python .claude/skills/investment-strategy/scripts/advisor.py quote NVDA GOOGL ARKVX

# Cross-check a price across TWO independent feeds and flag any divergence
python .claude/skills/investment-strategy/scripts/advisor.py crosscheck NVDA GOOGL

# Visual tracker: self-contained HTML dashboard (allocation bar + live table)
python .claude/skills/investment-strategy/scripts/advisor.py dashboard 100000 --live --out tracker.html
# then open tracker.html in any browser (no server, no dependencies)

# Screen a candidate the user read about: "should I add this?"
# Cross-checks the price, flags overlap with held ETFs, sizes it, and lists the
# judgment questions only the user's research can answer.
python .claude/skills/investment-strategy/scripts/advisor.py evaluate ASTS --budget 100000

# Curated watchlist with a thesis + what-to-watch per holding
python .claude/skills/investment-strategy/scripts/advisor.py watchlist --theme ai

# Monitoring checklist
python .claude/skills/investment-strategy/scripts/advisor.py monitor
```

## Live data: accuracy, freshness, and honesty rules

The `--live`, `quote`, and `crosscheck` commands hit public feeds (Yahoo
Finance primary, Stooq fallback) using only the Python stdlib — no API key.

- **Never fabricate a price.** If both feeds fail, the row prints `unavailable`
  with the error; it does not guess.
- **Always show freshness.** Every quote carries its source and UTC capture
  time so the user can judge staleness themselves.
- **Be honest about "real-time".** A free public feed is real-time for most
  U.S. equities/ETFs *during market hours*, but can lag ~15 min on some venues
  and outside hours; funds like `ARKVX` price once per day (NAV). A *guaranteed*
  real-time, exchange-authoritative feed requires a **paid/broker subscription**
  (e.g. a brokerage API, Polygon, or an exchange direct feed). Say this plainly;
  do not claim a guarantee the free feed cannot provide.
- **Cross-check before acting on a surprising number.** `crosscheck` pulls the
  same ticker from two independent sources; agreement within ~1% is a sanity
  check, a wide gap flags a stale/garbled feed to verify before trading.

Risk profiles (fraction of lump sum): `core / ai / space / cash`
- `conservative` — 50 / 20 / 5 / 25
- `balanced` — 40 / 30 / 10 / 20  (default)
- `aggressive` — 25 / 45 / 20 / 10
- `balanced-ipo` — same weights as `balanced`, but the space sleeve is restructured
  for a pending SpaceX IPO: ARKVX/XOVR are trimmed (they already hold SpaceX
  pre-IPO, so this avoids tripling up) and 30% of the sleeve becomes a capped
  `SPACEX` reserve — a non-tradeable placeholder held in SGOV until the IPO lists,
  then averaged in over ~3 tranches, keeping total SpaceX exposure under ~5%.

The script reconciles every sleeve and the grand total exactly to the cent.

## For pairing with live prices / math

- Live quotes: use web search/fetch (this skill ships no market-data feed).
- Compound growth, savings projections, IRR/NPV: use the sibling
  `financial-services` skill (`scripts/finance.py`).
