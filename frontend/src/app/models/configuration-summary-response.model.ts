export interface RiskSummary {
  stop_loss_percentage: number;
  max_position_size: number;
  max_drawdown: number;
}

export interface ConfigurationSummaryResponse {
  id: string;
  asset: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  strategy: string;
  risk: RiskSummary;
}