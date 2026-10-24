export type ReportSectionKey = 'setup' | 'performance' | 'key_decisions' | 'benchmark' | 'disclaimer';

export interface ReportRow {
  label: string;
  value: string;
}

export interface ReportTable {
  columns: string[];
  rows: string[][];
}

export interface ReportSection {
  key: ReportSectionKey;
  title: string;
  narrative: string | null;
  rows: ReportRow[];
  table: ReportTable | null;
  note: string | null;
}

export interface SimulationReport {
  simulation_id: string;
  title: string;
  generated_at: string;
  markdown: string;
  sections: ReportSection[];
}
