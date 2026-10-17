# app/agents/insights/facts.py
"""Pure calculations behind the proactive highlights (US-26).

`compute_highlights` decides *what* is worth pointing out in a finished simulation
(deterministic, always available). Each highlight carries the fact sentences the
agent is allowed to use; the verification step only accepts numbers and dates that
appear in those sentences.
"""
from dataclasses import dataclass


def money(value: float) -> str:
    return f"-${abs(value):,.2f}" if value < 0 else f"${value:,.2f}"


def signed_money(value: float) -> str:
    return f"+{money(value)}" if value > 0 else money(value)


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

    def describe(self) -> str:
        return (
            f"Bought on {self.buy_date} at ${self.buy_price:.2f} and sold on {self.sell_date} "
            f"at ${self.sell_price:.2f}: result {money(self.pnl)} ({self.return_pct:.2f}%)."
        )


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


@dataclass
class Drawdown:
    pct: float
    peak_date: str
    peak_value: float
    trough_date: str
    trough_value: float


def largest_drawdown(equity: list[dict]) -> Drawdown | None:
    if not equity:
        return None
    peak_value, peak_date = float(equity[0]["portfolio_value"]), str(equity[0]["date"])
    best: Drawdown | None = None
    for row in equity:
        value = float(row["portfolio_value"])
        if value > peak_value:
            peak_value, peak_date = value, str(row["date"])
        if peak_value > 0:
            pct = (peak_value - value) / peak_value * 100
            if pct > 0 and (best is None or pct > best.pct):
                best = Drawdown(pct, peak_date, peak_value, str(row["date"]), value)
    return best


def overview_text(run: dict, equity: list[dict]) -> str:
    """General context shared by every highlight."""
    initial = float(run["initial_capital"])
    lines = [
        f"Asset: {run['asset']}. Period: {run['start_date']} to {run['end_date']}. "
        f"Strategies: {', '.join(run.get('strategies') or []) or 'n/a'}.",
    ]
    if equity:
        final = float(equity[-1]["portfolio_value"])
        lines.append(
            f"Initial capital: ${initial:.2f}. Final portfolio value: ${final:.2f} on {equity[-1]['date']}. "
            f"Total return: {(final / initial - 1) * 100 if initial else 0:.2f}%."
        )
    return "\n".join(lines)


def compute_highlights(run: dict, trades: list[dict], equity: list[dict], prices: list[dict]) -> list[dict]:
    """Returns the notable points of a run, each with the facts that back it."""
    highlights: list[dict] = []
    initial = float(run["initial_capital"])
    final = float(equity[-1]["portfolio_value"]) if equity else None

    # Strategy vs. buy & hold over the same processed days
    if final is not None and initial and len(prices) >= 2 and prices[0]["price"]:
        first, last = prices[0], prices[-1]
        bh_return = (float(last["price"]) / float(first["price"]) - 1) * 100
        strategy_return = (final / initial - 1) * 100
        diff = strategy_return - bh_return
        beat = diff > 0
        highlights.append({
            "kind": "BUY_AND_HOLD",
            "label": f"{'Beat' if beat else 'Trailed'} buy & hold by {abs(diff):.2f} pts",
            "tone": "positive" if beat else "negative",
            "dates": [],
            "facts": (
                f"The strategy returned {strategy_return:.2f}%. Buying on {first['date']} at "
                f"${float(first['price']):.2f} and holding until {last['date']} at ${float(last['price']):.2f} "
                f"would have returned {bh_return:.2f}%. The strategy {'beat' if beat else 'did not beat'} "
                f"buy & hold by {abs(diff):.2f} percentage points."
            ),
        })

    # Early stop by the risk manager
    if run.get("status") == "STOPPED_BY_RISK":
        last_day = str(equity[-1]["date"]) if equity else None
        highlights.append({
            "kind": "RISK_STOP",
            "label": "Stopped early by risk",
            "tone": "negative",
            "dates": [last_day] if last_day else [],
            "facts": (
                f"The risk manager stopped the run before {run['end_date']}"
                + (f", on {last_day}" if last_day else "")
                + f". Reason recorded: {run.get('stop_reason') or 'not recorded'}."
            ),
        })

    # Best and worst completed trades
    trips = round_trips(trades)
    if trips:
        best = max(trips, key=lambda t: t.pnl)
        highlights.append({
            "kind": "BEST_TRADE",
            "label": f"Best trade {signed_money(best.pnl)}",
            "tone": "positive" if best.pnl > 0 else "neutral",
            "dates": [best.buy_date, best.sell_date],
            "facts": f"Best completed trade out of {len(trips)}: {best.describe()}",
        })
        worst = min(trips, key=lambda t: t.pnl)
        if len(trips) > 1 and worst.pnl < 0:
            highlights.append({
                "kind": "WORST_TRADE",
                "label": f"Worst trade {money(worst.pnl)}",
                "tone": "negative",
                "dates": [worst.buy_date, worst.sell_date],
                "facts": f"Worst completed trade out of {len(trips)}: {worst.describe()}",
            })

    # Largest peak-to-trough drop of the portfolio
    dd = largest_drawdown(equity)
    if dd is not None:
        highlights.append({
            "kind": "MAX_DRAWDOWN",
            "label": f"Largest drop -{dd.pct:.2f}%",
            "tone": "negative",
            "dates": [dd.peak_date, dd.trough_date],
            "facts": (
                f"The largest drop of the portfolio was {dd.pct:.2f}%: from a peak of ${dd.peak_value:.2f} "
                f"on {dd.peak_date} to a low of ${dd.trough_value:.2f} on {dd.trough_date}."
            ),
        })

    return highlights
