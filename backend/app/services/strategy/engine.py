def run_strategy(candles: list, strategy_function) -> list:
    decisions = []
    for index in range(len(candles)):
        decisions.append(strategy_function(candles, index))
    return decisions
