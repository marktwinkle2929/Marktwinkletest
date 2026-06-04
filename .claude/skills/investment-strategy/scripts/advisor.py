#!/usr/bin/env python3
"""Thematic portfolio planner for an AI + space (SpaceX-exposure) tilt.

Educational tooling for a beginner U.S. investor. It turns a lump sum into a
risk-profiled allocation, a curated watchlist with a thesis for each holding, a
dollar-cost-averaging (DCA) entry schedule, and a monitoring checklist.

All money math uses decimal.Decimal so dollar amounts reconcile to the cent.
This is NOT financial, tax, or investment advice. SpaceX is a private company
and cannot be bought directly on a public exchange; the "space" sleeve uses
regulated funds and public proxies that hold or track it.

Live prices: pass --live to allocate/plan, or use the `quote` command, to pull
real quotes from a public feed (Yahoo Finance, Stooq fallback) over the network.
Every price is stamped with its source and capture time. NOTE: a free public
feed is real-time for most U.S. equities/ETFs during market hours but can lag
~15 min on some venues, and funds like ARKVX price once a day (NAV). A *guaranteed*
real-time feed requires a paid/broker data subscription — see SKILL.md.

Usage:
    python advisor.py allocate <budget> [--risk balanced] [--live]
    python advisor.py watchlist [--theme all|ai|space|core|cash]
    python advisor.py plan <budget> [--risk balanced] [--tranches 4] [--live]
    python advisor.py quote <ticker> [<ticker> ...]
    python advisor.py crosscheck <ticker> [<ticker> ...]   # agree across 2 feeds?
    python advisor.py dashboard <budget> [--risk balanced] [--live] [--out file.html] [--range 1y]
    python advisor.py evaluate <ticker> [--budget 100000]  # should I add this?
    python advisor.py monitor

Risk profiles: conservative | balanced | aggressive   (default: balanced)
"""

from __future__ import annotations

import csv
import datetime
import io
import json
import sys
import urllib.request
from decimal import Decimal, ROUND_HALF_UP, getcontext

getcontext().prec = 28

CENT = Decimal("0.01")
USER_AGENT = "Mozilla/5.0 (compatible; investment-strategy/1.0)"
HTTP_TIMEOUT = 12


def _d(value) -> Decimal:
    return Decimal(str(value))


def money(value: Decimal) -> str:
    """Round half-up to the cent with thousands separators."""
    return f"{value.quantize(CENT, rounding=ROUND_HALF_UP):,.2f}"


def pct(value: Decimal) -> str:
    return f"{(value * Decimal(100)).quantize(Decimal('0.1'))}%"


# --- Live quotes --------------------------------------------------------------
# No third-party deps: stdlib urllib only. Two independent public sources so a
# single outage doesn't blank the whole table. Each quote carries its source and
# UTC capture time so the user can judge freshness — we never fake a price.

class Quote:
    __slots__ = ("ticker", "price", "currency", "asof", "source", "error")

    def __init__(self, ticker, price=None, currency=None, asof=None,
                 source=None, error=None):
        self.ticker = ticker
        self.price = price          # Decimal or None
        self.currency = currency
        self.asof = asof            # UTC datetime or None
        self.source = source
        self.error = error          # str or None


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return resp.read()


def _from_yahoo(ticker: str) -> Quote:
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
           f"?interval=1d&range=1d")
    meta = json.loads(_http_get(url))["chart"]["result"][0]["meta"]
    price = meta.get("regularMarketPrice")
    if price is None:
        raise ValueError("no regularMarketPrice in response")
    ts = meta.get("regularMarketTime")
    asof = datetime.datetime.utcfromtimestamp(ts) if ts else None
    return Quote(ticker, _d(price), meta.get("currency", "USD"), asof, "yahoo")


def _from_stooq(ticker: str) -> Quote:
    url = f"https://stooq.com/q/l/?s={ticker.lower()}.us&f=sd2t2ohlcv&h&e=csv"
    rows = list(csv.DictReader(io.StringIO(_http_get(url).decode())))
    if not rows or rows[0].get("Close") in (None, "", "N/D"):
        raise ValueError("no Close in Stooq response")
    row = rows[0]
    asof = None
    if row.get("Date") and row.get("Time") and row["Date"] != "N/D":
        try:
            asof = datetime.datetime.strptime(
                f"{row['Date']} {row['Time']}", "%Y-%m-%d %H:%M:%S")
        except ValueError:
            asof = None
    return Quote(ticker, _d(row["Close"]), "USD", asof, "stooq")


