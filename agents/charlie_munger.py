"""Charlie Munger persona: quality over price, avoid stupidity, penalize complexity/hype."""
from __future__ import annotations

from typing import Any

from data_layer import StockData
from utils.metrics import safe_div, series_cagr

from .base import InvestorAgent, Signal, score_to_signal


class CharlieMungerAgent(InvestorAgent):
    key = "charlie_munger"
    investor_name = "Charlie Munger"

    def compute_metrics(self, data: StockData) -> dict[str, Any]:
        net_income = data.annual_series("financials", "Net Income")
        equity = data.annual_series_any(
            "balance_sheet", ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"]
        )
        roe_values = []
        for date in net_income.index:
            if date in equity.index and equity[date]:
                v = safe_div(net_income[date], equity[date])
                if v is not None:
                    roe_values.append(v)

        total_debt = data.latest_value_any("balance_sheet", ["Total Debt", "Net Debt"])
        latest_equity = float(equity.iloc[-1]) if not equity.empty else None
        debt_to_equity = safe_div(total_debt, latest_equity)

        op_income = data.annual_series("financials", "Operating Income")
        revenue = data.annual_series("financials", "Total Revenue")
        op_margins = []
        for date in op_income.index:
            if date in revenue.index and revenue[date]:
                v = safe_div(op_income[date], revenue[date])
                if v is not None:
                    op_margins.append(v)
        margin_volatility = (max(op_margins) - min(op_margins)) if len(op_margins) >= 3 else None

        shares_series = data.annual_series_any(
            "balance_sheet", ["Share Issued", "Ordinary Shares Number"]
        )
        dilution_rate = series_cagr(shares_series) if len(shares_series) >= 2 else None

        pe_ratio = data.info_get("trailingPE", "forwardPE")
        fcf = data.latest_value_any("cashflow", ["Free Cash Flow"])
        op_cf = data.latest_value_any("cashflow", ["Operating Cash Flow"])
        capex = data.latest_value_any("cashflow", ["Capital Expenditure", "Capital Expenditures"])
        if fcf is None and op_cf is not None:
            fcf = op_cf - abs(capex or 0.0)

        return {
            "roe_avg": sum(roe_values) / len(roe_values) if roe_values else None,
            "roe_min": min(roe_values) if roe_values else None,
            "debt_to_equity": debt_to_equity,
            "op_margin_avg": sum(op_margins) / len(op_margins) if op_margins else None,
            "margin_volatility": margin_volatility,
            "dilution_rate": dilution_rate,
            "pe_ratio": pe_ratio,
            "free_cash_flow": fcf,
            "sector": data.sector,
        }

    def evaluate(self, data: StockData, metrics: dict[str, Any]) -> tuple[Signal, int, str]:
        roe_avg = metrics.get("roe_avg")
        roe_min = metrics.get("roe_min")
        d2e = metrics.get("debt_to_equity")
        margin_vol = metrics.get("margin_volatility")
        dilution = metrics.get("dilution_rate")
        pe = metrics.get("pe_ratio")
        fcf = metrics.get("free_cash_flow")

        if roe_avg is None and fcf is None:
            return (
                "neutral",
                15,
                f"Not enough clean data on {data.ticker} to tell if this is a good "
                "business or a bad one at a fair price. Better to say nothing than "
                "to guess.",
            )

        score = 50.0
        notes = []
        red_flags = []

        if roe_min is not None and roe_min > 0.15:
            score += 20
            notes.append("consistently high returns on capital, not a one-good-year fluke")
        elif roe_avg is not None and roe_avg > 0.10:
            score += 5
        elif roe_avg is not None and roe_avg < 0.05:
            score -= 15
            red_flags.append("mediocre returns on capital")

        if d2e is not None and d2e > 1.5:
            score -= 20
            red_flags.append("leverage that could turn a bad year into a disaster")
        elif d2e is not None and d2e < 0.4:
            score += 8

        if margin_vol is not None:
            if margin_vol > 0.12:
                score -= 15
                red_flags.append("jumpy margins that suggest less pricing power or discipline than advertised")
            else:
                score += 8
                notes.append("stable operating margins")

        if dilution is not None and dilution > 0.03:
            score -= 12
            red_flags.append("meaningful share dilution eating into per-share value")

        if fcf is not None and fcf <= 0:
            score -= 15
            red_flags.append("burning cash rather than generating it")

        if pe is not None and pe > 45:
            score -= 10
            red_flags.append(f"a P/E near {pe:.0f} that prices in a lot of hope")
        elif pe is not None and 0 < pe < 20:
            score += 8
            notes.append("a price that doesn't require heroic assumptions")

        signal, confidence = score_to_signal(score)

        fallback_flag = "too many things I can't get comfortable with"
        if signal == "bullish":
            body = f"It's a good business — {', '.join(notes[:2]) or 'the fundamentals hold up'} — and it isn't priced like a lottery ticket."
        elif signal == "bearish":
            body = f"I'm avoiding this one: {', '.join(red_flags[:2]) or fallback_flag}. It's easier to avoid stupidity than to be brilliant."
        else:
            body = "It's not obviously stupid, but it's not obviously a great business at a fair price either — I'd rather do nothing."

        reasoning = f"On {data.ticker}: {body}"
        return signal, confidence, reasoning
