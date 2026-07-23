"""ai-investor-panel: analyze stocks through the lens of famous investors.

Educational use only — see README.md disclaimer. Not financial advice.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agents import ANALYST_AGENTS, AgentSignal, PortfolioManagerAgent, PortfolioVerdict
from agents.risk_manager import RiskManagerAgent
from data_layer import StockData, fetch_stock_data
from utils.report import build_report_markdown

REPORTS_DIR = Path(__file__).parent / "reports"

SIGNAL_STYLE = {
    "bullish": "bold green",
    "neutral": "yellow",
    "bearish": "bold red",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ai-investor-panel",
        description="Analyze one or more stocks through a panel of famous-investor personas.",
    )
    parser.add_argument(
        "--ticker", required=True,
        help="Ticker symbol, or comma-separated list (e.g. AAPL or AAPL,NVDA,TSLA).",
    )
    parser.add_argument(
        "--show-work", action="store_true",
        help="Print the raw metrics each agent used to reach its verdict.",
    )
    parser.add_argument(
        "--no-report", action="store_true",
        help="Skip writing the markdown report to /reports.",
    )
    return parser.parse_args(argv)


def run_agents_for_ticker(
    data: StockData, peer_returns: dict[str, pd.Series]
) -> list[AgentSignal]:
    signals = []
    for agent_cls in ANALYST_AGENTS:
        agent = agent_cls()
        if isinstance(agent, RiskManagerAgent):
            agent.peer_returns = peer_returns
        signals.append(agent.analyze(data))
    return signals


def render_ticker_table(console: Console, data: StockData, signals: list[AgentSignal]) -> None:
    title = f"{data.ticker} — {data.long_name}"
    table = Table(title=title, show_lines=True, expand=True)
    table.add_column("Agent", style="bold", ratio=2)
    table.add_column("Signal", ratio=1)
    table.add_column("Confidence", justify="right", ratio=1)
    table.add_column("Reasoning", ratio=6)

    for sig in signals:
        style = SIGNAL_STYLE.get(sig.signal, "white")
        table.add_row(
            sig.investor_name,
            f"[{style}]{sig.signal.upper()}[/{style}]",
            f"{sig.confidence}",
            sig.reasoning,
        )
    console.print(table)


def render_show_work(console: Console, signals: list[AgentSignal]) -> None:
    for sig in signals:
        console.print(f"[bold]{sig.investor_name}[/bold] ({sig.agent_key}) raw metrics:")
        if not sig.metrics:
            console.print("  (none)")
        else:
            for key, val in sig.metrics.items():
                console.print(f"  {key}: {val}")
        console.print()


def render_verdict(console: Console, verdict: PortfolioVerdict) -> None:
    style = SIGNAL_STYLE.get(verdict.overall_signal, "white")
    body = (
        f"[{style}]Overall signal: {verdict.overall_signal.upper()}[/{style}]  "
        f"Conviction: {verdict.conviction}/100\n\n"
        f"[bold]Bull case:[/bold] {verdict.bull_case}\n\n"
        f"[bold]Bear case:[/bold] {verdict.bear_case}\n\n"
        f"[bold]Panel agreement:[/bold] {verdict.disagreement_level.upper()} disagreement — "
        f"{verdict.disagreement_detail}\n\n"
        f"[bold]What would change this thesis:[/bold] {verdict.thesis_breaker}"
    )
    console.print(Panel(body, title=f"Portfolio Manager Verdict — {verdict.ticker}", border_style=style))


def write_markdown_report(data: StockData, signals: list[AgentSignal], verdict: PortfolioVerdict) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"{data.ticker}_{date.today().isoformat()}.md"
    report_path.write_text(build_report_markdown(data, signals, verdict), encoding="utf-8")
    return report_path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    console = Console()
    tickers = [t.strip().upper() for t in args.ticker.split(",") if t.strip()]

    if not tickers:
        console.print("[bold red]No valid tickers provided.[/bold red]")
        return 1

    console.print(f"[bold]Fetching data for: {', '.join(tickers)}[/bold]\n")

    fetched: dict[str, StockData] = {}
    for ticker in tickers:
        with console.status(f"Fetching {ticker}..."):
            fetched[ticker] = fetch_stock_data(ticker)

    peer_returns: dict[str, pd.Series] = {}
    for ticker, data in fetched.items():
        if "Close" in data.history and not data.history.empty:
            peer_returns[ticker] = data.history["Close"].pct_change().dropna()

    portfolio_manager = PortfolioManagerAgent()
    exit_code = 0

    for ticker in tickers:
        data = fetched[ticker]
        if data.history.empty and not data.info:
            console.print(f"[bold red]Skipping {ticker}: {'; '.join(data.errors) or 'no data available'}[/bold red]\n")
            exit_code = 1
            continue

        if data.warnings:
            console.print(f"[dim]Note for {ticker}: {'; '.join(data.warnings)}[/dim]")

        signals = run_agents_for_ticker(data, peer_returns)
        render_ticker_table(console, data, signals)

        if args.show_work:
            render_show_work(console, signals)

        verdict = portfolio_manager.synthesize(data, signals)
        render_verdict(console, verdict)

        if not args.no_report:
            report_path = write_markdown_report(data, signals, verdict)
            console.print(f"[dim]Report written to {report_path}[/dim]")

        console.print()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
