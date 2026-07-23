"""Cathie Wood persona: disruptive innovation, exponential growth, tolerates losses."""
from __future__ import annotations

from typing import Any

from data_layer import StockData
from utils.metrics import safe_div, series_cagr

from .base import InvestorAgent, Signal, score_to_signal


class CathieWoodAgent(InvestorAgent):
    key = "cathie_wood"
    investor_name = "Cathie Wood"

    def compute_metrics(self, data: StockData) -> dict[str, Any]:
        revenue = data.annual_series("financials", "Total Revenue")
        revenue_cagr = series_cagr(revenue) if len(revenue) >= 2 else None
        latest_revenue = float(revenue.iloc[-1]) if not revenue.empty else None

        rd = data.latest_value_any("financials", ["Research And Development"])
        rd_intensity = safe_div(rd, latest_revenue)

        gross_profit = data.annual_series("financials", "Gross Profit")
        gm_values = []
        for date in gross_profit.index:
            if date in revenue.index and revenue[date]:
                v = safe_div(gross_profit[date], revenue[date])
                if v is not None:
                    gm_values.append(v)
        gross_margin_trend = (gm_values[-1] - gm_values[0]) if len(gm_values) >= 2 else None

        net_income = data.latest_value("financials", "Net Income")
        market_cap = data.market_cap
        price_to_sales = safe_div(market_cap, latest_revenue)

        # naive 5-year forward price target: extrapolate revenue at a capped
        # growth rate, apply the current (or a normalized) P/S multiple.
        target_price = None
        implied_upside = None
        if latest_revenue is not None and revenue_cagr is not None and price_to_sales is not None:
            growth_for_projection = max(min(revenue_cagr, 0.60), 0.0)
            future_revenue = latest_revenue * ((1 + growth_for_projection) ** 5)
            projected_market_cap = future_revenue * price_to_sales
            shares = data.shares_outstanding
            if shares:
                target_price = projected_market_cap / shares
                if data.current_price:
                    implied_upside = safe_div(target_price - data.current_price, data.current_price)

        return {
            "revenue_cagr": revenue_cagr,
            "rd_intensity": rd_intensity,
            "gross_margin_trend": gross_margin_trend,
            "net_income": net_income,
            "price_to_sales": price_to_sales,
            "five_year_target_price": target_price,
            "implied_5y_upside": implied_upside,
            "current_price": data.current_price,
            "sector": data.sector,
        }

    def evaluate(self, data: StockData, metrics: dict[str, Any]) -> tuple[Signal, int, str]:
        rev_cagr = metrics.get("revenue_cagr")
        rd_intensity = metrics.get("rd_intensity")
        gm_trend = metrics.get("gross_margin_trend")
        net_income = metrics.get("net_income")
        upside = metrics.get("implied_5y_upside")

        if rev_cagr is None:
            return (
                "neutral",
                15,
                f"I need a real revenue growth trajectory to underwrite a disruptive "
                f"thesis on {data.ticker}, and the data doesn't give me one — no call.",
            )

        score = 45.0
        notes = []

        if rev_cagr > 0.30:
            score += 30
            notes.append(f"revenue compounding at roughly {rev_cagr:.0%} a year, the kind of exponential curve we look for")
        elif rev_cagr > 0.15:
            score += 15
            notes.append(f"solid {rev_cagr:.0%} revenue growth")
        elif rev_cagr < 0.05:
            score -= 20
            notes.append("growth that's too slow to be a disruption story")

        if rd_intensity is not None and rd_intensity > 0.10:
            score += 12
            notes.append("heavy R&D reinvestment into future platforms")
        elif rd_intensity is not None and rd_intensity < 0.02:
            score -= 5

        if gm_trend is not None:
            if gm_trend > 0:
                score += 10
                notes.append("improving gross margins as the model scales")
            else:
                score -= 5

        if net_income is not None and net_income < 0:
            if rev_cagr > 0.25:
                notes.append("losses today, but that's the price of capturing the market first")
            else:
                score -= 15
                notes.append("losses without the growth to justify them")

        if upside is not None:
            if upside > 0.5:
                score += 15
                notes.append(f"our five-year model implies roughly {upside:.0%} upside")
            elif upside < -0.2:
                score -= 15
                notes.append("today's price already looks ahead of our five-year model")

        signal, confidence = score_to_signal(score)

        if signal == "bullish":
            body = f"This is exactly the kind of disruptive growth story we build conviction around: {', '.join(notes[:2])}."
        elif signal == "bearish":
            body = f"The growth trajectory doesn't support a disruption thesis: {', '.join(notes[:2]) or 'growth is too slow and losses too large'}."
        else:
            body = "There's an innovation story here, but the growth curve isn't steep enough yet for high conviction."

        return signal, confidence, f"On {data.ticker}: {body}"
