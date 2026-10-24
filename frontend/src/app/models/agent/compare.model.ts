export type CompareSide = 'a' | 'b' | 'tie';

export interface ComparedSimulation {
  id: string;
  label: string;
  status: string;
  started_at: string | null;
}

export interface ConfigurationDifference {
  field: string;
  label: string;
  a: string;
  b: string;
  changed: boolean;
}

export interface MetricDifference {
  metric: string;
  label: string;
  a: number | null;
  b: number | null;
  delta: number | null;
  a_display: string;
  b_display: string;
  delta_display: string;
  better: CompareSide | null;
}

export interface SimulationComparison {
  simulation_a: ComparedSimulation;
  simulation_b: ComparedSimulation;
  configuration_diff: ConfigurationDifference[];
  metrics_diff: MetricDifference[];
  winner: CompareSide;
  explanation: string | null;
}
