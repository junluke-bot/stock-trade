"""Fetches and normalizes market data from yfinance for downstream agents."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, TypeVar

import pandas as pd
import yfinance as yf

T = TypeVar("T")

DEFAULT_RETRIES = 3
DEFAULT_DELAY_SECONDS = 1.5


@dataclass
class StockData:
    """Container for everything fetched about a single ticker.

    All frame/series fields default to empty structures rather than None so
    agents can index into them without a None-check on every access; use the
    `warnings`/`errors` lists to know what's actually missing.
    """

    ticker: str
    info: dict[str, Any] = field(default_factory=dict)
    history: pd.DataFrame = field(default_factory=pd.DataFrame)
    financials: pd.DataFrame = field(default_factory=pd.DataFrame)
    quarterly_financials: pd.DataFrame = field(default_factory=pd.DataFrame)
    balance_sheet: pd.DataFrame = field(default_factory=pd.DataFrame)
    quarterly_balance_sheet: pd.DataFrame = field(default_factory=pd.DataFrame)
    cashflow: pd.DataFrame = field(default_factory=pd.DataFrame)
    quarterly_cashflow: pd.DataFrame = field(default_factory=pd.DataFrame)
    dividends: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    insider_transactions: pd.DataFrame = field(default_factory=pd.DataFrame)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    # --- convenience accessors used across many agents -------------------

    def info_get(self, *keys: str, default: Any = None) -> Any:
        """Return the first present, non-None value among `keys` in `info`."""
        for key in keys:
            val = self.info.get(key)
            if val is not None:
                return val
        return default

    @property
    def current_price(self) -> Optional[float]:
        price = self.info_get("currentPrice", "regularMarketPrice")
        if price is not None:
            return float(price)
        if not self.history.empty:
            return float(self.history["Close"].iloc[-1])
        return None

    @property
    def market_cap(self) -> Optional[float]:
        cap = self.info_get("marketCap")
        return float(cap) if cap is not None else None

    @property
    def shares_outstanding(self) -> Optional[float]:
        shares = self.info_get("sharesOutstanding")
        return float(shares) if shares is not None else None

    @property
    def sector(self) -> str:
        return self.info_get("sector", default="Unknown")

    @property
    def industry(self) -> str:
        return self.info_get("industry", default="Unknown")

    @property
    def long_name(self) -> str:
        return self.info_get("longName", "shortName", default=self.ticker)

    @property
    def has_dividends(self) -> bool:
        return not self.dividends.empty and self.dividends.tail(8).sum() > 0

    def annual_series(self, statement: str, row_name: str) -> pd.Series:
        """Pull one line item out of an annual statement, oldest -> newest.

        Returns an empty Series if the statement or row is unavailable
        instead of raising, so agents can treat missing fundamentals as
        "no data" rather than a crash.
        """
        frame: pd.DataFrame = getattr(self, statement, pd.DataFrame())
        if frame is None or frame.empty or row_name not in frame.index:
            return pd.Series(dtype=float)
        series = frame.loc[row_name].dropna()
        return series.sort_index()

    def latest_value(self, statement: str, row_name: str) -> Optional[float]:
        series = self.annual_series(statement, row_name)
        if series.empty:
            return None
        return float(series.iloc[-1])

    def annual_series_any(self, statement: str, row_names: list[str]) -> pd.Series:
        """Like `annual_series`, trying each candidate row label in order.

        yfinance's exact line-item labels drift across versions/tickers
        (e.g. "Total Debt" vs "Net Debt"), so agents pass a few aliases.
        """
        for name in row_names:
            series = self.annual_series(statement, name)
            if not series.empty:
                return series
        return pd.Series(dtype=float)

    def latest_value_any(self, statement: str, row_names: list[str]) -> Optional[float]:
        series = self.annual_series_any(statement, row_names)
        if series.empty:
            return None
        return float(series.iloc[-1])


def _retry(fn: Callable[[], T], label: str, warnings: list[str], errors: list[str],
           default: T, retries: int = DEFAULT_RETRIES, delay: float = DEFAULT_DELAY_SECONDS) -> T:
    last_exc: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except Exception as exc:  # yfinance raises a mix of exception types
            last_exc = exc
            if attempt < retries:
                time.sleep(delay * attempt)
    errors.append(f"{label}: failed after {retries} attempts ({last_exc})")
    warnings.append(f"Missing {label} — treating as unavailable.")
    return default


def fetch_stock_data(ticker: str, history_period: str = "5y") -> StockData:
    """Fetch all data an agent panel needs for one ticker, tolerating partial failures."""
    ticker = ticker.strip().upper()
    data = StockData(ticker=ticker)
    tk = yf.Ticker(ticker)

    def _frame(getter: Callable[[], Any]) -> Callable[[], pd.DataFrame]:
        return lambda: getter() if getter() is not None else pd.DataFrame()

    data.info = _retry(lambda: dict(tk.info or {}), "company info",
                        data.warnings, data.errors, default={})
    data.history = _retry(lambda: tk.history(period=history_period, auto_adjust=True),
                           "price history", data.warnings, data.errors,
                           default=pd.DataFrame())
    data.financials = _retry(_frame(lambda: tk.financials), "annual financials",
                              data.warnings, data.errors, default=pd.DataFrame())
    data.quarterly_financials = _retry(_frame(lambda: tk.quarterly_financials),
                                        "quarterly financials", data.warnings,
                                        data.errors, default=pd.DataFrame())
    data.balance_sheet = _retry(_frame(lambda: tk.balance_sheet), "balance sheet",
                                 data.warnings, data.errors, default=pd.DataFrame())
    data.quarterly_balance_sheet = _retry(_frame(lambda: tk.quarterly_balance_sheet),
                                           "quarterly balance sheet", data.warnings,
                                           data.errors, default=pd.DataFrame())
    data.cashflow = _retry(_frame(lambda: tk.cashflow), "cash flow statement",
                            data.warnings, data.errors, default=pd.DataFrame())
    data.quarterly_cashflow = _retry(_frame(lambda: tk.quarterly_cashflow),
                                      "quarterly cash flow", data.warnings,
                                      data.errors, default=pd.DataFrame())
    data.dividends = _retry(lambda: tk.dividends, "dividend history",
                             data.warnings, data.errors,
                             default=pd.Series(dtype=float))
    data.insider_transactions = _retry(_frame(lambda: tk.insider_transactions),
                                        "insider transactions", data.warnings,
                                        data.errors, default=pd.DataFrame())

    if data.history.empty and not data.info:
        data.errors.append(f"No data at all could be retrieved for '{ticker}'. "
                            "Check the ticker symbol.")

    return data
