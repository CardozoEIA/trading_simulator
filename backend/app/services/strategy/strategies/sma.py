from app.services.strategy.schema import DecisionAction, StrategySignal

SHORT_PERIOD = 5
LONG_PERIOD = 20


def _calculate_sma(candles: list, current_index: int, period: int) -> float | None:
    if current_index + 1 < period:
        return None
    candle_list = candles[current_index - period + 1 : current_index + 1]
    close_values = [c.close for c in candle_list]
    return sum(close_values) / len(close_values)


def evaluate(candles: list, current_index: int) -> StrategySignal:
    if current_index == 0:
        return StrategySignal(direction=DecisionAction.HOLD, score=0.0, reasoning="Not enough data yet")

    short_today = _calculate_sma(candles=candles, current_index=current_index, period=SHORT_PERIOD)
    long_today = _calculate_sma(candles=candles, current_index=current_index, period=LONG_PERIOD)
    short_yesterday = _calculate_sma(candles=candles, current_index=current_index - 1, period=SHORT_PERIOD)
    long_yesterday = _calculate_sma(candles=candles, current_index=current_index - 1, period=LONG_PERIOD)

    if any(value is None for value in [short_today, long_today, short_yesterday, long_yesterday]):
        return StrategySignal(direction=DecisionAction.HOLD, score=0.0, reasoning="Not enough data yet")

    # Score formula: normalized distance between the two SMAs relative to the long SMA,
    # clamped to [-1, 1]. A wider gap between short and long SMA means a stronger signal.
    gap_ratio = (short_today - long_today) / long_today
    score = max(-1.0, min(1.0, gap_ratio * 10))

    if short_yesterday <= long_yesterday and short_today > long_today:
        return StrategySignal(direction=DecisionAction.BUY, score=abs(score), reasoning=f"Short SMA crossed above long SMA (gap={gap_ratio:.4f})")

    if short_yesterday >= long_yesterday and short_today < long_today:
        return StrategySignal(direction=DecisionAction.SELL, score=-abs(score), reasoning=f"Short SMA crossed below long SMA (gap={gap_ratio:.4f})")

    return StrategySignal(direction=DecisionAction.HOLD, score=score, reasoning="No crossover detected")