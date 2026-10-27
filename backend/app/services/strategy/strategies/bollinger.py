import statistics

from app.services.strategy.schema import DecisionAction, StrategySignal

PERIOD = 20
NUM_STD = 2


def _calculate_bands(candles: list, current_index: int, period: int, num_std: float):
    if current_index + 1 < period:
        return None
    window = candles[current_index - period + 1 : current_index + 1]
    closes = [c.close for c in window]
    mean = sum(closes) / period
    std_dev = statistics.pstdev(closes)
    upper = mean + num_std * std_dev
    lower = mean - num_std * std_dev
    return mean, upper, lower


def build_evaluate(period: int = PERIOD, num_std: float = NUM_STD):
    """Returns an evaluate(candles, index) function with the given period and band width (US-21).
    With the default values it behaves exactly like the built-in Bollinger strategy."""

    def evaluate(candles: list, current_index: int) -> StrategySignal:
        return _evaluate(candles, current_index, period, num_std)

    return evaluate


def _evaluate(candles: list, current_index: int, period: int, num_std: float) -> StrategySignal:
    bands = _calculate_bands(candles=candles, current_index=current_index, period=period, num_std=num_std)

    if bands is None:
        return StrategySignal(direction=DecisionAction.HOLD, score=0.0, reasoning="Not enough data yet")

    _, upper, lower = bands
    price = candles[current_index].close
    band_width = upper - lower

    if band_width == 0:
        return StrategySignal(direction=DecisionAction.HOLD, score=0.0, reasoning="No volatility (flat band)")

    # Score formula: %B position within the band, inverted and centered so that
    # touching the lower band -> score +1 (BUY), touching the upper band -> score -1 (SELL).
    percent_b = (price - lower) / band_width
    score = max(-1.0, min(1.0, (0.5 - percent_b) * 2))

    if price < lower:
        return StrategySignal(direction=DecisionAction.BUY, score=score, reasoning=f"Price {price:.2f} below lower band {lower:.2f}")

    if price > upper:
        return StrategySignal(direction=DecisionAction.SELL, score=score, reasoning=f"Price {price:.2f} above upper band {upper:.2f}")

    return StrategySignal(direction=DecisionAction.HOLD, score=score, reasoning=f"Price {price:.2f} within bands [{lower:.2f}, {upper:.2f}]")


evaluate = build_evaluate()
