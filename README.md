# ai-investor-panel

Analyze a stock through the lens of eight famous investors, then have a
portfolio manager agent synthesize their (often conflicting) views into one
verdict — with the disagreement surfaced explicitly, not averaged away.

> ## ⚠️ Disclaimer
> **This tool is for educational and entertainment purposes only. It is not
> financial advice, and nothing it outputs should be used as the basis for
> an actual investment decision.** The "investor" agents are simplified,
> automated heuristics loosely inspired by public writings/interviews of
> real people — they do not represent those individuals' actual views, and
> they can be wrong, stale, or based on incomplete data. Markets involve
> risk of loss. Do your own research and consult a licensed financial
> professional before making investment decisions.

## What it does

For each ticker, eight agents independently analyze the same underlying
market data (price history, fundamentals, financials) through a distinct
investing philosophy:

| Agent | Focus |
|---|---|
| `warren_buffett` | Moats, owner earnings, ROE consistency, low debt, DCF margin of safety |
| `charlie_munger` | Business quality over price, avoiding stupidity, penalizes complexity/dilution/hype |
| `cathie_wood` | Disruptive growth, TAM expansion, R&D intensity, 5-year forward price target |
| `ben_graham` | Net-net working capital, P/E & P/B screens, Graham Number, dividend record |
| `michael_burry` | Contrarian deep value, FCF yield, insider activity, crowded-trade skepticism |
| `peter_lynch` | Growth at a reasonable price (PEG), earnings momentum, stock category |
| `technical_analyst` | 50/200-day SMA trend, RSI, MACD, volume, support/resistance |
| `risk_manager` | Volatility, beta, max drawdown, correlation/concentration warnings |

A `portfolio_manager` agent then weighs all eight signals into an overall
verdict per ticker: signal, conviction score, bull case, bear case, level of
panel disagreement, and what would change the thesis.

## Setup

```bash
# from this directory
py -3 -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
```

Requires Python 3.9+. Uses only [yfinance](https://pypi.org/project/yfinance/)
for market data — no paid APIs or API keys needed.

## Usage

### CLI

```bash
python main.py --ticker AAPL
python main.py --ticker AAPL,NVDA,TSLA
python main.py --ticker AAPL --show-work     # print the raw metrics each agent used
python main.py --ticker AAPL --no-report     # skip writing the markdown report
```

Output is a rich terminal table per ticker (one row per agent) followed by
the portfolio manager's verdict panel. A markdown report is also written to
`reports/{TICKER}_{YYYY-MM-DD}.md` unless `--no-report` is passed.

### Web app

**Windows:** double-click `run_app.bat` — it starts the server in its own
window and opens the dashboard in your default browser automatically.

**Any platform:**

```bash
streamlit run app.py
```

(add `--server.port 8600` if the default port 8501 is blocked/reserved on
your machine — Windows sometimes excludes it for other services)

Opens a local browser dashboard: enter one or more comma-separated tickers in
the sidebar, click **Analyze**, and view the same agent panel/verdict as the
CLI, with an option to show raw metrics, download the markdown report, or
save it to `/reports`.

## Notes on data quality

Real tickers are missing real data all the time — no dividends, negative
earnings, thin analyst coverage, delisted comparables, etc. Every agent is
built to degrade gracefully: if a required metric can't be computed, that
agent returns a low-confidence "neutral" signal explaining what was missing,
rather than crashing the whole run or hallucinating a number. Data fetches
retry automatically on transient failures; persistent failures are reported
as warnings in the terminal output and in the markdown report.

## Project layout

```
main.py                    CLI entry point
app.py                      Streamlit web dashboard
data_layer/fetcher.py       yfinance wrapper: StockData dataclass, retries
agents/base.py              InvestorAgent ABC + AgentSignal dataclass
agents/*.py                 one module per investor persona
agents/portfolio_manager.py synthesis agent (weights signals, surfaces disagreement)
utils/metrics.py            shared math: CAGR, DCF, RSI, MACD, drawdown, etc.
utils/report.py              shared markdown report builder (CLI + app)
reports/                    generated markdown reports (gitignored)
```
