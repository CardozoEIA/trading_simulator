import { ProposedChange } from './chat.model';
import { SimulationComparison } from './compare.model';

export type RiskParameter = 'stop_loss_percentage' | 'max_position_size' | 'max_drawdown';

export interface WhatIfResult {
  status: 'COMPLETED' | 'FALLBACK';
  original_id: string;
  what_if_id: string | null;
  change: ProposedChange;
  comparison: SimulationComparison | null;
  fallback: string | null;
  message: string;
}