def fetch_quote(ticker: str) -> Quote:
    """Try Yahoo, then Stooq. Return a Quote with .error set if both fail."""
    last = None
    for source in (_from_yahoo, _from_stooq):
        try:
            return source(ticker)
        except Exception as exc:  # network/parse/HTTP — try the next source
            last = f"{type(exc).__name__}: {exc}"
    return Quote(ticker, error=last or "unavailable")


def fetch_quotes(tickers) -> dict:
    return {t: fetch_quote(t) for t in tickers}


def fetch_history(ticker: str, rng: str = "1y", interval: str = "1wk"):
    """Return [(date, close_float), ...] of historical closes, or [] on failure.

    Uses the same Yahoo chart endpoint as the live quote (no extra deps). Closes
    are plain floats — these drive chart PIXEL geometry only, never money math.
    """
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
           f"?interval={interval}&range={rng}")
    try:
        result = json.loads(_http_get(url))["chart"]["result"][0]
        stamps = result.get("timestamp") or []
        closes = result["indicators"]["quote"][0].get("close") or []
    except Exception:
        return []
    series = []
    for ts, c in zip(stamps, closes):
        if c is None:
            continue
        series.append((datetime.datetime.utcfromtimestamp(ts).date(), float(c)))
    return series


def fetch_histories(tickers, rng: str = "1y", interval: str = "1wk") -> dict:
    return {t: fetch_history(t, rng, interval) for t in tickers}


def fmt_asof(q: Quote) -> str:
    when = q.asof.strftime("%Y-%m-%d %H:%MZ") if q.asof else "time n/a"
    return f"{when} via {q.source}" if q.source else "n/a"


# --- Sleeve weights by risk profile (fraction of the whole lump sum) ----------
# core = broad-market base, ai = AI/compute tilt, space = SpaceX-exposure tilt,
# cash = dry powder (T-bills) kept for volatility and future entries.
PROFILES = {
    "conservative": {"core": "0.50", "ai": "0.20", "space": "0.05", "cash": "0.25"},
    "balanced":     {"core": "0.40", "ai": "0.30", "space": "0.10", "cash": "0.20"},
    "aggressive":   {"core": "0.25", "ai": "0.45", "space": "0.20", "cash": "0.10"},
    # Same sleeve weights as 'balanced', but the space sleeve is restructured for
    # a pending SpaceX IPO (see SLEEVE_OVERRIDES): trim the funds that already
    # hold SpaceX and earmark a small reserve to average in AFTER it lists.
    "balanced-ipo": {"core": "0.40", "ai": "0.30", "space": "0.10", "cash": "0.20"},
}

# --- Within-sleeve splits (fractions of the sleeve) ---------------------------
SLEEVES = {
    "core": [("VTI", "0.60"), ("VXUS", "0.20"), ("SCHD", "0.20")],
    "ai":   [("SMH", "0.35"), ("QQQM", "0.20"), ("NVDA", "0.15"),
             ("MSFT", "0.12"), ("GOOGL", "0.10"), ("AVGO", "0.08")],
    "space": [("ARKVX", "0.40"), ("XOVR", "0.30"), ("RKLB", "0.30")],
    "cash":  [("SGOV", "1.00")],
}

# Per-profile sleeve overrides. balanced-ipo trims ARKVX/XOVR (which already hold
# SpaceX pre-IPO, to avoid tripling up) and reserves 30% of the space sleeve as a
# capped SpaceX slice — parked in cash until the IPO lists, then averaged in.
SLEEVE_OVERRIDES = {
    "balanced-ipo": {
        "space": [("ARKVX", "0.25"), ("XOVR", "0.15"), ("RKLB", "0.30"),
                  ("SPACEX", "0.30")],
    },
}

# Pseudo-tickers that are not yet tradeable — never fetch a quote for these.
RESERVE_TICKERS = {"SPACEX"}

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
    "SPACEX": ("SpaceX IPO reserve (hold in SGOV until it lists)", "Reserve",
               "Capped speculative slice for the SpaceX IPO. Park it in SGOV now; "
               "do NOT buy day one — after it lists, average in over ~3 tranches, "
               "keeping total SpaceX exposure (this + ARKVX/XOVR) under ~5%.",
               "IPO listing date/price, first public quarterly report, price vs. "
               "the $135 IPO price, valuation (price/sales) vs. peers."),
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

        positions = SLEEVE_OVERRIDES.get(risk, {}).get(sleeve, SLEEVES[sleeve])
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


