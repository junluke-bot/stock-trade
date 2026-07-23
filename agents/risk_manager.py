"""Risk manager persona: volatility, drawdown, position sizing, concentration/correlation."""
from __future__ import annotations

from typing import Any

import pandas as pd

from data_layer import StockData
from utils.metrics import annualized_volatility, max_drawdown

from .base import InvestorAgent, Signal, score_to_signal

HIGH_VOL_THRESHOLD = 0.45
HIGH_CORRELATION_THRESHOLD = 0.75


class RiskManagerAgent(InvestorAgent):
    key = "risk_manager"
    investor_name = "The Risk Manager"

    def __init__(self) -> None:
        # Populated by the CLI before analyzing a batch, so this agent can
        # flag correlation/concentration risk across the tickers requested
        # together, not just the one it's currently scoring.
        self.peer_returns: dict[str, pd.Series] = {}

    def compute_metrics(self, data: StockData) -> dict[str, Any]:
        close = data.history["Close"] if "Close" in data.history else None
        if close is None or close.empty:
            return {}

        beta = data.info_get("beta")
        vol = annualized_volatility(close)
        drawdown = max_drawdown(close.tail(252)) if len(close) >= 20 else max_drawdown(close)

        correlated_with = []
        my_returns = close.pct_change().dropna()
        for peer_ticker, peer_returns in self.peer_returns.items():
            if peer_ticker == data.ticker or peer_returns.empty:
                continue
            aligned = pd.concat([my_returns, peer_returns], axis=1, join="inner")
            if len(aligned) < 20:
                continue
            corr = aligned.iloc[:, 0].corr(aligned.iloc[:, 1])
            if corr is not None and corr > HIGH_CORRELATION_THRESHOLD:
                correlated_with.append((peer_ticker, float(corr)))

        # simple inverse-volatility position sizing suggestion, as a % of a
        # notional single-name risk budget
        suggested_position_pct = None
        if vol is not None and vol > 0:
            suggested_position_pct = max(1.0, min(20.0, 10.0 / (vol / 0.20)))

        return {
            "beta": beta,
            "annualized_volatility": vol,
            "max_drawdown_1y": drawdown,
            "correlated_peers": correlated_with,
            "suggested_position_pct": suggested_position_pct,
        }

    def evaluate(self, data: StockData, metrics: dict[str, Any]) -> tuple[Signal, int, str]:
        if not metrics:
            return (
                "neutral",
                10,
                f"No price history to assess risk on {data.ticker} — treat any "
                "position here as unsized and unmonitored until data is available.",
            )

        beta = metrics.get("beta")
        vol = metrics.get("annualized_volatility")
        drawdown = metrics.get("max_drawdown_1y")
        correlated = metrics.get("correlated_peers") or []
        suggested_pct = metrics.get("suggested_position_pct")

        # risk_manager's "signal" is a risk read, not a directional call:
        # bullish = low risk/manageable, bearish = elevated risk, flagged loudly.
        score = 60.0
        notes = []

        if vol is not None:
            if vol > HIGH_VOL_THRESHOLD:
                score -= 25
                notes.append(f"annualized volatility around {vol:.0%} is high — size accordingly")
            elif vol < 0.20:
                score += 10
                notes.append(f"volatility is contained at roughly {vol:.0%}")

        if beta is not None:
            if beta > 1.5:
                score -= 12
                notes.append(f"beta of {beta:.1f} means it will move harder than the market both ways")
            elif beta < 0.8:
                score += 8

        if drawdown is not None and drawdown < -0.40:
            score -= 15
            notes.append(f"a max drawdown of {drawdown:.0%} in the past year — this can go through real pain")

        if correlated:
            score -= min(20, 8 * len(correlated))
            peer_list = ", ".join(f"{t} ({c:.0%})" for t, c in correlated)
            notes.append(f"highly correlated with {peer_list} — concentration risk if held together, not diversification")

        if suggested_pct is not None:
            notes.append(f"suggested single-position sizing around {suggested_pct:.0f}% of a risk budget given its volatility")

        signal, confidence = score_to_signal(score)

        risk_label = "manageable" if signal == "bullish" else "elevated" if signal == "bearish" else "moderate"
        reasoning = f"Risk profile for {data.ticker} looks {risk_label}: {'; '.join(notes[:3]) or 'nothing unusual in the numbers'}."
        return signal, confidence, reasoning
