---
name: financial-services
description: >-
  Perform common financial-services calculations and workflows — loan and
  mortgage amortization, time-value-of-money (PV/FV/NPV/IRR), investment
  returns (CAGR, ROI), retirement/savings projections, and currency/percentage
  formatting. Use when a request involves money math, interest, loans, payments,
  investments, or financial reporting, and when accuracy, rounding, and
  regulatory-safe handling of financial data matter.
---

# Financial Services

A toolkit of well-tested financial calculations plus guidance for handling
money correctly. Reach for this whenever a task involves interest, loans,
payments, investments, or financial projections.

## When to use this skill

Trigger on requests like:

- "What's the monthly payment on a $300k mortgage at 6.5% for 30 years?"
- "Calculate the NPV / IRR of these cash flows."
- "What's the future value if I invest $500/month for 20 years?"
- "Compute the CAGR / ROI of this investment."
- "Build an amortization schedule."
- "Format these amounts as USD."

## Core principles (read first)

1. **Never use binary floating point for money.** Use integer minor units
   (cents) or a decimal type. In Python use `decimal.Decimal`; in JS use a
   decimal library or integer cents. The helper script in `scripts/finance.py`
   uses `Decimal` throughout.
2. **Be explicit about rounding.** Default to round-half-up to the currency's
   minor unit (2 dp for USD/EUR/GBP, 0 dp for JPY). State the rounding rule
   used in any output.
3. **Be explicit about the rate period.** Convert annual nominal rates to the
   compounding period before using them. Distinguish nominal (APR) from
   effective (APY) rates.
4. **Show the formula and the inputs**, not just the number, so results are
   auditable.
5. **This is not financial, tax, or investment advice.** Produce calculations
   and clearly-labeled projections; do not recommend specific securities or
   make guarantees about returns.

## Quick reference — formulas

- **Loan payment (amortizing):**
  `P = principal * r / (1 - (1 + r)^-n)` where `r` = periodic rate,
  `n` = number of payments.
- **Future value of a single sum:** `FV = PV * (1 + r)^n`
- **Future value of an annuity (level payments):**
  `FV = PMT * ((1 + r)^n - 1) / r`
- **Present value of future cash flows (NPV):**
  `NPV = Σ CF_t / (1 + r)^t`
- **CAGR:** `(ending / beginning)^(1/years) - 1`
- **ROI:** `(gain - cost) / cost`
- **Effective annual rate (APY) from nominal APR with m periods:**
  `(1 + APR/m)^m - 1`

## Helper script

`scripts/finance.py` implements these correctly with `Decimal`. Run it directly:

```bash
# Monthly mortgage payment: principal, annual-rate-percent, years
python scripts/finance.py payment 300000 6.5 30

# Full amortization schedule (first/last rows + totals)
python scripts/finance.py amortize 300000 6.5 30

# Future value of recurring contributions: monthly, annual-rate-percent, years
python scripts/finance.py fv-annuity 500 7 20

# NPV of cash flows at a discount rate (first arg is the rate %)
python scripts/finance.py npv 8 -1000 300 400 500 600

# IRR of cash flows
python scripts/finance.py irr -1000 300 400 500 600

# CAGR: beginning, ending, years
python scripts/finance.py cagr 10000 16105 5
```

Prefer the script over re-deriving the math by hand — it handles rounding and
edge cases (zero-rate loans, sign conventions) consistently.

## Workflow

1. Identify the calculation type and gather all inputs (principal, rate, term,
   compounding frequency, cash-flow timing).
2. Confirm the rate's period and compounding; convert if needed.
3. Run `scripts/finance.py` (or apply the formula with a `Decimal` type).
4. Present: the result, the formula used, the inputs, the rounding rule, and any
   assumptions. Add the not-advice disclaimer when the output looks like
   guidance.

## Compliance & data-handling notes

- Treat account numbers, balances, SSNs/Tax IDs, and card numbers (PAN) as
  sensitive. Don't echo full values back unnecessarily; mask all but the last 4.
- Never log secrets or full PANs. PCI DSS prohibits storing CVV at all.
- When summarizing financial figures, preserve precision until the final
  presentation step, then round once.
