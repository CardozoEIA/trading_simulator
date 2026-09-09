from app.services.strategy.schema import Decision, DecisionAction

SHORT_PERIOD = 5
LONG_PERIOD = 20


def _calculate_sma(candles: list, current_index: int, period: int) -> float | None:
    if current_index + 1 < period:
        return None
    candle_list = candles[current_index - period + 1 : current_index + 1]
    close_values = [c.close for c in candle_list]
    return sum(close_values) / len(close_values)


def evaluate(candles: list, current_index: int) -> Decision:
    today_date = candles[current_index].date

    if current_index == 0:
        return Decision(date=today_date, action=DecisionAction.HOLD, reason="Not enough data yet")

    short_today = _calculate_sma(candles=candles, current_index=current_index, period=SHORT_PERIOD)
    long_today = _calculate_sma(candles=candles, current_index=current_index, period=LONG_PERIOD)
    short_yesterday = _calculate_sma(candles=candles, current_index=current_index - 1, period=SHORT_PERIOD)
    long_yesterday = _calculate_sma(candles=candles, current_index=current_index - 1, period=LONG_PERIOD)

    if any(value is None for value in [short_today, long_today, short_yesterday, long_yesterday]):
        return Decision(date=today_date, action=DecisionAction.HOLD, reason="Not enough data yet")

    if short_yesterday <= long_yesterday and short_today > long_today:
        return Decision(date=today_date, action=DecisionAction.BUY, reason="Short SMA crossed above long SMA")

    if short_yesterday >= long_yesterday and short_today < long_today:
        return Decision(date=today_date, action=DecisionAction.SELL, reason="Short SMA crossed below long SMA")

    return Decision(date=today_date, action=DecisionAction.HOLD, reason="No crossover detected")