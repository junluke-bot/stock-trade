"""Builds the markdown report body shared by the CLI and the Streamlit app."""
from __future__ import annotations

from datetime import date

from agents.base import AgentSignal
from agents.portfolio_manager import PortfolioVerdict
from data_layer import StockData


def build_report_markdown(data: StockData, signals: list[AgentSignal], verdict: PortfolioVerdict) -> str:
    today = date.today().isoformat()
    lines = [
        f"# {data.ticker} — {data.long_name}",
        "",
        f"*Generated {today}. Educational use only — not financial advice.*",
        "",
        "## Agent Panel",
        "",
        "| Agent | Signal | Confidence | Reasoning |",
        "|---|---|---|---|",
    ]
    for sig in signals:
        reasoning = sig.reasoning.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {sig.investor_name} | {sig.signal.upper()} | {sig.confidence} | {reasoning} |")

    lines += [
        "",
        "## Portfolio Manager Verdict",
        "",
        f"- **Overall signal:** {verdict.overall_signal.upper()}",
        f"- **Conviction:** {verdict.conviction}/100",
        f"- **Bull case:** {verdict.bull_case}",
        f"- **Bear case:** {verdict.bear_case}",
        f"- **Panel disagreement:** {verdict.disagreement_level.upper()} — {verdict.disagreement_detail}",
        f"- **What would change this thesis:** {verdict.thesis_breaker}",
    ]

    if data.warnings:
        lines += ["", "## Data Notes", ""]
        lines += [f"- {w}" for w in data.warnings]

    return "\n".join(lines)
