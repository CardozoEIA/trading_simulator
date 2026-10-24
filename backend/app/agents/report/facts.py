# app/agents/report/facts.py
"""Report structure (US-32), built by code from the recorded simulation data.

Every section carries the rows/table the student sees (rendered by code) and the
fact sentences the model may use for its narrative. The verification step only
accepts numbers and dates that appear in those facts.
"""
from app.agents.insights.facts import money, round_trips

NARRATED_SECTIONS = ("setup", "performance", "key_decisions", "benchmark")
MAX_TABLE_TRADES = 30

DISCLAIMER = (
    "This report was generated from the recorded data of an educational backtest on historical prices. "
    "No real money was traded. It is not financial advice, and past simulated performance is not a "
    "guarantee of future results."
)


def pct(value: float) -> str:
    return f"{value:.2f}%"


def signed_pct(value: float) -> str:
    return f"+{value:.2f}%" if value > 0 else pct(value)


def _row(label: str, value: str) -> dict:
    return {"label": label, "value": value}


def _setup(configuration: dict) -> dict:
    risk = configuration["risk"]
    strategies = ", ".join(configuration.get("strategies") or []) or "n/a"
    facts = (
        f"Asset: {configuration['asset']}. Period: {configuration['start_date']} to {configuration['end_date']}. "
        f"Strategies: {strategies}. Initial capital: {money(float(configuration['initial_capital']))}. "
        f"Risk limits: stop-loss {pct(float(risk['stop_loss_percentage']))}, maximum position size "
        f"{pct(float(risk['max_position_size']))} of the portfolio, maximum drawdown {pct(float(risk['max_drawdown']))}."
    )
    return {
        "key": "setup",
        "title": "Setup",
        "facts": facts,
        "rows": [
            _row("Asset", configuration["asset"]),
            _row("Period", f"{configuration['start_date']} to {configuration['end_date']}"),
            _row("Strategies", strategies),
            _row("Initial capital", money(float(configuration["initial_capital"]))),
            _row("Stop-loss", pct(float(risk["stop_loss_percentage"]))),
            _row("Max position size", pct(float(risk["max_position_size"]))),
            _row("Max drawdown limit", pct(float(risk["max_drawdown"]))),
        ],
    }


def _performance(simulation: dict, results: dict, metrics: dict, highlights: dict) -> dict:
    stopped = simulation["status"] == "STOPPED_BY_RISK"
    status_text = "Stopped early by the risk manager" if stopped else "Completed normally"
    profit_factor = metrics.get("profit_factor")
    total_trades = int(metrics["total_trades"])

    lines = [
        f"Status: {status_text.lower()}"
        + (f" (reason recorded: {simulation.get('stop_reason') or 'not recorded'})." if stopped else "."),
        f"Final portfolio value: {money(float(results['final_capital']))}. "
        f"Profit/loss: {money(float(results['profit_loss']))}. "
        f"Total return: {pct(float(metrics['total_return_pct']))}.",
        f"Sharpe ratio: {float(metrics['sharpe_ratio']):.2f}. "
        f"Maximum drawdown: {pct(float(metrics['max_drawdown_pct']))}.",
    ]
    if total_trades:
        lines.append(
            f"Completed trades (a buy followed by a sell): {total_trades}, of which {metrics['winning_trades']} "
            f"were winners (win rate {pct(float(metrics['win_rate']))}). "
            + (f"Profit factor: {float(profit_factor):.2f}." if profit_factor is not None
               else "Profit factor: not defined because there were no losing trades.")
        )
    else:
        lines.append("No trade was completed (no buy followed by a sell), so win rate and profit factor do not apply.")
    for kind in ("MAX_DRAWDOWN", "RISK_STOP"):
        if kind in highlights:
            lines.append(highlights[kind]["facts"])

    if total_trades:
        win_rate = pct(float(metrics["win_rate"]))
        pf = f"{float(profit_factor):.2f}" if profit_factor is not None else "No losing trades"
    else:
        win_rate = pf = "n/a"
    return {
        "key": "performance",
        "title": "Performance",
        "facts": "\n".join(lines),
        "rows": [
            _row("Status", status_text),
            _row("Final value", money(float(results["final_capital"]))),
            _row("Profit / loss", money(float(results["profit_loss"]))),
            _row("Total return", signed_pct(float(metrics["total_return_pct"]))),
            _row("Sharpe ratio", f"{float(metrics['sharpe_ratio']):.2f}"),
            _row("Max drawdown", pct(float(metrics["max_drawdown_pct"]))),
            _row("Win rate", win_rate),
            _row("Profit factor", pf),
            _row("Winning trades", f"{metrics['winning_trades']}/{total_trades}"),
        ],
    }


