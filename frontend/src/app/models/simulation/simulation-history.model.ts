import { SimulationStatus } from './simulation-response.model';

export interface SimulationHistoryItem {
  id: string;
  status: SimulationStatus;
  started_at: string;
  finished_at: string | null;
  stop_reason: string | null;
  asset: string;
  start_date: string;
  end_date: string;
  strategies: string[];
  initial_capital: number;
  final_value: number | null;
  total_return_pct: number | null;
}