#!/usr/bin/env python3
"""Financial calculations using Decimal for money-safe arithmetic.

All monetary math uses decimal.Decimal to avoid binary floating-point error.
Results are rounded half-up to the cent only at presentation time.

Usage:
    python finance.py payment <principal> <annual_rate_pct> <years>
    python finance.py amortize <principal> <annual_rate_pct> <years>
    python finance.py fv-annuity <monthly_payment> <annual_rate_pct> <years>
    python finance.py fv <present_value> <annual_rate_pct> <years>
    python finance.py npv <discount_rate_pct> <cf0> <cf1> ...
    python finance.py irr <cf0> <cf1> ...
    python finance.py cagr <beginning> <ending> <years>
    python finance.py apy <nominal_apr_pct> <compounds_per_year>
"""

from __future__ import annotations

import sys
from decimal import Decimal, ROUND_HALF_UP, getcontext

getcontext().prec = 28

CENT = Decimal("0.01")


def _d(value: str | float | int) -> Decimal:
    return Decimal(str(value))


def money(value: Decimal) -> str:
    """Round half-up to the cent and format with thousands separators."""
    rounded = value.quantize(CENT, rounding=ROUND_HALF_UP)
    return f"{rounded:,.2f}"


def monthly_payment(principal: Decimal, annual_rate_pct: Decimal, years: Decimal) -> Decimal:
    """Level payment for a fully-amortizing loan, paid monthly."""
    n = int(years * 12)
    r = annual_rate_pct / Decimal(100) / Decimal(12)
    if r == 0:
        return principal / Decimal(n)
    factor = (Decimal(1) + r) ** n
    return principal * r * factor / (factor - Decimal(1))


def amortization(principal: Decimal, annual_rate_pct: Decimal, years: Decimal):
    """Yield (period, payment, interest, principal_paid, balance) rows."""
    n = int(years * 12)
    r = annual_rate_pct / Decimal(100) / Decimal(12)
    pmt = monthly_payment(principal, annual_rate_pct, years)
    balance = principal
    for period in range(1, n + 1):
        interest = (balance * r).quantize(CENT, rounding=ROUND_HALF_UP)
        principal_paid = pmt - interest
        balance = balance - principal_paid
        if period == n:
            # Absorb rounding drift in the final payment.
            principal_paid += balance
            balance = Decimal(0)
        yield period, pmt, interest, principal_paid, balance


def fv_single(present_value: Decimal, annual_rate_pct: Decimal, years: Decimal) -> Decimal:
    r = annual_rate_pct / Decimal(100)
    return present_value * (Decimal(1) + r) ** int(years)


def fv_annuity(monthly: Decimal, annual_rate_pct: Decimal, years: Decimal) -> Decimal:
    """Future value of level monthly contributions (ordinary annuity)."""
    n = int(years * 12)
    r = annual_rate_pct / Decimal(100) / Decimal(12)
    if r == 0:
        return monthly * Decimal(n)
    return monthly * (((Decimal(1) + r) ** n - Decimal(1)) / r)


def npv(rate_pct: Decimal, cash_flows: list[Decimal]) -> Decimal:
    r = rate_pct / Decimal(100)
    total = Decimal(0)
    for t, cf in enumerate(cash_flows):
        total += cf / (Decimal(1) + r) ** t
    return total


def irr(cash_flows: list[Decimal], guess: Decimal = Decimal("0.1")) -> Decimal:
    """Internal rate of return via Newton's method; returns a percentage."""
    rate = guess
    for _ in range(200):
        npv_val = Decimal(0)
        deriv = Decimal(0)
        for t, cf in enumerate(cash_flows):
            denom = (Decimal(1) + rate) ** t
            npv_val += cf / denom
            if t > 0:
                deriv -= Decimal(t) * cf / (Decimal(1) + rate) ** (t + 1)
        if deriv == 0:
            break
        new_rate = rate - npv_val / deriv
        if abs(new_rate - rate) < Decimal("0.0000001"):
            rate = new_rate
            break
        rate = new_rate
    return rate * Decimal(100)


def cagr(beginning: Decimal, ending: Decimal, years: Decimal) -> Decimal:
    """Compound annual growth rate as a percentage."""
    ratio = ending / beginning
    # Decimal has no fractional power; use float for the exponent only.
    result = Decimal(str(float(ratio) ** (1.0 / float(years)))) - Decimal(1)
    return result * Decimal(100)


def apy(nominal_apr_pct: Decimal, m: Decimal) -> Decimal:
    apr = nominal_apr_pct / Decimal(100)
    eff = (Decimal(1) + apr / m) ** int(m) - Decimal(1)
    return eff * Decimal(100)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1

    cmd = argv[1]
    args = argv[2:]

    if cmd == "payment":
        principal, rate, years = map(_d, args)
        pmt = monthly_payment(principal, rate, years)
        print(f"Monthly payment: ${money(pmt)}")
        print(f"  principal=${money(principal)} apr={rate}% term={years}y "
              f"({int(years * 12)} payments)")
        total = pmt * Decimal(int(years * 12))
        print(f"  total paid: ${money(total)}  total interest: "
              f"${money(total - principal)}")

    elif cmd == "amortize":
        principal, rate, years = map(_d, args)
        rows = list(amortization(principal, rate, years))
        print(f"Amortization: principal=${money(principal)} apr={rate}% "
              f"term={years}y")
        print(f"{'Pmt#':>5} {'Payment':>12} {'Interest':>12} "
              f"{'Principal':>12} {'Balance':>14}")
        total_interest = Decimal(0)
        for period, pmt, interest, principal_paid, balance in rows:
            total_interest += interest
            if period <= 3 or period > len(rows) - 3:
                print(f"{period:>5} {money(pmt):>12} {money(interest):>12} "
                      f"{money(principal_paid):>12} {money(balance):>14}")
            elif period == 4:
                print(f"{'...':>5}")
        print(f"Total interest over life of loan: ${money(total_interest)}")

    elif cmd == "fv-annuity":
        monthly, rate, years = map(_d, args)
        fv = fv_annuity(monthly, rate, years)
        contributed = monthly * Decimal(int(years * 12))
        print(f"Future value: ${money(fv)}")
        print(f"  contributed: ${money(contributed)}  growth: "
              f"${money(fv - contributed)}")

    elif cmd == "fv":
        pv, rate, years = map(_d, args)
        print(f"Future value: ${money(fv_single(pv, rate, years))}")

    elif cmd == "npv":
        rate = _d(args[0])
        flows = [_d(x) for x in args[1:]]
        print(f"NPV @ {rate}%: ${money(npv(rate, flows))}")

    elif cmd == "irr":
        flows = [_d(x) for x in args]
        result = irr(flows)
        print(f"IRR: {result.quantize(Decimal('0.0001'))}%")

    elif cmd == "cagr":
        beginning, ending, years = map(_d, args)
        print(f"CAGR: {cagr(beginning, ending, years).quantize(Decimal('0.0001'))}%")

    elif cmd == "apy":
        apr, m = map(_d, args)
        print(f"APY: {apy(apr, m).quantize(Decimal('0.0001'))}%")

    else:
        print(f"Unknown command: {cmd}\n")
        print(__doc__)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
