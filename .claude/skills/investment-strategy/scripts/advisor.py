#!/usr/bin/env python3
"""Thematic portfolio planner for an AI + space (SpaceX-exposure) tilt.

Educational tooling for a beginner U.S. investor. It turns a lump sum into a
risk-profiled allocation, a curated watchlist with a thesis for each holding, a
dollar-cost-averaging (DCA) entry schedule, and a monitoring checklist.

All money math uses decimal.Decimal so dollar amounts reconcile to the cent.
This is NOT financial, tax, or investment advice. SpaceX is a private company
and cannot be bought directly on a public exchange; the "space" sleeve uses
regulated funds and public proxies that hold or track it.

Usage:
    python advisor.py allocate <budget> [--risk balanced]
    python advisor.py watchlist [--theme all|ai|space|core|cash]
    python advisor.py plan <budget> [--risk balanced] [--tranches 4]
    python advisor.py monitor

Risk profiles: conservative | balanced | aggressive   (default: balanced)
"""

from __future__ import annotations

import sys
from decimal import Decimal, ROUND_HALF_UP, getcontext

getcontext().prec = 28

CENT = Decimal("0.01")


def _d(value) -> Decimal:
    return Decimal(str(value))


def money(value: Decimal) -> str:
    """Round half-up to the cent with thousands separators."""
    return f"{value.quantize(CENT, rounding=ROUND_HALF_UP):,.2f}"


def pct(value: Decimal) -> str:
    return f"{(value * Decimal(100)).quantize(Decimal('0.1'))}%"


# --- Sleeve weights by risk profile (fraction of the whole lump sum) ----------
# core = broad-market base, ai = AI/compute tilt, space = SpaceX-exposure tilt,
# cash = dry powder (T-bills) kept for volatility and future entries.
PROFILES = {
    "conservative": {"core": "0.50", "ai": "0.20", "space": "0.05", "cash": "0.25"},
    "balanced":     {"core": "0.40", "ai": "0.30", "space": "0.10", "cash": "0.20"},
    "aggressive":   {"core": "0.25", "ai": "0.45", "space": "0.20", "cash": "0.10"},
}

# --- Within-sleeve splits (fractions of the sleeve) ---------------------------
SLEEVES = {
    "core": [("VTI", "0.60"), ("VXUS", "0.20"), ("SCHD", "0.20")],
    "ai":   [("SMH", "0.35"), ("QQQM", "0.20"), ("NVDA", "0.15"),
             ("MSFT", "0.12"), ("GOOGL", "0.10"), ("AVGO", "0.08")],
    "space": [("ARKVX", "0.40"), ("XOVR", "0.30"), ("RKLB", "0.30")],
    "cash":  [("SGOV", "1.00")],
}

