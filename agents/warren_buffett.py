"""Warren Buffett persona: durable moats, owner earnings, low debt, margin of safety."""
from __future__ import annotations

from typing import Any

import pandas as pd

from data_layer import StockData
from utils.metrics import cagr, discounted_cash_flow, safe_div, series_cagr

from .base import InvestorAgent, Signal, score_to_signal

DISCOUNT_RATE = 0.09
MAX_CONSERVATIVE_GROWTH = 0.07
DEFAULT_GROWTH_IF_UNKNOWN = 0.02


class WarrenBuffettAgent(InvestorAgent):
    key = "warren_buffett"
    investor_name = "Warren Buffett"

    def compute_metrics(self, data: StockData) -> dict[str, Any]:
        net_income = data.annual_series("financials", "Net Income")
        equity = data.annual_series_any(
            "balance_sheet", ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"]
        )
        roe_values = []
        for date in net_income.index:
            if date in equity.index and equity[date]:
                roe_values.append(safe_div(net_income[date], equity[date]))
        roe_values = [r for r in roe_values if r is not None]

        total_debt = data.latest_value_any("balance_sheet", ["Total Debt", "Net Debt"])
        latest_equity = float(equity.iloc[-1]) if not equity.empty else None
        debt_to_equity = safe_div(total_debt, latest_equity)

        gross_margin_series = data.annual_series("financials", "Gross Profit")
        revenue_series = data.annual_series("financials", "Total Revenue")
        margins = []
        for date in gross_margin_series.index:
            if date in revenue_series.index and revenue_series[date]:
                margins.append(safe_div(gross_margin_series[date], revenue_series[date]))
        margins = [m for m in margins if m is not None]

        op_cash_flow = data.latest_value_any("cashflow", ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"])
        capex = data.latest_value_any("cashflow", ["Capital Expenditure", "Capital Expenditures"])
        owner_earnings = None
        if op_cash_flow is not None:
            owner_earnings = op_cash_flow - abs(capex or 0.0)

        oe_series_raw = data.annual_series_any("cashflow", ["Operating Cash Flow"])
        capex_series = data.annual_series_any("cashflow", ["Capital Expenditure", "Capital Expenditures"])
        owner_earnings_series = []
        for date in oe_series_raw.index:
            capex_val = float(capex_series[date]) if date in capex_series.index else 0.0
            owner_earnings_series.append(oe_series_raw[date] - abs(capex_val))
        oe_growth = series_cagr(
            pd.Series(owner_earnings_series, index=oe_series_raw.index)
        ) if len(owner_earnings_series) >= 2 else None

        shares = data.shares_outstanding
        intrinsic_value_per_share = None
        margin_of_safety = None
        if owner_earnings is not None and owner_earnings > 0 and shares:
            growth_assumption = DEFAULT_GROWTH_IF_UNKNOWN
            if oe_growth is not None:
                growth_assumption = max(0.0, min(oe_growth, MAX_CONSERVATIVE_GROWTH))
            intrinsic_total = discounted_cash_flow(
                base_cash_flow=owner_earnings,
                growth_rate=growth_assumption,
                discount_rate=DISCOUNT_RATE,
            )
            if intrinsic_total is not None:
                intrinsic_value_per_share = intrinsic_total / shares
                if data.current_price:
                    margin_of_safety = safe_div(
                        intrinsic_value_per_share - data.current_price, intrinsic_value_per_share
                    )

        return {
            "roe_avg": sum(roe_values) / len(roe_values) if roe_values else None,
            "roe_values": roe_values,
            "roe_consistent": (len(roe_values) >= 3 and min(roe_values) > 0.10) if roe_values else None,
            "debt_to_equity": debt_to_equity,
            "gross_margin_avg": sum(margins) / len(margins) if margins else None,
            "gross_margin_stable": (max(margins) - min(margins) < 0.10) if len(margins) >= 3 else None,
            "owner_earnings": owner_earnings,
            "owner_earnings_growth": oe_growth,
            "intrinsic_value_per_share": intrinsic_value_per_share,
            "margin_of_safety": margin_of_safety,
            "current_price": data.current_price,
            "sector": data.sector,
            "industry": data.industry,
        }

    def evaluate(self, data: StockData, metrics: dict[str, Any]) -> tuple[Signal, int, str]:
        roe_avg = metrics.get("roe_avg")
        roe_consistent = metrics.get("roe_consistent")
        d2e = metrics.get("debt_to_equity")
        gm_stable = metrics.get("gross_margin_stable")
        mos = metrics.get("margin_of_safety")
        oe = metrics.get("owner_earnings")

        if oe is None or metrics.get("roe_avg") is None:
            return (
                "neutral",
                20,
                f"I can't get a clean read on {data.ticker}'s owner earnings or return on "
                "equity from what's available. I don't invest in what I can't understand "
                "on the numbers, so I'll pass rather than guess.",
            )

        score = 50.0
        notes = []

        if roe_consistent:
            score += 20
            notes.append("consistent double-digit returns on equity, the kind of moat I like")
        elif roe_avg is not None and roe_avg > 0.10:
            score += 8
            notes.append("decent but not fully proven returns on equity")
        else:
            score -= 15
            notes.append("returns on equity aren't consistently attractive")

        if d2e is not None:
            if d2e < 0.5:
                score += 12
                notes.append("a conservative balance sheet")
            elif d2e > 1.5:
                score -= 15
                notes.append("more debt than I'm comfortable with")

        if gm_stable:
            score += 8
            notes.append("stable margins suggesting real pricing power")
        elif gm_stable is False:
            score -= 8
            notes.append("margins bounce around more than I'd like")

        if oe <= 0:
            score -= 25
            notes.append("negative owner earnings is a real problem")

        if mos is not None:
            if mos > 0.25:
                score += 20
                notes.append(f"trading well below my estimate of intrinsic value (~{mos:.0%} margin of safety)")
            elif mos > 0:
                score += 5
                notes.append(f"a modest margin of safety (~{mos:.0%})")
            else:
                score -= 15
                notes.append(f"priced above my conservative intrinsic value estimate ({mos:.0%})")

        signal, confidence = score_to_signal(score)

        reasoning = (
            f"Looking at {data.ticker}, I see {', '.join(notes[:3])}. "
            + ("This is the kind of business I'd want to own for the long haul at the right price."
               if signal == "bullish"
               else "I'd rather wait for a better price or more clarity before committing capital."
               if signal == "neutral"
               else "This doesn't meet my bar for quality and price today.")
        )
        return signal, confidence, reasoning
