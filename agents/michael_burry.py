"""Michael Burry persona: contrarian deep value, FCF yield, skeptical of crowded trades."""
from __future__ import annotations

from typing import Any

from data_layer import StockData
from utils.metrics import safe_div

from .base import InvestorAgent, Signal, score_to_signal


class MichaelBurryAgent(InvestorAgent):
    key = "michael_burry"
    investor_name = "Michael Burry"

    def compute_metrics(self, data: StockData) -> dict[str, Any]:
        fcf = data.latest_value_any("cashflow", ["Free Cash Flow"])
        op_cf = data.latest_value_any("cashflow", ["Operating Cash Flow"])
        capex = data.latest_value_any("cashflow", ["Capital Expenditure", "Capital Expenditures"])
        if fcf is None and op_cf is not None:
            fcf = op_cf - abs(capex or 0.0)

        market_cap = data.market_cap
        fcf_yield = safe_div(fcf, market_cap)

        pe = data.info_get("trailingPE", "forwardPE")
        short_pct_float = data.info_get("shortPercentOfFloat")
        short_ratio = data.info_get("shortRatio")

        insider_net_shares = None
        if not data.insider_transactions.empty:
            df = data.insider_transactions
            for col in ("Shares", "shares"):
                if col in df.columns:
                    text_col = None
                    for tcol in ("Transaction", "Text", "transactionText"):
                        if tcol in df.columns:
                            text_col = tcol
                            break
                    if text_col is not None:
                        buys = df[df[text_col].astype(str).str.contains("Buy|Purchase", case=False, na=False)][col].sum()
                        sells = df[df[text_col].astype(str).str.contains("Sale|Sell", case=False, na=False)][col].sum()
                        insider_net_shares = float(buys) - float(sells)
                    break

        institutional_ownership = data.info_get("heldPercentInstitutions")

        peg = data.info_get("pegRatio")

        return {
            "free_cash_flow": fcf,
            "fcf_yield": fcf_yield,
            "pe_ratio": pe,
            "short_percent_of_float": short_pct_float,
            "short_ratio": short_ratio,
            "insider_net_shares": insider_net_shares,
            "institutional_ownership": institutional_ownership,
            "peg_ratio": peg,
        }

    def evaluate(self, data: StockData, metrics: dict[str, Any]) -> tuple[Signal, int, str]:
        fcf_yield = metrics.get("fcf_yield")
        pe = metrics.get("pe_ratio")
        short_pct = metrics.get("short_percent_of_float")
        insider_net = metrics.get("insider_net_shares")
        institutional = metrics.get("institutional_ownership")

        if fcf_yield is None:
            return (
                "neutral",
                15,
                f"Without a real free cash flow number I can't tell what {data.ticker} is "
                "actually worth versus its price. I'm not going to make it up.",
            )

        score = 45.0
        notes = []

        if fcf_yield > 0.08:
            score += 25
            notes.append(f"a free cash flow yield near {fcf_yield:.0%} the market is ignoring")
        elif fcf_yield > 0.04:
            score += 10
        elif fcf_yield < 0:
            score -= 20
            notes.append("burning cash, which is exactly the kind of story that ends badly")

        if pe is not None and pe > 40:
            score -= 15
            notes.append(f"a P/E of {pe:.0f} priced for perfection — the crowd is all on one side of this trade")
        elif pe is not None and 0 < pe < 12:
            score += 10
            notes.append("a valuation the market has already given up on, which is where I like to look")

        if institutional is not None and institutional > 0.85:
            score -= 8
            notes.append("ownership this concentrated among institutions is itself a crowding risk")

        if short_pct is not None:
            if short_pct > 0.15:
                notes.append(f"short interest around {short_pct:.0%} of float — worth checking whether the crowd or the shorts are missing something")
            score -= 3 if short_pct < 0.02 else 0

        if insider_net is not None:
            if insider_net > 0:
                score += 10
                notes.append("insiders buying, which I take more seriously than any analyst note")
            elif insider_net < 0:
                score -= 5

        signal, confidence = score_to_signal(score)

        if signal == "bullish":
            body = f"The market looks wrong about this one: {', '.join(notes[:2])}."
        elif signal == "bearish":
            body = f"This looks like a crowded, overpriced trade: {', '.join(notes[:2]) or 'the valuation assumes everything goes right'}."
        else:
            body = "Nothing here that the market has obviously mispriced in either direction."

        return signal, confidence, f"On {data.ticker}: {body}"
