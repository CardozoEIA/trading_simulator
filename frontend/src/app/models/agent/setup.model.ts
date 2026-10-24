export interface SetupProposal {
  asset: string | null;
  start_date: string | null;
  end_date: string | null;
  initial_capital: number | null;
  strategies: string[] | null;
  stop_loss_percentage: number | null;
  max_position_size: number | null;
  max_drawdown: number | null;
}

export interface SetupParseResponse {
  status: 'complete' | 'incomplete';
  proposal: SetupProposal;
  missing_fields: string[];
  message: string;
}

/** sessionStorage key used to hand the risk limits of a described setup over to the risk step. */
export const PENDING_SETUP_RISK_KEY = 'pending_setup_risk';
