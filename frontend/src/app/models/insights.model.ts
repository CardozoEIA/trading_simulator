export type InsightsStatus = 'NOT_GENERATED' | 'PENDING' | 'READY' | 'FAILED';

export interface Insight {
  title: string;
  detail: string;
}

export interface SimulationInsights {
  simulation_id: string;
  status: InsightsStatus;
  insights: Insight[];
  error: string | null;
  generated_at: string | null;
}