# --- Holding catalog: name, kind, thesis, what to watch -----------------------
HOLDINGS = {
    "VTI":   ("Vanguard Total U.S. Market ETF", "ETF",
              "The base of the portfolio: ~3,500 U.S. companies in one low-cost fund. "
              "Captures the market without betting on any single name.",
              "Broad market trend (S&P 500), expense ratio (~0.03%)."),
    "VXUS":  ("Vanguard Total International ETF", "ETF",
              "Diversification outside the U.S. so the whole book is not one country/theme.",
              "USD strength, global growth."),
    "SCHD":  ("Schwab U.S. Dividend Equity ETF", "ETF",
              "Quality dividend payers — ballast and income that behaves differently than AI names.",
              "Dividend yield, drawdown vs. the Nasdaq in selloffs."),
    "SMH":   ("VanEck Semiconductor ETF", "ETF",
              "Beginner-friendly way to own the AI compute supply chain (NVDA, TSM, AVGO) "
              "without picking one chipmaker. The picks-and-shovels of AI.",
              "Data-center capex from hyperscalers, chip lead times, SOX index."),
    "QQQM":  ("Invesco Nasdaq-100 ETF", "ETF",
              "Mega-cap tech / AI platform exposure (MSFT, GOOGL, META, AMZN) at a low fee.",
              "Nasdaq-100 valuation (forward P/E), megacap earnings."),
    "NVDA":  ("NVIDIA", "Stock",
              "The dominant AI training/inference chip. Highest reward and highest single-name risk.",
              "Data-center revenue, gross margin, guidance, export-control headlines."),
    "MSFT":  ("Microsoft", "Stock",
              "AI monetization via Azure + Copilot; an established cash machine, lower beta than NVDA.",
              "Azure growth rate, AI capex vs. free cash flow."),
    "GOOGL": ("Alphabet (Class A)", "Stock",
              "Gemini AI, cloud, and a cheap-vs-peers megacap with huge cash flow.",
              "Cloud growth, AI capex, ad revenue, antitrust headlines."),
    "AVGO":  ("Broadcom", "Stock",
              "Custom AI accelerators and networking — benefits as hyperscalers build their own chips.",
              "AI revenue mix, custom-silicon deal wins."),
    "ARKVX": ("ARK Venture Fund", "Interval fund",
              "Regulated fund open to non-accredited investors ($500 min) holding private innovators; "
              "SpaceX is a top holding. Closest 'real' SpaceX exposure.",
              "NAV updates, SpaceX % of fund, quarterly repurchase window (illiquid!)."),
    "XOVR":  ("ERShares Private-Public Crossover ETF", "ETF",
              "Exchange-traded, so it trades intraday; holds SpaceX alongside public growth names.",
              "SpaceX weight, premium/discount to NAV."),
    "RKLB":  ("Rocket Lab", "Stock",
              "Publicly traded launch + space-systems company — a liquid, pure-play space proxy "
              "(NOT SpaceX, but rides the same launch-economy thesis).",
              "Launch cadence, Neutron rocket milestones, backlog."),
    "SGOV":  ("iShares 0-3 Month Treasury ETF", "ETF",
              "Dry powder. Earns ~T-bill yield with almost no price risk while you wait to deploy.",
              "Short-term Treasury yield (the risk-free rate)."),
}

SLEEVE_LABELS = {
    "core": "Core / broad market (the foundation)",
    "ai": "AI & compute tilt",
    "space": "Space / SpaceX exposure tilt",
    "cash": "Cash / dry powder (T-bills)",
}


def resolve_profile(risk: str) -> dict:
    if risk not in PROFILES:
        raise SystemExit(f"Unknown risk profile '{risk}'. "
                         f"Choose: {', '.join(PROFILES)}")
    return PROFILES[risk]


def allocate(budget: Decimal, risk: str):
    """Return [(sleeve, sleeve_dollars, [(ticker, dollars), ...]), ...].

    The last line item in each sleeve absorbs rounding so sleeve totals and the
    grand total reconcile exactly to the cent.
    """
    weights = resolve_profile(risk)
    result = []
    spent_total = Decimal(0)
    sleeves = list(weights.items())
    for s_idx, (sleeve, w) in enumerate(sleeves):
        if s_idx == len(sleeves) - 1:
            sleeve_dollars = budget - spent_total  # absorb drift
        else:
            sleeve_dollars = (budget * _d(w)).quantize(CENT, rounding=ROUND_HALF_UP)
        spent_total += sleeve_dollars

        positions = SLEEVES[sleeve]
        rows = []
        spent_sleeve = Decimal(0)
        for p_idx, (ticker, pw) in enumerate(positions):
            if p_idx == len(positions) - 1:
                dollars = sleeve_dollars - spent_sleeve
            else:
                dollars = (sleeve_dollars * _d(pw)).quantize(CENT, rounding=ROUND_HALF_UP)
            spent_sleeve += dollars
            rows.append((ticker, dollars))
        result.append((sleeve, sleeve_dollars, rows))
    return result


def cmd_allocate(budget: Decimal, risk: str) -> None:
    plan = allocate(budget, risk)
    print(f"Allocation for ${money(budget)}  ·  risk profile: {risk}\n")
    for sleeve, sleeve_dollars, rows in plan:
        share = sleeve_dollars / budget if budget else Decimal(0)
        print(f"  {SLEEVE_LABELS[sleeve]}  —  ${money(sleeve_dollars)} ({pct(share)})")
        for ticker, dollars in rows:
            name = HOLDINGS[ticker][0]
            print(f"      {ticker:<6} ${money(dollars):>12}   {name}")
        print()
    total = sum((d for _, d, _ in plan), Decimal(0))
    print(f"  Total: ${money(total)}")


