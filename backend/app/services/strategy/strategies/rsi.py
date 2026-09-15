from app.services.strategy.schema import DecisionAction, StrategySignal

RSI_PERIOD = 14
OVERBOUGHT = 70
OVERSOLD = 30


def _calculate_rsi(candles: list, current_index: int, period: int) -> float | None:
    if current_index + 1 < period + 1:
        return None

    window = candles[current_index - period : current_index + 1]
    gains = []
    losses = []

    for i in range(1, len(window)):
        change = window[i].close - window[i - 1].close
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def evaluate(candles: list, current_index: int) -> StrategySignal:
    rsi = _calculate_rsi(candles=candles, current_index=current_index, period=RSI_PERIOD)

    if rsi is None:
        return StrategySignal(direction=DecisionAction.HOLD, score=0.0, reasoning="Not enough data yet")

    # Score formula: distance from the neutral midpoint (50), normalized to [-1, 1].
    # RSI near 0 (oversold) -> score near +1 (BUY). RSI near 100 (overbought) -> score near -1 (SELL).
    score = (50 - rsi) / 50

    if rsi < OVERSOLD:
        return StrategySignal(direction=DecisionAction.BUY, score=score, reasoning=f"RSI={rsi:.2f} indicates oversold conditions")

    if rsi > OVERBOUGHT:
        return StrategySignal(direction=DecisionAction.SELL, score=score, reasoning=f"RSI={rsi:.2f} indicates overbought conditions")

    return StrategySignal(direction=DecisionAction.HOLD, score=score, reasoning=f"RSI={rsi:.2f} is within normal range")