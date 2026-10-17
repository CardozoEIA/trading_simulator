export const HELP_TEXTS = {
  initialCapital:
    'The simulated money you start with. No real money is ever used.',
  strategies:
    'Each strategy turns price data into buy or sell signals. If you pick several, their signals are combined into one decision, so they can reinforce or cancel each other.',
  stopLoss:
    'If a position loses this percentage from its entry price, it is sold automatically. Example: with 5%, something bought at $100 is sold if the price falls to $95. Lower values cut losses sooner but can sell on small dips.',
  maxPositionSize:
    'The largest share of your capital that one trade can use. Example: with 50% and $10,000, no single purchase will be bigger than $5,000. Smaller values spread the risk.',
  maxDrawdown:
    'How far your whole portfolio can fall from its highest value before the simulation stops itself. Example: with 20%, a portfolio that peaked at $10,000 stops if it drops to $8,000.',
  drawdownResult:
    'The biggest fall of your portfolio from a peak to a later low during this run. It shows how painful the worst stretch was.',
  sharpeRatio:
    'Return earned per unit of risk. Higher is better. A strategy with big gains but wild swings can still score low.',
  winRate:
    'The share of closed trades that made a profit. A high win rate does not guarantee a profit if the losing trades are larger than the winning ones.',
  profitFactor:
    'Total profit from winning trades divided by total loss from losing trades. Above 1 means the strategy earned more than it lost.',
} as const;

export type HelpTopic = keyof typeof HELP_TEXTS;