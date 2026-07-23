"""Technical analyst persona: trend, RSI, MACD, volume, support/resistance. Price-only."""
from __future__ import annotations

from typing import Any

from data_layer import StockData
from utils.metrics import macd, rsi, sma

from .base import InvestorAgent, Signal, score_to_signal


class TechnicalAnalystAgent(InvestorAgent):
    key = "technical_analyst"
    investor_name = "The Technical Analyst"

    def compute_metrics(self, data: StockData) -> dict[str, Any]:
        close = data.history["Close"] if "Close" in data.history else None
        volume = data.history["Volume"] if "Volume" in data.history else None

        if close is None or close.empty:
            return {}

        sma50 = sma(close, 50)
        sma200 = sma(close, 200)
        latest_price = float(close.iloc[-1])
        latest_sma50 = float(sma50.iloc[-1]) if not sma50.dropna().empty else None
        latest_sma200 = float(sma200.iloc[-1]) if not sma200.dropna().empty else None

        golden_cross = None
        if latest_sma50 is not None and latest_sma200 is not None:
            golden_cross = latest_sma50 > latest_sma200

        rsi_series = rsi(close)
        latest_rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty else None

        macd_line, signal_line, hist = macd(close)
        macd_bullish = None
        if not hist.dropna().empty:
            macd_bullish = float(hist.iloc[-1]) > 0

        recent_volume = volume.tail(20).mean() if volume is not None and len(volume) >= 20 else None
        baseline_volume = volume.tail(100).mean() if volume is not None and len(volume) >= 100 else None
        volume_surge = None
        if recent_volume is not None and baseline_volume:
            volume_surge = (recent_volume / baseline_volume) - 1

        lookback = close.tail(126)
        resistance = float(lookback.max()) if not lookback.empty else None
        support = float(lookback.min()) if not lookback.empty else None

        return {
            "latest_price": latest_price,
            "sma50": latest_sma50,
            "sma200": latest_sma200,
            "golden_cross": golden_cross,
            "rsi": latest_rsi,
            "macd_bullish": macd_bullish,
            "volume_surge_pct": volume_surge,
            "support_6m": support,
            "resistance_6m": resistance,
        }

    def evaluate(self, data: StockData, metrics: dict[str, Any]) -> tuple[Signal, int, str]:
        if not metrics or metrics.get("latest_price") is None:
            return (
                "neutral",
                10,
                f"Not enough price history to chart {data.ticker} — no trend to read.",
            )

        price = metrics["latest_price"]
        sma50 = metrics.get("sma50")
        sma200 = metrics.get("sma200")
        golden_cross = metrics.get("golden_cross")
        rsi_val = metrics.get("rsi")
        macd_bullish = metrics.get("macd_bullish")
        support = metrics.get("support_6m")
        resistance = metrics.get("resistance_6m")

        score = 50.0
        notes = []

        if golden_cross is True:
            score += 18
            notes.append("50-day above the 200-day, a bullish long-term trend")
        elif golden_cross is False:
            score -= 18
            notes.append("50-day below the 200-day, a bearish long-term trend")

        if sma50 is not None:
            if price > sma50:
                score += 8
                notes.append("price holding above its 50-day average")
            else:
                score -= 8

        if rsi_val is not None:
            if rsi_val > 70:
                score -= 10
                notes.append(f"RSI at {rsi_val:.0f} is overbought territory")
            elif rsi_val < 30:
                score += 10
                notes.append(f"RSI at {rsi_val:.0f} is oversold, room to bounce")

        if macd_bullish is True:
            score += 10
            notes.append("MACD confirms upward momentum")
        elif macd_bullish is False:
            score -= 10
            notes.append("MACD shows fading momentum")

        volume_surge = metrics.get("volume_surge_pct")
        if volume_surge is not None and volume_surge > 0.3:
            notes.append("recent volume is running well above average, confirming conviction behind the move")

        if resistance is not None and price >= resistance * 0.98:
            notes.append(f"trading near six-month resistance around {resistance:.2f}")
        if support is not None and price <= support * 1.02:
            notes.append(f"sitting just above six-month support around {support:.2f}")

        signal, confidence = score_to_signal(score)

        reasoning = f"Chart read on {data.ticker}: {'; '.join(notes[:3]) or 'no strong signal either way'}."
        return signal, confidence, reasoning
