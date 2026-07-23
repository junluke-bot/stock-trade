"""Small numeric helpers shared across agents: growth rates, DCF, technicals.

Every function returns `None` (or an empty structure) on undefined/degenerate
input rather than raising, so agents can chain them without a try/except
around every call.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def safe_div(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator is None or denominator == 0:
        return None
    try:
        return float(numerator) / float(denominator)
    except (TypeError, ValueError):
        return None


def cagr(begin: Optional[float], end: Optional[float], years: float) -> Optional[float]:
    """Compound annual growth rate. Undefined if signs differ or begin <= 0."""
    if begin is None or end is None or years <= 0:
        return None
    if begin <= 0 or end <= 0:
        return None
    try:
        return (end / begin) ** (1.0 / years) - 1.0
    except (ValueError, ZeroDivisionError):
        return None


def series_cagr(series: pd.Series, years: Optional[float] = None) -> Optional[float]:
    """CAGR from the first to last value of an oldest->newest series."""
    if series is None or len(series.dropna()) < 2:
        return None
    clean = series.dropna()
    n_years = years if years is not None else max(len(clean) - 1, 1)
    return cagr(float(clean.iloc[0]), float(clean.iloc[-1]), n_years)


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_series = 100 - (100 / (1 + rs))
    return rsi_series.fillna(50)


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def max_drawdown(close: pd.Series) -> Optional[float]:
    if close is None or close.empty:
        return None
    running_max = close.cummax()
    drawdown = (close - running_max) / running_max
    return float(drawdown.min())


def annualized_volatility(close: pd.Series, trading_days: int = 252) -> Optional[float]:
    if close is None or len(close) < 2:
        return None
    returns = close.pct_change().dropna()
    if returns.empty:
        return None
    return float(returns.std() * np.sqrt(trading_days))


def discounted_cash_flow(
    base_cash_flow: float,
    growth_rate: float,
    discount_rate: float,
    years: int = 10,
    terminal_growth: float = 0.025,
) -> Optional[float]:
    """Single-stage-growth-then-terminal-value DCF. Returns total PV (equity-level
    if base_cash_flow is an equity-level cash flow like owner earnings/FCF)."""
    if discount_rate <= terminal_growth:
        return None
    pv_sum = 0.0
    cash_flow = base_cash_flow
    for year in range(1, years + 1):
        cash_flow = cash_flow * (1 + growth_rate)
        pv_sum += cash_flow / ((1 + discount_rate) ** year)
    terminal_value = (cash_flow * (1 + terminal_growth)) / (discount_rate - terminal_growth)
    pv_sum += terminal_value / ((1 + discount_rate) ** years)
    return pv_sum


def graham_number(eps: Optional[float], book_value_per_share: Optional[float]) -> Optional[float]:
    if eps is None or book_value_per_share is None or eps <= 0 or book_value_per_share <= 0:
        return None
    return float(np.sqrt(22.5 * eps * book_value_per_share))
