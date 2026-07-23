"""Streamlit dashboard for ai-investor-panel.

Educational use only — see README.md disclaimer. Not financial advice.

Run with: streamlit run app.py
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from agents import ANALYST_AGENTS, AgentSignal, PortfolioManagerAgent, PortfolioVerdict
from agents.risk_manager import RiskManagerAgent
from data_layer import StockData, fetch_stock_data
from utils.report import build_report_markdown
from main import REPORTS_DIR

st.set_page_config(page_title="AI Investor Panel", page_icon="📊", layout="wide")

SIGNAL_COLOR = {"bullish": "#1a7f37", "neutral": "#9a6700", "bearish": "#cf222e"}
SIGNAL_BG = {"bullish": "#dafbe1", "neutral": "#fff8c5", "bearish": "#ffebe9"}
VERDICT_BOX = {"bullish": st.success, "neutral": st.warning, "bearish": st.error}


@st.cache_data(ttl=1800, show_spinner=False)
def cached_fetch(ticker: str) -> StockData:
    return fetch_stock_data(ticker)


def run_agents_for_ticker(data: StockData, peer_returns: dict[str, pd.Series]) -> list[AgentSignal]:
    signals = []
    for agent_cls in ANALYST_AGENTS:
        agent = agent_cls()
        if isinstance(agent, RiskManagerAgent):
            agent.peer_returns = peer_returns
        signals.append(agent.analyze(data))
    return signals


def signal_badge(signal: str) -> str:
    color = SIGNAL_COLOR.get(signal, "#57606a")
    bg = SIGNAL_BG.get(signal, "#eaeef2")
    return (
        f'<span style="background:{bg};color:{color};padding:2px 10px;'
        f'border-radius:12px;font-weight:600;font-size:0.85em;white-space:nowrap;">'
        f"{signal.upper()}</span>"
    )


def render_agent_table(signals: list[AgentSignal]) -> None:
    rows = [
        {
            "Agent": sig.investor_name,
            "Signal": signal_badge(sig.signal),
            "Confidence": sig.confidence,
            "Reasoning": sig.reasoning,
        }
        for sig in signals
    ]
    df = pd.DataFrame(rows)
    st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)


def render_show_work(signals: list[AgentSignal]) -> None:
    for sig in signals:
        with st.expander(f"{sig.investor_name} — raw metrics"):
            if not sig.metrics:
                st.caption("No metrics available.")
            else:
                st.json({k: (v if not isinstance(v, float) else round(v, 4)) for k, v in sig.metrics.items()})


def render_verdict(verdict: PortfolioVerdict) -> None:
    body = (
        f"**Overall signal: {verdict.overall_signal.upper()}** — Conviction: {verdict.conviction}/100\n\n"
        f"**Bull case:** {verdict.bull_case}\n\n"
        f"**Bear case:** {verdict.bear_case}\n\n"
        f"**Panel agreement:** {verdict.disagreement_level.upper()} disagreement — "
        f"{verdict.disagreement_detail}\n\n"
        f"**What would change this thesis:** {verdict.thesis_breaker}"
    )
    box_fn = VERDICT_BOX.get(verdict.overall_signal, st.info)
    box_fn(body)


def render_ticker(ticker: str, data: StockData, peer_returns: dict[str, pd.Series],
                   portfolio_manager: PortfolioManagerAgent, show_work: bool, save_report: bool) -> None:
    if data.history.empty and not data.info:
        st.error(f"No data available for {ticker}: {'; '.join(data.errors) or 'unknown error'}")
        return

    st.subheader(f"{data.ticker} — {data.long_name}")
    if data.warnings:
        st.caption("⚠️ " + "; ".join(data.warnings))

    signals = run_agents_for_ticker(data, peer_returns)
    render_agent_table(signals)

    if show_work:
        render_show_work(signals)

    verdict = portfolio_manager.synthesize(data, signals)
    render_verdict(verdict)

    report_md = build_report_markdown(data, signals, verdict)
    col1, col2 = st.columns([1, 5])
    with col1:
        st.download_button(
            "Download report (.md)",
            data=report_md,
            file_name=f"{ticker}_{date.today().isoformat()}.md",
            mime="text/markdown",
            key=f"download_{ticker}",
        )
    if save_report:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_path = REPORTS_DIR / f"{ticker}_{date.today().isoformat()}.md"
        report_path.write_text(report_md, encoding="utf-8")
        with col2:
            st.caption(f"Saved to {report_path}")


def main() -> None:
    st.title("📊 AI Investor Panel")
    st.warning(
        "**Educational use only — not financial advice.** These agents are simplified, "
        "automated heuristics loosely inspired by public investing philosophies. They do "
        "not represent the real individuals' views and can be wrong or based on incomplete "
        "data. Do your own research and consult a licensed professional before investing."
    )

    with st.sidebar:
        st.header("Analyze")
        ticker_input = st.text_input("Ticker(s)", value="AAPL", help="Comma-separated, e.g. AAPL,NVDA,TSLA")
        show_work = st.checkbox("Show raw metrics (--show-work)", value=False)
        save_report = st.checkbox("Save report to /reports", value=False)
        run_clicked = st.button("Analyze", type="primary")

    if not run_clicked and "last_tickers" not in st.session_state:
        st.info("Enter one or more tickers in the sidebar and click **Analyze**.")
        return

    if run_clicked:
        st.session_state["last_tickers"] = ticker_input
        st.session_state["last_show_work"] = show_work
        st.session_state["last_save_report"] = save_report

    tickers = [t.strip().upper() for t in st.session_state.get("last_tickers", "").split(",") if t.strip()]
    show_work = st.session_state.get("last_show_work", False)
    save_report = st.session_state.get("last_save_report", False)

    if not tickers:
        st.error("No valid tickers provided.")
        return

    fetched: dict[str, StockData] = {}
    with st.spinner(f"Fetching data for {', '.join(tickers)}..."):
        for ticker in tickers:
            fetched[ticker] = cached_fetch(ticker)

    peer_returns: dict[str, pd.Series] = {
        ticker: data.history["Close"].pct_change().dropna()
        for ticker, data in fetched.items()
        if "Close" in data.history and not data.history.empty
    }

    portfolio_manager = PortfolioManagerAgent()

    if len(tickers) == 1:
        render_ticker(tickers[0], fetched[tickers[0]], peer_returns, portfolio_manager, show_work, save_report)
    else:
        tabs = st.tabs(tickers)
        for tab, ticker in zip(tabs, tickers):
            with tab:
                render_ticker(ticker, fetched[ticker], peer_returns, portfolio_manager, show_work, save_report)


main()