def cmd_allocate(budget: Decimal, risk: str, live: bool = False) -> None:
    plan = allocate(budget, risk)
    quotes = {}
    if live:
        tickers = [t for _, _, rows in plan for t, _ in rows
                   if t not in RESERVE_TICKERS]
        print("Fetching live quotes...", file=sys.stderr)
        quotes = fetch_quotes(tickers)
    print(f"Allocation for ${money(budget)}  ·  risk profile: {risk}"
          f"{'  ·  LIVE prices' if live else ''}\n")
    leftover_cash = Decimal(0)
    for sleeve, sleeve_dollars, rows in plan:
        share = sleeve_dollars / budget if budget else Decimal(0)
        print(f"  {SLEEVE_LABELS[sleeve]}  —  ${money(sleeve_dollars)} ({pct(share)})")
        for ticker, dollars in rows:
            name = HOLDINGS[ticker][0]
            if ticker in RESERVE_TICKERS:
                print(f"      {ticker:<6} ${money(dollars):>12}   {name}")
                if live:
                    print(f"             not tradeable yet — hold in SGOV until IPO")
                continue
            if not live:
                print(f"      {ticker:<6} ${money(dollars):>12}   {name}")
                continue
            q = quotes.get(ticker)
            if not q or q.error or not q.price:
                print(f"      {ticker:<6} ${money(dollars):>12}   {name}")
                print(f"             price unavailable ({q.error if q else 'n/a'})")
                continue
            shares = int(dollars / q.price)          # whole shares, floor
            spent = (q.price * shares).quantize(CENT, rounding=ROUND_HALF_UP)
            leftover_cash += dollars - spent
            print(f"      {ticker:<6} ${money(dollars):>12}   {name}")
            print(f"             @ ${money(q.price)}  ->  {shares} sh "
                  f"(${money(spent)})   [{fmt_asof(q)}]")
        print()
    total = sum((d for _, d, _ in plan), Decimal(0))
    print(f"  Total: ${money(total)}")
    if live:
        print(f"  Uninvested remainder from whole-share rounding: "
              f"${money(leftover_cash)}")
        print(f"  (Many brokers support fractional shares, which removes this "
              f"remainder.)")


def cmd_quote(tickers) -> None:
    if not tickers:
        raise SystemExit("usage: advisor.py quote <ticker> [<ticker> ...]")
    print("Fetching live quotes...\n", file=sys.stderr)
    quotes = fetch_quotes([t.upper() for t in tickers])
    print(f"{'Ticker':<8}{'Price':>12}  {'Cur':<4}{'As of (UTC)':<28}Name")
    for t in (t.upper() for t in tickers):
        q = quotes[t]
        name = HOLDINGS.get(t, (t,))[0]
        if q.error or not q.price:
            print(f"{t:<8}{'—':>12}  {'':<4}{'unavailable':<28}{q.error or ''}")
        else:
            print(f"{t:<8}${money(q.price):>11}  {q.currency:<4}"
                  f"{fmt_asof(q):<28}{name}")
    print("\nFree public feed: real-time for most U.S. listings in market hours;")
    print("some venues lag ~15 min and funds (e.g. ARKVX) price once daily (NAV).")


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


def cmd_crosscheck(tickers, tol_pct: Decimal = Decimal("1.0")) -> None:
    """Independently pull each ticker from BOTH feeds and flag disagreement.

    Two sources agreeing is a sanity check that a price isn't stale or garbled;
    a gap beyond `tol_pct` is a flag to verify before trading on the number.
    """
    if not tickers:
        raise SystemExit("usage: advisor.py crosscheck <ticker> [<ticker> ...]")
    print("Cross-checking each ticker across two independent feeds...\n",
          file=sys.stderr)
    print(f"{'Ticker':<8}{'Yahoo':>11}{'Stooq':>11}{'Diff':>9}  Verdict")
    for t in (t.upper() for t in tickers):
        try:
            y = _from_yahoo(t).price
        except Exception:
            y = None
        try:
            s = _from_stooq(t).price
        except Exception:
            s = None
        if y is None or s is None:
            have = "yahoo" if y else "stooq" if s else "neither"
            shown = money(y or s) if (y or s) else "—"
            print(f"{t:<8}{money(y) if y else '—':>11}{money(s) if s else '—':>11}"
                  f"{'':>9}  only {have} responded ({shown})")
            continue
        diff = abs(y - s) / ((y + s) / Decimal(2)) * Decimal(100)
        verdict = "OK" if diff <= tol_pct else f"CHECK (> {tol_pct}%)"
        print(f"{t:<8}{money(y):>11}{money(s):>11}{pct(diff/100):>9}  {verdict}")
    print(f"\nAgreement within {tol_pct}% => trust the number. A wide gap usually "
          f"means one\nfeed is stale (after-hours/NAV timing) — verify before acting.")


