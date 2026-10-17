# Trading glossary — Market Navigator AI

## Backtest
A backtest simulates how a trading strategy would have behaved on past market data. It uses only historical prices and never real money. A good backtest only uses information that was available on each simulated day.

## Look-ahead bias
Look-ahead bias happens when a simulation uses information that was not yet available at the time of the decision, for example using tomorrow's closing price to decide today's trade. It makes results look better than they could have been in reality.

## Simple moving average (SMA)
The simple moving average is the average closing price over the last N days. A short average (for example 20 days) reacts quickly and a long average (for example 50 days) reacts slowly. In an SMA crossover strategy, a BUY signal appears when the short average crosses above the long average, and a SELL signal when it crosses below.

## Relative Strength Index (RSI)
The RSI is a momentum indicator between 0 and 100 that compares recent gains with recent losses, usually over 14 days. A value above 70 is traditionally read as overbought, meaning the price may have risen too fast. A value below 30 is read as oversold, meaning the price may have fallen too fast.

## Bollinger Bands
Bollinger Bands draw two lines around a moving average, usually two standard deviations above and below it. When the price touches the lower band the asset may be oversold, and when it touches the upper band it may be overbought. Narrow bands mean low volatility and wide bands mean high volatility.

## Momentum
Momentum measures how much the price has changed over a given period. Positive momentum means the price is rising compared with N days ago, and negative momentum means it is falling. Momentum strategies assume that recent trends tend to continue.

## Stop-loss
A stop-loss is a risk rule that closes a position automatically when its loss reaches a chosen percentage. For example, a 5% stop-loss sells the position if the price falls 5% below the purchase price. It limits the loss of a single trade.

## Position size
Position size is the share of the capital that is allowed to be invested in a single trade. A maximum position size of 20% means no more than one fifth of the capital can be in one position. It prevents putting too much money on one decision.

## Maximum drawdown
Drawdown is the drop from a peak in portfolio value to a later low. The maximum drawdown is the largest such drop during the whole simulation, shown as a percentage. If the portfolio goes from 100,000 to 80,000, the drawdown is 20%. In this platform, a simulation stops when the configured maximum drawdown is reached.

## Total return
Total return is the percentage change between the initial capital and the final capital. If 10,000 becomes 11,500 the total return is 15%.

## Sharpe ratio
The Sharpe ratio measures return per unit of risk. It is the average excess return divided by the standard deviation of returns. A higher value means a better return for the volatility taken. A value above 1 is usually considered good and a negative value means the strategy did worse than a risk-free investment.

## Win rate
The win rate is the percentage of closed trades that ended with a profit. A win rate of 60% means 6 out of every 10 trades made money. It says nothing about how large the wins and losses were.

## Profit factor
The profit factor is the sum of all winning trades divided by the sum of all losing trades, in absolute value. A profit factor above 1 means the strategy made more than it lost, and a value below 1 means it lost money overall.

## Buy and hold
Buy and hold is a benchmark: buy the asset on the first day and keep it until the last day without trading. A strategy is only useful if it performs better than buy and hold after considering its risk.

## Market regime
A market regime is the general state of the market in a period, such as high volatility, trending or range-bound. The platform labels regimes only as context for the student; the regime label is never used by a strategy to decide a trade.

## Walk-forward
Walk-forward testing recalculates a model at fixed checkpoints using only the data available before each checkpoint. It avoids look-ahead bias because every label or decision uses only past information.

## Paper trading
Paper trading means practicing trades with virtual money. This platform is educational: it never executes real orders.
