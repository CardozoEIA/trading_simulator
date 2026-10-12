from app.services.benchmark.schema import BuyAndHoldSummary
from app.services.historical_data.schema import Candle


def calculate_buy_and_hold(
    candles: list[Candle], initial_capital: float
) -> BuyAndHoldSummary:
    if not candles:
        raise ValueError(
            "calculate_buy_and_hold requires at least one candle; received an empty candle series."
        )
    if initial_capital <= 0:
        raise ValueError(
            f"initial_capital should be greater than 0; received {initial_capital} as value."
        )
    first_candle_close_value = candles[0].close
    if first_candle_close_value <= 0:
        raise ValueError(
            f"The close value for the first candle should be greater than 0; received {first_candle_close_value} as value"
        )
    units = initial_capital / first_candle_close_value
    final_capital = units * candles[-1].close
    profit_loss = final_capital - initial_capital
    total_return_pct = (profit_loss / initial_capital) * 100

    return BuyAndHoldSummary(
        initial_capital=initial_capital,
        final_capital=final_capital,
        profit_loss=profit_loss,
        total_return_pct=total_return_pct,
    )
