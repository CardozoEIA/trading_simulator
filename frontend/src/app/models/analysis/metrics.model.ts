export interface SimulationMetrics {
  simulation_id: string;
  total_return_pct: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  win_rate: number;
  profit_factor: number | null;
  total_trades: number;
  winning_trades: number;
}