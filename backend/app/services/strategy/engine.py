from app.services.strategy.schema import Decision, DecisionAction

BUY_THRESHOLD = 0.3
SELL_THRESHOLD = -0.3


def _combine_signals(signals: list) -> tuple:
    """Averages the scores of all provided StrategySignals and applies thresholds
    to produce a single combined direction. Returns (direction, combined_score, reasons)."""
    average_score = sum(s.score for s in signals) / len(signals)
    reasons = "; ".join(f"{type(s).__name__ if False else s.reasoning}" for s in signals)

    if average_score > BUY_THRESHOLD:
        direction = DecisionAction.BUY
    elif average_score < SELL_THRESHOLD:
        direction = DecisionAction.SELL
    else:
        direction = DecisionAction.HOLD

    return direction, average_score, reasons


def run_strategy(candles: list, strategy_functions: list) -> list:
    """strategy_functions is a list of evaluate() functions (one per selected strategy).
    For each candle, every strategy is evaluated and the resulting signals are combined
    into a single Decision."""
    decisions = []

    for index in range(len(candles)):
        signals = [fn(candles, index) for fn in strategy_functions]
        direction, score, reasons = _combine_signals(signals)

        decisions.append(
            Decision(
                date=candles[index].date,
                action=direction,
                reason=f"Combined score={score:.3f} from [{reasons}]"
            )
        )

    return decisions