def _key_decisions(trades: list[dict], highlights: dict) -> dict:
    trips = round_trips(trades)
    buys = sum(1 for t in trades if t["type"] == "BUY")
    sells = sum(1 for t in trades if t["type"] == "SELL")

    if not trades:
        lines = ["No trades were executed during this simulation."]
    else:
        lines = [f"Executed trades: {len(trades)} ({buys} buys and {sells} sells), "
                 f"forming {len(trips)} completed round trips."]
    for kind in ("BEST_TRADE", "WORST_TRADE"):
        if kind in highlights:
            lines.append(highlights[kind]["facts"])
    open_position = bool(trades) and trades[-1]["type"] == "BUY"
    if open_position:
        last = trades[-1]
        lines.append(
            f"The last trade was a buy on {last['date']} at ${float(last['price']):.2f}; "
            "that position was still open at the end of the run."
        )

    shown = trips[:MAX_TABLE_TRADES]
    notes = []
    if len(trips) > len(shown):
        notes.append(f"Showing the first {len(shown)} of {len(trips)} completed round trips.")
    if open_position:
        notes.append("The last buy has no matching sell: the position was still open at the end.")
    return {
        "key": "key_decisions",
        "title": "Key decisions",
        "facts": "\n".join(lines),
        "rows": [
            _row("Executed trades", f"{len(trades)} ({buys} buys, {sells} sells)"),
            _row("Completed round trips", str(len(trips))),
        ],
        "table": {
            "columns": ["Bought", "Sold", "Buy price", "Sell price", "Result", "Return"],
            "rows": [
                [t.buy_date, t.sell_date, f"${t.buy_price:.2f}", f"${t.sell_price:.2f}",
                 money(t.pnl), signed_pct(t.return_pct)]
                for t in shown
            ],
        } if shown else None,
        "note": " ".join(notes) or None,
    }


def _benchmark(configuration: dict, metrics: dict) -> dict:
    benchmark = configuration.get("benchmark")
    strategy_return = float(metrics["total_return_pct"])
    if not benchmark:
        return {
            "key": "benchmark",
            "title": "Benchmark",
            "facts": f"The strategy returned {pct(strategy_return)}. The buy & hold comparison is not available for this simulation.",
            "rows": [_row("Strategy return", signed_pct(strategy_return)), _row("Buy & hold return", "n/a")],
        }

    bh_return = float(benchmark["total_return_pct"])
    diff = strategy_return - bh_return
    beat = diff > 0
    facts = (
        f"Buy & hold means investing the full initial capital of {money(float(benchmark['initial_capital']))} "
        f"in {configuration['asset']} on the first trading day of the period ({configuration['start_date']} to "
        f"{configuration['end_date']}) and holding it until the end: final value {money(float(benchmark['final_capital']))}, return {pct(bh_return)}. "
        f"The strategy returned {pct(strategy_return)}, so it {'beat' if beat else 'trailed'} buy & hold "
        f"by {abs(diff):.2f} percentage points."
    )
    return {
        "key": "benchmark",
        "title": "Benchmark",
        "facts": facts,
        "rows": [
            _row("Strategy return", signed_pct(strategy_return)),
            _row("Buy & hold return", signed_pct(bh_return)),
            _row("Buy & hold final value", money(float(benchmark["final_capital"]))),
            _row("Difference", f"{'Beat' if beat else 'Trailed'} by {abs(diff):.2f} pts"),
        ],
    }


def build_sections(data: dict) -> list[dict]:
    """The fixed report sections, in order. Narratives are added later by the agent."""
    highlights = {h["kind"]: h for h in data.get("highlights") or []}
    sections = [
        _setup(data["configuration"]),
        _performance(data["simulation"], data["results"], data["metrics"], highlights),
        _key_decisions(data["trades"], highlights),
        _benchmark(data["configuration"], data["metrics"]),
        {"key": "disclaimer", "title": "Disclaimer", "facts": "", "rows": [], "narrative": DISCLAIMER},
    ]
    for section in sections:
        section.setdefault("narrative", None)
        section.setdefault("table", None)
        section.setdefault("note", None)
    return sections
