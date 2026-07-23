"""Ben Graham persona: net-net working capital, P/E & P/B screens, Graham Number."""
from __future__ import annotations

from typing import Any

from data_layer import StockData
from utils.metrics import graham_number, safe_div

from .base import InvestorAgent, Signal, score_to_signal


class BenGrahamAgent(InvestorAgent):
    key = "ben_graham"
    investor_name = "Benjamin Graham"

    def compute_metrics(self, data: StockData) -> dict[str, Any]:
        current_assets = data.latest_value_any("balance_sheet", ["Current Assets", "Total Current Assets"])
        total_liabilities = data.latest_value_any(
            "balance_sheet", ["Total Liabilities Net Minority Interest", "Total Liab"]
        )
        current_liabilities = data.latest_value_any("balance_sheet", ["Current Liabilities", "Total Current Liabilities"])
        market_cap = data.market_cap

        ncav = None
        ncav_to_market_cap = None
        if current_assets is not None and total_liabilities is not None:
            ncav = current_assets - total_liabilities
            ncav_to_market_cap = safe_div(ncav, market_cap)

        current_ratio = safe_div(current_assets, current_liabilities)

        pe = data.info_get("trailingPE")
        pb = data.info_get("priceToBook")

        eps = data.info_get("trailingEps")
        book_value_per_share = data.info_get("bookValue")
        g_number = graham_number(eps, book_value_per_share)
        price = data.current_price
        graham_upside = safe_div(g_number - price, price) if (g_number and price) else None

        total_debt = data.latest_value_any("balance_sheet", ["Total Debt"])
        equity = data.latest_value_any(
            "balance_sheet", ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"]
        )
        debt_to_equity = safe_div(total_debt, equity)

        dividends_paid = data.has_dividends
        div_years = 0
        if not data.dividends.empty:
            div_years = len(set(data.dividends.index.year)) if hasattr(data.dividends.index, "year") else 0

        return {
            "ncav": ncav,
            "ncav_to_market_cap": ncav_to_market_cap,
            "current_ratio": current_ratio,
            "pe_ratio": pe,
            "pb_ratio": pb,
            "graham_number": g_number,
            "graham_upside": graham_upside,
            "debt_to_equity": debt_to_equity,
            "pays_dividend": dividends_paid,
            "dividend_years_on_record": div_years,
        }

    def evaluate(self, data: StockData, metrics: dict[str, Any]) -> tuple[Signal, int, str]:
        pe = metrics.get("pe_ratio")
        pb = metrics.get("pb_ratio")
        ncav_ratio = metrics.get("ncav_to_market_cap")
        current_ratio = metrics.get("current_ratio")
        graham_upside = metrics.get("graham_upside")
        d2e = metrics.get("debt_to_equity")
        pays_div = metrics.get("pays_dividend")

        if pe is None and pb is None and ncav_ratio is None:
            return (
                "neutral",
                15,
                f"None of my usual screens — earnings, book value, net current assets — "
                f"give me a usable number for {data.ticker}. I don't buy what I can't "
                "measure against a margin of safety.",
            )

        score = 45.0
        notes = []

        if ncav_ratio is not None and ncav_ratio > 1.0:
            score += 30
            notes.append("trading below its net current asset value, a classic net-net")
        elif ncav_ratio is not None and ncav_ratio > 0.66:
            score += 15
            notes.append("priced attractively versus net current assets")

        if pe is not None:
            if 0 < pe < 15:
                score += 15
                notes.append(f"an undemanding P/E of {pe:.1f}")
            elif pe > 25:
                score -= 15
                notes.append(f"a P/E of {pe:.1f} that leaves no margin of safety")

        if pb is not None:
            if 0 < pb < 1.5:
                score += 10
                notes.append(f"P/B of {pb:.1f}, close to or below book value")
            elif pb > 3:
                score -= 10

        if graham_upside is not None:
            if graham_upside > 0.3:
                score += 15
                notes.append(f"the Graham Number implies roughly {graham_upside:.0%} upside")
            elif graham_upside < -0.2:
                score -= 10

        if current_ratio is not None:
            if current_ratio > 2:
                score += 8
                notes.append("a strong current ratio protecting the downside")
            elif current_ratio < 1:
                score -= 15
                notes.append("a current ratio below 1 is a real balance sheet risk")

        if d2e is not None and d2e > 1.0:
            score -= 10
        if pays_div:
            score += 5
            notes.append("a dividend record adds a margin of safety")

        signal, confidence = score_to_signal(score)

        if signal == "bullish":
            body = f"This screens as a genuine value opportunity: {', '.join(notes[:3])}."
        elif signal == "bearish":
            body = "This does not offer an adequate margin of safety by any of my usual measures."
        else:
            body = "Some value characteristics are present, but not enough margin of safety to commit capital."

        return signal, confidence, f"On {data.ticker}: {body}"
