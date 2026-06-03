# Marktwinkletest

## Skills

This repository provides Claude Code [Agent Skills](https://code.claude.com/docs).

### financial-services

Money-safe financial calculations and workflows — loan/mortgage amortization,
time-value-of-money (PV/FV/NPV/IRR), investment returns (CAGR, ROI, APY), and
recurring-savings projections — all computed with `Decimal` to avoid
floating-point error.

- Skill definition: [`.claude/skills/financial-services/SKILL.md`](.claude/skills/financial-services/SKILL.md)
- Helper script: [`.claude/skills/financial-services/scripts/finance.py`](.claude/skills/financial-services/scripts/finance.py)

```bash
python .claude/skills/financial-services/scripts/finance.py payment 300000 6.5 30
```

Claude invokes the skill automatically when a task involves interest, loans,
payments, investments, or financial projections. The calculations are
informational and are **not** financial, tax, or investment advice.

### investment-strategy

Thematic portfolio planner for a U.S. retail investor with an AI/compute and
space (SpaceX-exposure) tilt. Turns a lump sum into a risk-profiled allocation,
a curated watchlist with a thesis per holding, a dollar-cost-averaging entry
schedule, and a monitoring checklist — all reconciled to the cent with
`Decimal`.

- Skill definition: [`.claude/skills/investment-strategy/SKILL.md`](.claude/skills/investment-strategy/SKILL.md)
- Helper script: [`.claude/skills/investment-strategy/scripts/advisor.py`](.claude/skills/investment-strategy/scripts/advisor.py)

```bash
python .claude/skills/investment-strategy/scripts/advisor.py plan 100000 --risk balanced
```

Output is **educational only — not financial, tax, or investment advice.**
Note: SpaceX is a private company; exposure comes only through regulated funds
or public proxies, never direct shares.