SLEEVE_COLORS = {
    "core": "#3b82f6", "ai": "#a855f7", "space": "#ef4444", "cash": "#10b981",
}

UP_COLOR, DOWN_COLOR = "#22c55e", "#ef4444"


def sparkline_svg(series, width: int = 240, height: int = 56) -> str:
    """Inline SVG line chart of a price history. Pure SVG — no JS/lib.

    Green if the period ended higher than it started, red otherwise. Returns an
    empty string when there is too little data to draw a meaningful line.
    """
    pts = [c for _, c in series]
    if len(pts) < 2:
        return ""
    lo, hi = min(pts), max(pts)
    span = (hi - lo) or 1.0
    pad = 4.0
    n = len(pts) - 1
    coords = []
    for i, c in enumerate(pts):
        x = pad + (width - 2 * pad) * (i / n)
        y = pad + (height - 2 * pad) * (1 - (c - lo) / span)
        coords.append(f"{x:.1f},{y:.1f}")
    color = UP_COLOR if pts[-1] >= pts[0] else DOWN_COLOR
    line = " ".join(coords)
    # Fill area under the line for a sparkline feel.
    area = f"{pad:.1f},{height - pad:.1f} {line} {width - pad:.1f},{height - pad:.1f}"
    fill_id = f"g{abs(hash(line)) % 100000}"
    return (
        f'<svg class="spark" viewBox="0 0 {width} {height}" '
        f'preserveAspectRatio="none" width="100%" height="{height}">'
        f'<defs><linearGradient id="{fill_id}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{color}" stop-opacity="0.28"/>'
        f'<stop offset="100%" stop-color="{color}" stop-opacity="0"/>'
        f'</linearGradient></defs>'
        f'<polygon points="{area}" fill="url(#{fill_id})" stroke="none"/>'
        f'<polyline points="{line}" fill="none" stroke="{color}" '
        f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
        f'</svg>')


def period_change(series):
    """Return (pct_change_float, first_close, last_close) or (None, None, None)."""
    pts = [c for _, c in series]
    if len(pts) < 2 or pts[0] == 0:
        return None, None, None
    return (pts[-1] - pts[0]) / pts[0] * 100.0, pts[0], pts[-1]

# --- Candidate screening knowledge --------------------------------------------
# Partial, illustrative ETF constituents so the screener can flag when a new
# name is ALREADY owned indirectly. Verify against the fund's official holdings
# page — these lists are not exhaustive and change over time.
CONSTITUENTS = {
    "SMH": {"NVDA", "AVGO", "TSM", "AMD", "MU", "INTC", "QCOM", "TXN", "LRCX",
            "AMAT", "ASML", "KLAC", "ADI", "MRVL", "MCHP", "NXPI", "ON", "TER"},
    "QQQM": {"MSFT", "GOOGL", "GOOG", "NVDA", "AVGO", "META", "AMZN", "AAPL",
             "TSLA", "AMD", "NFLX", "COST", "PLTR", "QCOM", "AMAT", "ADBE"},
}
# Funds in the default book that give broad/indirect exposure.
HELD_ETFS = ["SMH", "QQQM"]
# Rough theme tags for names a beginner is likely to read about.
CANDIDATE_THEME = {
    "AMD": "ai", "TSM": "ai", "PLTR": "ai", "MRVL": "ai", "MU": "ai",
    "SMCI": "ai", "DELL": "ai", "ARM": "ai", "TSLA": "ai/space-adjacent",
    "ASTS": "space", "LUNR": "space", "RDW": "space", "ASTR": "space",
    "PL": "space", "BKSY": "space", "VSAT": "space", "RKLB": "space",
}

ALL_HELD = {t for positions in SLEEVES.values() for t, _ in positions}


def _classify(ticker: str):
    """Return (theme, direct_holding?, [ETFs that already cover it])."""
    direct = ticker in ALL_HELD
    covered = [etf for etf in HELD_ETFS if ticker in CONSTITUENTS.get(etf, set())]
    theme = CANDIDATE_THEME.get(ticker) or ("known holding" if direct else "unknown")
    return theme, direct, covered


