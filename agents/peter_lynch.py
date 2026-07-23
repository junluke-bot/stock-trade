"""Peter Lynch persona: growth at a reasonable price, PEG, earnings momentum, category."""
from __future__ import annotations

from typing import Any

from data_layer import StockData
from utils.metrics import safe_div, series_cagr

from .base import InvestorAgent, Signal, score_to_signal


def _classify_category(revenue_cagr: float | None, market_cap: float | None,
                        pays_dividend: bool, net_income: float | None,
                        earnings_cagr: float | None) -> str:
    if net_income is not None and net_income < 0 and revenue_cagr is not None and revenue_cagr > 0:
        return "turnaround"
    if revenue_cagr is not None and revenue_cagr > 0.20:
        return "fast grower"
    if market_cap is not None and market_cap > 100e9 and pays_dividend and (revenue_cagr or 0) < 0.10:
        return "stalwart"
    if earnings_cagr is not None and abs(earnings_cagr) > 0.25 and (revenue_cagr or 0) < 0.10:
        return "cyclical"
    return "slow grower"


class PeterLynchAgent(InvestorAgent):
    key = "peter_lynch"
    investor_name = "Peter Lynch"

    def compute_metrics(self, data: StockData) -> dict[str, Any]:
        revenue = data.annual_series("financials", "Total Revenue")
        revenue_cagr = series_cagr(revenue) if len(revenue) >= 2 else None

        net_income_series = data.annual_series("financials", "Net Income")
        earnings_cagr = series_cagr(net_income_series) if len(net_income_series) >= 2 else None
        latest_net_income = float(net_income_series.iloc[-1]) if not net_income_series.empty else None

        pe = data.info_get("trailingPE")
        peg = data.info_get("pegRatio")
        if peg is None and pe is not None and earnings_cagr is not None and earnings_cagr > 0:
            peg = safe_div(pe, earnings_cagr * 100)

        quarterly_earnings = data.annual_series("quarterly_financials", "Net Income")
        earnings_momentum = None
        if len(quarterly_earnings) >= 2:
            prev, latest = quarterly_earnings.iloc[-2], quarterly_earnings.iloc[-1]
            if prev:
                earnings_momentum = safe_div(latest - prev, abs(prev))

        category = _classify_category(
            revenue_cagr, data.market_cap, data.has_dividends, latest_net_income, earnings_cagr
        )

        return {
            "revenue_cagr": revenue_cagr,
            "earnings_cagr": earnings_cagr,
            "pe_ratio": pe,
            "peg_ratio": peg,
            "earnings_momentum_qoq": earnings_momentum,
            "category": category,
            "pays_dividend": data.has_dividends,
        }

    def evaluate(self, data: StockData, metrics: dict[str, Any]) -> tuple[Signal, int, str]:
        peg = metrics.get("peg_ratio")
        pe = metrics.get("pe_ratio")
        earnings_cagr = metrics.get("earnings_cagr")
        momentum = metrics.get("earnings_momentum_qoq")
        category = metrics.get("category", "unclassified")

        if peg is None and earnings_cagr is None:
            return (
                "neutral",
                15,
                f"I can't pin down earnings growth for {data.ticker} well enough to "
                "check the price against it, so I've got no story to tell here.",
            )

        score = 50.0
        notes = [f"I'd bucket this as a '{category}'"]

        if peg is not None:
            if 0 < peg < 1.0:
                score += 25
                notes.append(f"a PEG of {peg:.2f} — growth I'm not overpaying for")
            elif peg < 1.5:
                score += 10
            elif peg > 2.5:
                score -= 20
                notes.append(f"a PEG of {peg:.2f} means the price has run ahead of the growth")

        if earnings_cagr is not None:
            if earnings_cagr > 0.15:
                score += 10
                notes.append("real earnings growth behind the story")
            elif earnings_cagr < 0:
                score -= 10
                notes.append("earnings are shrinking, not growing")

        if momentum is not None:
            if momentum > 0.10:
                score += 8
                notes.append("recent quarters show accelerating earnings")
            elif momentum < -0.10:
                score -= 8
                notes.append("earnings momentum has turned down recently")

        if category == "fast grower" and (peg is None or peg > 2.0) and pe is not None and pe > 40:
            score -= 10
            notes.append("paying a fast-grower price without fast-grower-cheap valuation")

        signal, confidence = score_to_signal(score)

        if signal == "bullish":
            body = f"{', '.join(notes)}. That's growth at a reasonable price — my favorite combination."
        elif signal == "bearish":
            body = f"{', '.join(notes)}. The growth doesn't justify what you'd pay for it today."
        else:
            body = f"{', '.join(notes)}. Not a clear enough setup either way for me to load up."

        return signal, confidence, f"On {data.ticker}: {body}"
