"""Synthesizes all persona agents' signals into one final verdict per ticker.

Deliberately does not average away disagreement: the verdict surfaces the
strongest bull and bear case verbatim, and reports a disagreement score so a
reader can see when the panel is split rather than aligned.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from data_layer import StockData

from .base import AgentSignal

SIGNAL_WEIGHT = {"bullish": 1.0, "neutral": 0.0, "bearish": -1.0}

# Agents whose job is describing risk/trend rather than taking a directional
# fundamental view get a lighter vote in the overall signal, but their
# reasoning still surfaces in bull/bear cases and thesis-breakers.
VOTE_WEIGHT_OVERRIDES = {
    "technical_analyst": 0.6,
    "risk_manager": 0.5,
}


@dataclass
class PortfolioVerdict:
    ticker: str
    overall_signal: str
    conviction: int
    bull_case: str
    bear_case: str
    thesis_breaker: str
    disagreement_level: str
    disagreement_detail: str
    signals: list[AgentSignal] = field(default_factory=list)


class PortfolioManagerAgent:
    key = "portfolio_manager"
    investor_name = "The Portfolio Manager"

    def synthesize(self, data: StockData, signals: list[AgentSignal]) -> PortfolioVerdict:
        if not signals:
            return PortfolioVerdict(
                ticker=data.ticker,
                overall_signal="neutral",
                conviction=0,
                bull_case="No agent could form a view.",
                bear_case="No agent could form a view.",
                thesis_breaker="More data becoming available.",
                disagreement_level="unknown",
                disagreement_detail="No signals to compare.",
                signals=[],
            )

        weighted_sum = 0.0
        weight_total = 0.0
        for sig in signals:
            weight = VOTE_WEIGHT_OVERRIDES.get(sig.agent_key, 1.0)
            confidence_weight = sig.confidence / 100.0
            weighted_sum += SIGNAL_WEIGHT[sig.signal] * confidence_weight * weight
            weight_total += confidence_weight * weight

        avg_score = (weighted_sum / weight_total) if weight_total > 0 else 0.0

        if avg_score > 0.15:
            overall_signal = "bullish"
        elif avg_score < -0.15:
            overall_signal = "bearish"
        else:
            overall_signal = "neutral"

        conviction = round(min(100, abs(avg_score) * 100 + (weight_total / len(signals)) * 20))

        bullish = [s for s in signals if s.signal == "bullish"]
        bearish = [s for s in signals if s.signal == "bearish"]

        top_bull = max(bullish, key=lambda s: s.confidence, default=None)
        top_bear = max(bearish, key=lambda s: s.confidence, default=None)

        bull_case = (
            f"{top_bull.investor_name}: {top_bull.reasoning}"
            if top_bull else "No agent on the panel currently makes a bullish case."
        )
        bear_case = (
            f"{top_bear.investor_name}: {top_bear.reasoning}"
            if top_bear else "No agent on the panel currently makes a bearish case."
        )

        n_bull, n_bear, n_neutral = len(bullish), len(bearish), len(signals) - len(bullish) - len(bearish)
        if n_bull > 0 and n_bear > 0:
            spread = min(n_bull, n_bear) / len(signals)
            if spread >= 0.35:
                disagreement_level = "high"
            elif spread >= 0.15:
                disagreement_level = "moderate"
            else:
                disagreement_level = "low"
        else:
            disagreement_level = "low"

        disagreement_detail = (
            f"{n_bull} bullish / {n_neutral} neutral / {n_bear} bearish out of {len(signals)} agents."
        )
        if disagreement_level in ("high", "moderate") and top_bull and top_bear:
            disagreement_detail += (
                f" {top_bull.investor_name} and {top_bear.investor_name} see this in opposite directions "
                f"— that split is the real story here, not the averaged score."
            )

        thesis_breaker = self._build_thesis_breaker(signals, overall_signal)

        return PortfolioVerdict(
            ticker=data.ticker,
            overall_signal=overall_signal,
            conviction=int(conviction),
            bull_case=bull_case,
            bear_case=bear_case,
            thesis_breaker=thesis_breaker,
            disagreement_level=disagreement_level,
            disagreement_detail=disagreement_detail,
            signals=signals,
        )

    @staticmethod
    def _build_thesis_breaker(signals: list[AgentSignal], overall_signal: str) -> str:
        by_key = {s.agent_key: s for s in signals}

        if overall_signal == "bullish":
            candidates = []
            wb = by_key.get("warren_buffett")
            if wb and wb.metrics.get("margin_of_safety") is not None:
                candidates.append(
                    "a sustained deterioration in margins or return on equity that erodes the "
                    "estimated margin of safety"
                )
            cw = by_key.get("cathie_wood")
            if cw and cw.metrics.get("revenue_cagr") is not None:
                candidates.append("revenue growth decelerating meaningfully below its recent trend")
            ta = by_key.get("technical_analyst")
            if ta and ta.metrics.get("golden_cross"):
                candidates.append("the 50-day moving average crossing back below the 200-day")
            rm = by_key.get("risk_manager")
            if rm and rm.metrics.get("correlated_peers"):
                candidates.append("a shared shock hitting the whole basket of correlated names at once")
            return (
                "; ".join(candidates[:2]) or "a clear break in the fundamentals the bull case depends on"
            ) + " would change this thesis."

        if overall_signal == "bearish":
            candidates = []
            mb = by_key.get("michael_burry")
            if mb and mb.metrics.get("fcf_yield") is not None:
                candidates.append("free cash flow generation turning positive and durable")
            bg = by_key.get("ben_graham")
            if bg and bg.metrics.get("pe_ratio") is not None:
                candidates.append("a valuation reset that restores a real margin of safety")
            candidates.append("evidence the balance sheet or earnings quality concerns are being resolved")
            return "; ".join(candidates[:2]) + " would change this thesis."

        return (
            "A decisive move in either fundamentals (growth, margins, balance sheet) or "
            "price/technicals strong enough to break the current tie among the panel."
        )
