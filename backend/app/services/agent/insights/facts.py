# app/services/agent/insights/facts.py
"""Pure calculations behind the proactive insights (US-26).

Every number the insights may mention is produced here from recorded simulation
data and formatted as text; the verification step only accepts numbers that
appear in these texts.
"""
from dataclasses import dataclass


def money(value: float) -> str:
    return f"-${abs(value):,.2f}" if value < 0 else f"${value:,.2f}"


@dataclass
class RoundTrip:
    buy_date: str
    sell_date: str
    buy_price: float
    sell_price: float
    quantity: float

    @property
    def pnl(self) -> float:
        return (self.sell_price - self.buy_price) * self.quantity

    @property
    def return_pct(self) -> float:
        return (self.sell_price / self.buy_price - 1) * 100 if self.buy_price else 0.0


def round_trips(trades: list[dict]) -> list[RoundTrip]:
    """Pairs consecutive BUY -> SELL trades (same rule as the US-16 metrics)."""
    result = []
    i = 0
    while i + 1 < len(trades):
        entry, exit_ = trades[i], trades[i + 1]
        if entry["type"] == "BUY" and exit_["type"] == "SELL":
            result.append(RoundTrip(
                buy_date=str(entry["date"]),
                sell_date=str(exit_["date"]),
                buy_price=float(entry["price"]),
                sell_price=float(exit_["price"]),
                quantity=float(entry["quantity"]),
            ))
            i += 2
        else:
            i += 1
    return result


def trade_performance_text(trades: list[dict]) -> str:
    if not trades:
        return "No trades were executed in this simulation."

    trips = round_trips(trades)
    buys = sum(1 for t in trades if t["type"] == "BUY")
    sells = sum(1 for t in trades if t["type"] == "SELL")
    lines = [f"Executed trades: {len(trades)} ({buys} BUY, {sells} SELL)."]

    if not trips:
        lines.append("No completed round-trips (BUY followed by SELL), so there is no closed trade to rank.")
    else:
        best = max(trips, key=lambda t: t.pnl)
        worst = min(trips, key=lambda t: t.pnl)
        lines.append(f"Completed round-trips: {len(trips)}.")
        lines.append(
            f"Best round-trip: bought {best.buy_date} at ${best.buy_price:.2f}, sold {best.sell_date} "
            f"at ${best.sell_price:.2f}, result {money(best.pnl)} ({best.return_pct:.2f}%)."
        )
        if len(trips) > 1:
            lines.append(
                f"Worst round-trip: bought {worst.buy_date} at ${worst.buy_price:.2f}, sold {worst.sell_date} "
                f"at ${worst.sell_price:.2f}, result {money(worst.pnl)} ({worst.return_pct:.2f}%)."
            )

    if trades[-1]["type"] == "BUY":
        lines.append(f"A position opened on {trades[-1]['date']} was still open when the simulation ended.")
    return "\n".join(lines)


def drawdown_text(equity: list[dict], initial_capital: float) -> str:
    if not equity:
        return "No equity curve was recorded for this simulation."

    final_value = float(equity[-1]["portfolio_value"])
    total_return = (final_value / initial_capital - 1) * 100 if initial_capital else 0.0

    peak_value, peak_date = float(equity[0]["portfolio_value"]), str(equity[0]["date"])
    max_dd, dd_peak_date, dd_trough_date = 0.0, None, None
    for row in equity:
        value = float(row["portfolio_value"])
        if value > peak_value:
            peak_value, peak_date = value, str(row["date"])
        if peak_value > 0:
            dd = (peak_value - value) / peak_value * 100
            if dd > max_dd:
                max_dd, dd_peak_date, dd_trough_date = dd, peak_date, str(row["date"])

    highest = max(equity, key=lambda r: float(r["portfolio_value"]))
    lines = [
        f"Initial capital: ${initial_capital:.2f}. Final portfolio value: ${final_value:.2f} "
        f"on {equity[-1]['date']}. Total return: {total_return:.2f}%.",
        f"Highest portfolio value: ${float(highest['portfolio_value']):.2f} on {highest['date']}.",
    ]
    if max_dd > 0:
        lines.append(
            f"Largest drawdown: {max_dd:.2f}%, from the peak on {dd_peak_date} to the low on {dd_trough_date}."
        )
    else:
        lines.append("The portfolio never fell below a previous peak (no drawdown).")
    return "\n".join(lines)


def buy_and_hold_text(prices: list[dict], initial_capital: float, final_value: float | None) -> str:
    """Simple buy & hold over the same days the simulation processed."""
    if len(prices) < 2 or not prices[0]["price"]:
        return "Not enough price data to compare with buy & hold."

    first, last = prices[0], prices[-1]
    bh_return = (float(last["price"]) / float(first["price"]) - 1) * 100
    lines = [
        f"Buy & hold: buying on {first['date']} at ${float(first['price']):.2f} and holding until "
        f"{last['date']} at ${float(last['price']):.2f} would have returned {bh_return:.2f}%."
    ]
    if final_value is not None and initial_capital:
        strategy_return = (final_value / initial_capital - 1) * 100
        difference = strategy_return - bh_return
        verdict = "beat" if difference > 0 else "did not beat"
        lines.append(
            f"The strategy returned {strategy_return:.2f}%, so it {verdict} buy & hold "
            f"by {abs(difference):.2f} percentage points."
        )
    return "\n".join(lines)


def run_summary_text(status: str, stop_reason: str | None, strategies: list[str], asset: str,
                     start_date: str, end_date: str) -> str:
    lines = [
        f"Asset: {asset}. Period: {start_date} to {end_date}. Strategies: {', '.join(strategies) or 'n/a'}.",
    ]
    if status == "STOPPED_BY_RISK":
        lines.append(f"The run was stopped early by the risk manager: {stop_reason or 'no reason recorded'}.")
    else:
        lines.append("The run completed the full period.")
    return "\n".join(lines)
