from app.services.strategy.schema import DecisionAction, StrategySignal

MOMENTUM_PERIOD = 10
THRESHOLD = 0.02  # 2% price change over the period


def _calculate_momentum(candles: list, current_index: int, period: int) -> float | None:
    if current_index - period < 0:
        return None
    past_close = candles[current_index - period].close
    current_close = candles[current_index].close
    return (current_close - past_close) / past_close


def build_evaluate(period: int = MOMENTUM_PERIOD, threshold: float = THRESHOLD):
    """Returns an evaluate(candles, index) function with the given period and threshold (US-21).
    With the default values it behaves exactly like the built-in Momentum strategy."""

    def evaluate(candles: list, current_index: int) -> StrategySignal:
        return _evaluate(candles, current_index, period, threshold)

    return evaluate


def _evaluate(candles: list, current_index: int, period: int, threshold: float) -> StrategySignal:
    momentum = _calculate_momentum(candles=candles, current_index=current_index, period=period)

    if momentum is None:
        return StrategySignal(direction=DecisionAction.HOLD, score=0.0, reasoning="Not enough data yet")

    # Score formula: momentum ratio scaled so +/-10% price change over the period maps to +/-1.
    score = max(-1.0, min(1.0, momentum * 10))

    if momentum > threshold:
        return StrategySignal(direction=DecisionAction.BUY, score=score, reasoning=f"Price up {momentum:.2%} over {period} days")

    if momentum < -threshold:
        return StrategySignal(direction=DecisionAction.SELL, score=score, reasoning=f"Price down {momentum:.2%} over {period} days")

    return StrategySignal(direction=DecisionAction.HOLD, score=score, reasoning=f"Price change {momentum:.2%} below threshold")


evaluate = build_evaluate()
