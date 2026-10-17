"""Short, beginner-friendly definitions the conceptual agent is allowed to use.

Keeping them in code (instead of trusting the model's memory) grounds the answers.
"""

GLOSSARY: dict[str, str] = {
    "RSI": (
        "Relative Strength Index. A momentum indicator from 0 to 100 that compares recent "
        "gains with recent losses. Above 70 is traditionally read as overbought, below 30 as "
        "oversold, and anything in between as neutral."
    ),
    "SMA": (
        "Simple Moving Average: the average closing price over the last N days. A short SMA "
        "reacts quickly and a long SMA reacts slowly. When the short SMA is above the long SMA "
        "the trend is read as up; below it, as down. A crossover can trigger a signal."
    ),
    "Bollinger Bands": (
        "A band drawn around a moving average, usually two standard deviations above and below. "
        "A price near the lower band is read as unusually low, near the upper band as unusually "
        "high. The bands widen when volatility rises."
    ),
    "Momentum": (
        "How much the price changed over a recent window. Positive momentum means the price has "
        "been rising, negative momentum means it has been falling."
    ),
    "Stop-loss": (
        "A risk limit. If an open position loses the chosen percentage from its entry price, it "
        "is closed automatically to cap the loss."
    ),
    "Max position size": (
        "A risk limit: the largest share of your capital that can go into a single trade."
    ),
    "Max drawdown": (
        "The largest drop from a peak in portfolio value to a later low. As a risk limit, the "
        "simulation stops itself when the loss reaches the chosen percentage."
    ),
    "Sharpe ratio": (
        "Return per unit of risk. A higher value means the strategy earned more for the "
        "volatility it took on."
    ),
    "Win rate": "The share of closed trades that made a profit.",
    "Profit factor": (
        "Total profit from winning trades divided by total loss from losing trades. Above 1 "
        "means the strategy made more than it lost."
    ),
    "Buy & hold": (
        "A benchmark: buy at the start of the period and hold until the end without trading. "
        "It shows whether the strategy's activity added value."
    ),
    "Backtest": (
        "Running a strategy on past prices to see how it would have performed. Past results do "
        "not guarantee future results."
    ),
}