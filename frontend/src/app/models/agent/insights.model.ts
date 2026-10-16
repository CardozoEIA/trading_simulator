export type InsightsStatus = 'PENDING' | 'READY' | 'FAILED';
export type HighlightKind = 'BUY_AND_HOLD' | 'RISK_STOP' | 'BEST_TRADE' | 'WORST_TRADE' | 'MAX_DRAWDOWN';

export interface Highlight {
  kind: HighlightKind;
  label: string;
  tone: 'positive' | 'negative' | 'neutral';
  dates: string[];
  facts: string;
  title: string | null;
  explanation: string | null;
}

export interface SimulationInsights {
  simulation_id: string;
  status: InsightsStatus;
  highlights: Highlight[];
  error: string | null;
}
