export type SimulationStatus = 'RUNNING' | 'FINISHED' | 'STOPPED_BY_RISK';

export interface SimulationResponse {
  id: string;
  configuration_id: string;
  status: SimulationStatus;
  started_at: string;
  finished_at: string | null;
}