def cmd_evaluate(ticker: str, budget: Decimal, risk: str) -> None:
    ticker = ticker.upper()
    theme, direct, covered = _classify(ticker)
    print("=" * 66)
    print(f"  SCREEN: should {ticker} go into the strategy?")
    print("=" * 66)

    # 1) Data integrity — two independent feeds must agree.
    print("\n  [1] DATA INTEGRITY (cross-checked across two feeds)")
    try:
        y = _from_yahoo(ticker).price
    except Exception:
        y = None
    try:
        s = _from_stooq(ticker).price
    except Exception:
        s = None
    if y and s:
        diff = abs(y - s) / ((y + s) / Decimal(2)) * Decimal(100)
        flag = "agree" if diff <= Decimal("1.0") else "DISAGREE — verify"
        print(f"      Yahoo ${money(y)} | Stooq ${money(s)} | "
              f"diff {pct(diff/100)} -> {flag}")
    elif y or s:
        print(f"      Only one feed responded: ${money(y or s)} "
              f"(can't cross-check — treat as unconfirmed)")
    else:
        print(f"      No price from either feed — bad/unknown ticker? Stop and verify.")

    # 2) Fit & overlap with what you already own.
    print("\n  [2] FIT & OVERLAP")
    print(f"      Theme tag        : {theme}")
    if direct:
        print(f"      Already held     : YES — {ticker} is already a position. "
              f"Adding = increasing its weight, not diversifying.")
    elif covered:
        print(f"      Indirect exposure: YES — already owned inside {', '.join(covered)}. "
              f"Buying it directly is a CONCENTRATION bet on one name, not new exposure.")
    else:
        print(f"      Indirect exposure: not in the SMH/QQQM lists I track "
              f"(still likely a tiny sliver via VTI if it's a U.S. stock).")

    # 3) Position-sizing guardrail.
    print("\n  [3] SIZING GUARDRAIL (single-stock cap ~10%)")
    cap = (budget * Decimal("0.10")).quantize(CENT, rounding=ROUND_HALF_UP)
    starter = (budget * Decimal("0.03")).quantize(CENT, rounding=ROUND_HALF_UP)
    print(f"      On a ${money(budget)} book: hard cap ~${money(cap)}; "
          f"a beginner starter is ~${money(starter)} (3%).")
    print(f"      Fund it by trimming the matching sleeve (AI/space) or from cash —")
    print(f"      don't let total single-stock names blow past the sleeve target.")

    # 4) The judgment questions the data can't answer for you.
    print("\n  [4] BEFORE YOU ADD — answer these (this is where YOUR reading matters)")
    for q in [
        "What is the ONE-SENTENCE thesis, and what would prove it WRONG?",
        "Profitable / positive free cash flow, or a story stock? (speculative = smaller size)",
        "Is the good news already priced in? (forward P/E vs. its own history & peers)",
        "Does it add a NEW driver, or just double-down on AI/space you already own?",
        "Liquidity: can you exit easily? (avoid thin micro-caps and lock-up funds for big size)",
        "Source quality: primary source, or someone talking their own book?",
    ]:
        print(f"        - {q}")
    print("\n  Verdict is yours. Rule of thumb: if it only deepens existing AI/space")
    print("  exposure, prefer adding to your ETF (SMH/QQQM) over a single stock.")
    print("  Educational only — not financial advice; verify all figures yourself.")