def cmd_watchlist(theme: str) -> None:
    themes = {
        "core": ["VTI", "VXUS", "SCHD"],
        "ai": ["SMH", "QQQM", "NVDA", "MSFT", "GOOGL", "AVGO"],
        "space": ["ARKVX", "XOVR", "RKLB"],
        "cash": ["SGOV"],
    }
    if theme == "all":
        order = themes["core"] + themes["ai"] + themes["space"] + themes["cash"]
    elif theme in themes:
        order = themes[theme]
    else:
        raise SystemExit(f"Unknown theme '{theme}'. "
                         f"Choose: all, {', '.join(themes)}")
    print(f"Watchlist — theme: {theme}\n")
    for ticker in order:
        name, kind, thesis, watch = HOLDINGS[ticker]
        print(f"  {ticker}  ({kind}) — {name}")
        print(f"     thesis : {thesis}")
        print(f"     watch  : {watch}\n")


def cmd_plan(budget: Decimal, risk: str, tranches: int) -> None:
    print("=" * 70)
    print(f"  INVESTMENT PLAN  ·  ${money(budget)}  ·  {risk} profile")
    print("=" * 70)
    print()
    cmd_allocate(budget, risk)

    # DCA the risk-on sleeves (core/ai/space); cash deploys as you buy dips.
    plan = allocate(budget, risk)
    risk_on = sum((d for s, d, _ in plan if s != "cash"), Decimal(0))
    per = (risk_on / Decimal(tranches)).quantize(CENT, rounding=ROUND_HALF_UP)
    print()
    print(f"  ENTRY: dollar-cost average, don't buy it all in one day")
    print(f"  Valuations on AI names are elevated — spreading entries lowers the")
    print(f"  risk of buying a single bad day. Deploy the risk-on sleeves")
    print(f"  (${money(risk_on)}) across {tranches} tranches, ~2-4 weeks apart:")
    deployed = Decimal(0)
    for i in range(1, tranches + 1):
        amt = (risk_on - deployed) if i == tranches else per
        deployed += amt
        print(f"      Tranche {i}: ~${money(amt)}")
    cash = next(d for s, d, _ in plan if s == "cash")
    print(f"  Keep ${money(cash)} in SGOV as dry powder for >10% market dips.")
    print()
    monitor_section()
    print()
    print("  REMINDER: educational only — not financial advice. SpaceX is private;")
    print("  exposure is via funds/proxies. Never invest money you may need soon.")


def monitor_section() -> None:
    print("  HOW TO MONITOR (a simple weekly + event-driven routine):")
    checks = [
        "Set price alerts at -15% and -25% from your cost basis per position.",
        "Position-size rule: no single stock above ~10% of the portfolio; trim if it grows past that.",
        "AI thesis health: hyperscaler data-center capex (MSFT/GOOGL/AMZN/META "
        "earnings calls) and NVDA data-center revenue + guidance.",
        "Space thesis health: ARKVX NAV & SpaceX weight; Rocket Lab launch cadence "
        "and Neutron milestones.",
        "Liquidity check: remember ARKVX only lets you sell in quarterly windows — "
        "size it as a long-hold, not a trade.",
        "Macro: the 10-yr Treasury yield and Fed decisions — rising rates pressure "
        "high-growth/AI valuations.",
        "Rebalance on a schedule (e.g. quarterly), not on emotion; sell winners back "
        "to target weights, top up laggards.",
        "Write your sell rules BEFORE buying (thesis broken? target hit? better idea?) "
        "so you don't decide in a panic.",
    ]
    for c in checks:
        print(f"    - {c}")


def parse_opts(args: list[str]) -> tuple[list[str], dict]:
    positional, opts = [], {}
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("--"):
            key = a[2:]
            val = args[i + 1] if i + 1 < len(args) else ""
            opts[key] = val
            i += 2
        else:
            positional.append(a)
            i += 1
    return positional, opts


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    positional, opts = parse_opts(argv[2:])
    risk = opts.get("risk", "balanced")

    if cmd == "allocate":
        cmd_allocate(_d(positional[0]), risk)
    elif cmd == "watchlist":
        cmd_watchlist(opts.get("theme", "all"))
    elif cmd == "plan":
        cmd_plan(_d(positional[0]), risk, int(opts.get("tranches", "4")))
    elif cmd == "monitor":
        monitor_section()
    else:
        print(f"Unknown command: {cmd}\n")
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
