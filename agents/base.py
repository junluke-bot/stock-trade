"""Shared contract every investor-persona agent implements."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

from data_layer import StockData

Signal = str  # one of "bullish", "neutral", "bearish"


@dataclass
class AgentSignal:
    """The verdict one agent renders for one ticker."""

    agent_key: str
    investor_name: str
    signal: Signal
    confidence: int  # 0-100
    reasoning: str
    metrics: dict[str, Any] = field(default_factory=dict)
    data_warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.confidence = max(0, min(100, int(round(self.confidence))))
        if self.signal not in ("bullish", "neutral", "bearish"):
            self.signal = "neutral"


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def score_to_signal(
    score: float, bullish_threshold: float = 65.0, bearish_threshold: float = 40.0
) -> tuple[Signal, int]:
    """Map an unbounded 0-centered-at-50 bull/bear score to (signal, confidence).

    `score` measures direction (above threshold = bullish, below = bearish);
    confidence measures conviction, i.e. distance from the neutral midpoint
    (50) — NOT the raw score itself. A score of 5 is a strong bearish call
    (high confidence in "bearish"), not a low-confidence anything.
    """
    if score >= bullish_threshold:
        signal: Signal = "bullish"
    elif score <= bearish_threshold:
        signal = "bearish"
    else:
        signal = "neutral"
    confidence = int(round(clamp(abs(score - 50) * 2)))
    return signal, confidence


class InvestorAgent(ABC):
    """Base class for every persona agent.

    Subclasses implement `compute_metrics` (pure data extraction/derivation
    from a StockData, tolerant of missing fields) and `evaluate` (the
    investor's judgment applied to those metrics). `analyze` wires the two
    together and is the only method callers need.
    """

    key: ClassVar[str] = "base"
    investor_name: ClassVar[str] = "Unnamed Investor"

    @abstractmethod
    def compute_metrics(self, data: StockData) -> dict[str, Any]:
        """Extract/derive the raw numbers this agent's thesis depends on."""

    @abstractmethod
    def evaluate(self, data: StockData, metrics: dict[str, Any]) -> tuple[Signal, int, str]:
        """Turn metrics into (signal, confidence, reasoning-in-character)."""

    def analyze(self, data: StockData) -> AgentSignal:
        try:
            metrics = self.compute_metrics(data)
        except Exception as exc:
            return AgentSignal(
                agent_key=self.key,
                investor_name=self.investor_name,
                signal="neutral",
                confidence=0,
                reasoning=(
                    f"Couldn't even assemble the numbers I'd need for {data.ticker} "
                    f"({exc}) — no view."
                ),
                metrics={},
                data_warnings=list(data.warnings),
            )

        try:
            signal, confidence, reasoning = self.evaluate(data, metrics)
        except Exception as exc:
            return AgentSignal(
                agent_key=self.key,
                investor_name=self.investor_name,
                signal="neutral",
                confidence=0,
                reasoning=(
                    f"Had partial numbers for {data.ticker} but couldn't form a "
                    f"coherent view ({exc}) — sitting this one out."
                ),
                metrics=metrics,
                data_warnings=list(data.warnings),
            )

        return AgentSignal(
            agent_key=self.key,
            investor_name=self.investor_name,
            signal=signal,
            confidence=confidence,
            reasoning=reasoning,
            metrics=metrics,
            data_warnings=list(data.warnings),
        )