def _esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def build_dashboard(budget: Decimal, risk: str, live: bool,
                    history_range: str = "1y") -> str:
    """Return a self-contained HTML string: a visual portfolio tracker.

    No external libraries or fonts — pure HTML/CSS/SVG so it opens offline in
    any browser. With --live, prices/values are real and stamped with capture
    time. Each tradeable holding also gets an inline SVG price-history chart and
    its period return, plus the "why buy" thesis and "what to watch".
    """
    plan = allocate(budget, risk)
    tradeable = [t for _, _, rows in plan for t, _ in rows
                 if t not in RESERVE_TICKERS]
    quotes = fetch_quotes(tradeable) if live else {}
    histories = fetch_histories(tradeable, rng=history_range, interval="1wk")
    gen = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    rng_label = {"6mo": "6-month", "1y": "1-year", "2y": "2-year",
                 "5y": "5-year"}.get(history_range, history_range)

    # Sleeve allocation bar (CSS widths — robust, no JS/SVG deps).
    bars, legend_parts = [], []
    for sleeve, dollars, _ in plan:
        w = (dollars / budget * Decimal(100)) if budget else Decimal(0)
        bars.append(
            f'<div class="seg" style="width:{w.quantize(Decimal("0.01"))}%;'
            f'background:{SLEEVE_COLORS[sleeve]}" '
            f'title="{SLEEVE_LABELS[sleeve]}: {pct(dollars/budget)}"></div>')
        legend_parts.append(
            f'<span class="lg"><i style="background:{SLEEVE_COLORS[sleeve]}"></i>'
            f'{_esc(SLEEVE_LABELS[sleeve])} — ${money(dollars)} '
            f'({pct(dollars/budget)})</span>')
    legend = "".join(legend_parts)

    # Per-sleeve sections of holding cards (chart + why + how-much).
    sections, total_value, leftover = [], Decimal(0), Decimal(0)
    for sleeve, sleeve_dollars, rows in plan:
        cards = []
        for ticker, dollars in rows:
            name, kind, thesis, watch = HOLDINGS[ticker]
            color = SLEEVE_COLORS[sleeve]

            # "How much" — price / shares / value.
            if ticker in RESERVE_TICKERS:
                price_c, sh_c, val_c, asof_c = "reserve", "—", "—", \
                    "not tradeable — hold in SGOV until IPO"
            elif live:
                q = quotes.get(ticker)
                if q and q.price and not q.error:
                    shares = int(dollars / q.price)
                    value = (q.price * shares).quantize(CENT, rounding=ROUND_HALF_UP)
                    leftover += dollars - value
                    total_value += value
                    price_c, sh_c, val_c = f"${money(q.price)}", str(shares), \
                        f"${money(value)}"
                    asof_c = _esc(fmt_asof(q))
                else:
                    err = _esc(q.error if q and q.error else "unavailable")
                    price_c, sh_c, val_c, asof_c = "—", "—", "—", err
            else:
                price_c = sh_c = val_c = "—"
                asof_c = "static plan (no --live)"

            # Chart + period return.
            series = histories.get(ticker, [])
            chart = sparkline_svg(series)
            chg, first_c, last_c = period_change(series)
            if chart:
                cls = "up" if chg is not None and chg >= 0 else "down"
                sign = "+" if chg is not None and chg >= 0 else ""
                chg_html = (f'<span class="chg {cls}">{sign}{chg:.1f}% '
                            f'· {rng_label}</span>') if chg is not None else ""
                chart_html = (f'<div class="chartwrap">{chart}'
                              f'<div class="chgline">{chg_html}</div></div>')
            elif ticker in RESERVE_TICKERS:
                chart_html = ('<div class="chartwrap nochart">No market history — '
                              'pre-IPO reserve</div>')
            else:
                chart_html = ('<div class="chartwrap nochart">Price history '
                              'unavailable</div>')

            cards.append(f"""
        <div class="hcard" style="border-left:3px solid {color}">
          <div class="hhead">
            <span class="tk">{ticker}</span>
            <span class="kind">{_esc(kind)}</span>
            <span class="nm">{_esc(name)}</span>
          </div>
          {chart_html}
          <div class="metrics">
            <div><span class="mk">Buy (target)</span><span class="mv">${money(dollars)}</span></div>
            <div><span class="mk">Latest price</span><span class="mv">{price_c}</span></div>
            <div><span class="mk">Shares</span><span class="mv">{sh_c}</span></div>
            <div><span class="mk">Value</span><span class="mv">{val_c}</span></div>
          </div>
          <div class="asof">{asof_c}</div>
          <div class="why"><b>Why:</b> {_esc(thesis)}</div>
          <div class="watch"><b>Watch:</b> {_esc(watch)}</div>
        </div>""")

        sections.append(f"""
      <div class="sleeve">
        <div class="sleeve-h"><span class="sdot" style="background:{SLEEVE_COLORS[sleeve]}"></span>
          {_esc(SLEEVE_LABELS[sleeve])} — <b>${money(sleeve_dollars)}</b>
          ({pct(sleeve_dollars/budget) if budget else '—'})</div>
        <div class="hgrid">{''.join(cards)}</div>
      </div>""")

    live_banner = (
        f'<div class="note">Live prices &amp; {rng_label} charts baked in at '
        f'generation time — regenerate to refresh. Uninvested whole-share '
        f'remainder: <b>${money(leftover)}</b> (brokers with fractional shares '
        f'remove this).</div>'
        if live else
        f'<div class="note">Charts show {rng_label} history, but this is a static '
        f'plan (no live prices). Re-run with <code>--live</code> for real quotes, '
        f'share counts, and market values.</div>')

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Portfolio Tracker — {risk}</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0;
    background: #0b1020; color: #e6e9f0; }}
  .wrap {{ max-width: 980px; margin: 0 auto; padding: 28px 20px 60px; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  .sub {{ color: #9aa3b8; font-size: 13px; margin-bottom: 22px; }}
  .bar {{ display: flex; height: 26px; border-radius: 7px; overflow: hidden;
    box-shadow: 0 1px 0 #ffffff14 inset; }}
  .seg {{ height: 100%; }}
  .legend {{ display: flex; flex-wrap: wrap; gap: 14px; margin: 14px 0 6px;
    font-size: 12.5px; color: #c7cde0; }}
  .lg i {{ display: inline-block; width: 10px; height: 10px; border-radius: 3px;
    margin-right: 6px; vertical-align: middle; }}
  .cards {{ display: flex; gap: 14px; flex-wrap: wrap; margin: 22px 0 6px; }}
  .card {{ flex: 1; min-width: 150px; background: #121a33; border: 1px solid #1d2540;
    border-radius: 11px; padding: 14px 16px; }}
  .card .k {{ color: #9aa3b8; font-size: 11.5px; text-transform: uppercase; }}
  .card .v {{ font-size: 21px; font-weight: 700; margin-top: 4px; }}
  .sleeve {{ margin-top: 30px; }}
  .sleeve-h {{ font-size: 14px; color: #d7dcec; margin-bottom: 12px; }}
  .sdot {{ display: inline-block; width: 9px; height: 9px; border-radius: 50%;
    margin-right: 8px; vertical-align: middle; }}
  .hgrid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
    gap: 14px; }}
  .hcard {{ background: #121a33; border: 1px solid #1d2540; border-radius: 11px;
    padding: 13px 15px; }}
  .hhead {{ display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }}
  .tk {{ font-size: 16px; font-weight: 700; }}
  .kind {{ font-size: 10px; text-transform: uppercase; letter-spacing: .04em;
    color: #9aa3b8; background: #1d2540; padding: 2px 6px; border-radius: 5px; }}
  .nm {{ font-size: 12px; color: #9aa3b8; }}
  .chartwrap {{ margin: 10px 0 4px; }}
  .nochart {{ color: #6b7390; font-size: 11.5px; padding: 16px 0; text-align: center; }}
  .spark {{ display: block; }}
  .chgline {{ text-align: right; margin-top: 2px; }}
  .chg {{ font-size: 12px; font-weight: 600; font-variant-numeric: tabular-nums; }}
  .chg.up {{ color: {UP_COLOR}; }}
  .chg.down {{ color: {DOWN_COLOR}; }}
  .metrics {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px 14px;
    margin: 8px 0 6px; }}
  .metrics .mk {{ color: #9aa3b8; font-size: 11px; display: block; }}
  .metrics .mv {{ font-size: 14px; font-weight: 600; font-variant-numeric: tabular-nums; }}
  .asof {{ color: #7e879e; font-size: 10.5px; margin-bottom: 8px; }}
  .why {{ font-size: 12px; color: #cdd3e6; line-height: 1.45; margin-bottom: 5px; }}
  .watch {{ font-size: 11.5px; color: #9aa3b8; line-height: 1.4; }}
  .why b, .watch b {{ color: #e6e9f0; }}
  .note {{ background: #121a33; border: 1px solid #1d2540; border-left: 3px solid #f59e0b;
    padding: 10px 14px; border-radius: 8px; font-size: 12.5px; color: #cdd3e6;
    margin-top: 22px; }}
  .disc {{ color: #6b7390; font-size: 11px; margin-top: 26px; line-height: 1.5; }}
  code {{ background: #1d2540; padding: 1px 5px; border-radius: 4px; }}
</style></head>
<body><div class="wrap">
  <h1>📈 Portfolio Tracker</h1>
  <div class="sub">Budget <b>${money(budget)}</b> · risk profile <b>{risk}</b>
    · {rng_label} charts · generated {gen}</div>

  <div class="cards">
    <div class="card"><div class="k">Target budget</div>
      <div class="v">${money(budget)}</div></div>
    <div class="card"><div class="k">Invested value</div>
      <div class="v">{'$'+money(total_value) if live else '—'}</div></div>
    <div class="card"><div class="k">Holdings</div>
      <div class="v">{sum(len(r) for _,_,r in plan)}</div></div>
  </div>

  <div class="bar">{''.join(bars)}</div>
  <div class="legend">{legend}</div>

  {''.join(sections)}

  {live_banner}
  <div class="disc">Educational only — not financial, tax, or investment advice.
    Past performance (the charts above) does not predict future returns.
    SpaceX is a private company; exposure here is via regulated funds/proxies,
    never direct shares. Free price feeds may lag ~15 min and funds price once
    daily (NAV); a guaranteed real-time feed needs a paid/broker subscription.
  </div>
</div></body></html>"""


def cmd_dashboard(budget: Decimal, risk: str, live: bool, out: str,
                  history_range: str = "1y") -> None:
    if live:
        print("Fetching live quotes for dashboard...", file=sys.stderr)
    print("Fetching price history for charts...", file=sys.stderr)
    html = build_dashboard(budget, risk, live, history_range)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"Wrote visual tracker -> {out}")
    print(f"Open it in a browser:  file://{out}")


def cmd_plan(budget: Decimal, risk: str, tranches: int, live: bool = False) -> None:
    print("=" * 70)
    print(f"  INVESTMENT PLAN  ·  ${money(budget)}  ·  {risk} profile")
    print("=" * 70)
    print()
    cmd_allocate(budget, risk, live=live)

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
    print("  REMINDER: educational only — not financial advice. Until its IPO lists,")
    print("  SpaceX exposure is via funds/proxies; once public, treat a fresh mega-IPO")
    print("  with the IPO discipline above. Never invest money you may need soon.")


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

    # Late-cycle / bubble-regime gauges. These are RISK THERMOMETERS, not timing
    # triggers — no one reliably calls the exact top. Use them to decide how much
    # dry powder to hold, not to pile in or fully bail.
    print("\n  BUBBLE / REGIME WARNING GAUGES (thermometers, not timing signals):")
    for c in [
        "Market concentration: top-10 weight & tech share of the S&P 500 — the "
        "higher it climbs, the more one wobble hurts the whole index.",
        "Sentiment crowding: BofA Bull & Bear Indicator > 8 is a contrarian "
        "'too-bullish' flag (cash low, managers all-in). A flag, not a sell button.",
        "Rates: 30-yr Treasury yield > 5% and core CPI drifting toward 4-5% — rising "
        "real rates compress high-growth/AI valuations the most.",
        "Breadth: if new highs come from only a handful of AI names ('narrow' market), "
        "the rally is fragile.",
    ]:
        print(f"    - {c}")

    print("\n  IPO / HYPE DISCIPLINE (e.g. a SpaceX or OpenAI mega-IPO):")
    for c in [
        "A fresh mega-IPO is the most hyped, least-seasoned price you can pay. Don't "
        "chase day one — let it trade a few quarters and report as a public company first.",
        "Sanity-check valuation: price / sales and profitability vs. peers. A "
        "trillion-dollar tag on a loss-making firm = priced for perfection.",
        "If you must participate, cap it as a SMALL speculative position (well under "
        "the 10% single-name limit) and average in — never reallocate the whole book into it.",
        "History: giant IPOs often mark sentiment peaks. Index-inclusion buying can "
        "spike a price short-term, then fade once the forced flows are done.",
    ]:
        print(f"    - {c}")


def parse_opts(args: list[str]) -> tuple[list[str], dict]:
    positional, opts = [], {}
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("--"):
            key = a[2:]
            nxt = args[i + 1] if i + 1 < len(args) else None
            if nxt is None or nxt.startswith("--"):
                opts[key] = "true"      # bare boolean flag (e.g. --live)
                i += 1
            else:
                opts[key] = nxt
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
    live = "live" in opts

    if cmd == "allocate":
        cmd_allocate(_d(positional[0]), risk, live=live)
    elif cmd == "watchlist":
        cmd_watchlist(opts.get("theme", "all"))
    elif cmd == "plan":
        cmd_plan(_d(positional[0]), risk, int(opts.get("tranches", "4")), live=live)
    elif cmd == "quote":
        cmd_quote(positional)
    elif cmd == "crosscheck":
        cmd_crosscheck(positional)
    elif cmd == "dashboard":
        cmd_dashboard(_d(positional[0]), risk, live,
                      opts.get("out", "portfolio_tracker.html"),
                      opts.get("range", "1y"))
    elif cmd == "evaluate":
        cmd_evaluate(positional[0], _d(opts.get("budget", "100000")), risk)
    elif cmd == "monitor":
        monitor_section()
    else:
        print(f"Unknown command: {cmd}\n")
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
