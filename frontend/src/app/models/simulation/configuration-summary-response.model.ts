export interface RiskSummary {
  stop_loss_percentage: number;
  max_position_size: number;
  max_drawdown: number;
}

export interface BuyAndHoldSummary {
  initial_capital: number;
  final_capital: number;
  profit_loss: number;
  total_return_pct: number;
}

export interface ConfigurationSummaryResponse {
  id: string;
  asset: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  strategies: string[];
  risk: RiskSummary;
  benchmark: BuyAndHoldSummary;
}