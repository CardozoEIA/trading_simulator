from app.services.strategy.schema import Decision, DecisionAction

BUY_THRESHOLD = 0.1
SELL_THRESHOLD = -0.1


def _combine_signals(signals: list) -> tuple:
    """Averages the scores of all provided StrategySignals and applies thresholds
    to produce a single combined direction. Returns (raw_direction, combined_score, reasons)."""
    average_score = sum(s.score for s in signals) / len(signals)
    reasons = "; ".join(s.reasoning for s in signals)

    if average_score > BUY_THRESHOLD:
        raw_direction = DecisionAction.BUY
    elif average_score < SELL_THRESHOLD:
        raw_direction = DecisionAction.SELL
    else:
        raw_direction = DecisionAction.HOLD

    return raw_direction, average_score, reasons


def run_strategy(candles: list, strategy_functions: list) -> list:
    """strategy_functions is a list of evaluate() functions (one per selected strategy).
    For each candle, every strategy is evaluated and the resulting signals are combined
    into a single Decision.

    Signals are de-duplicated: a BUY/SELL is only emitted when the combined signal
    ENTERS that zone (crosses the threshold), not every day the score stays there.
    While the score remains in the same zone, the decision is HOLD. This avoids
    emitting repeated BUYs that the portfolio can't execute once fully invested,
    and keeps the recorded reason meaningful (a BUY marks a genuine new entry signal)."""
    decisions = []
    last_actionable = None  # last non-HOLD direction actually emitted

    for index in range(len(candles)):
        signals = [fn(candles, index) for fn in strategy_functions]
        raw_direction, score, reasons = _combine_signals(signals)

        # Only act when the actionable direction changes; otherwise HOLD.
        if raw_direction != DecisionAction.HOLD and raw_direction != last_actionable:
            action = raw_direction
            last_actionable = raw_direction
            reason = f"Combined score={score:.3f} crossed {action.value} threshold [{reasons}]"
        else:
            action = DecisionAction.HOLD
            if raw_direction == DecisionAction.HOLD:
                reason = f"Combined score={score:.3f} within neutral zone [{reasons}]"
            else:
                reason = f"Combined score={score:.3f} still in {raw_direction.value} zone — no new signal [{reasons}]"

        decisions.append(
            Decision(date=candles[index].date, action=action, reason=reason)
        )

    return decisions