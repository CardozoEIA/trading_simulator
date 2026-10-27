export interface Strategy {
  code: string;
  name: string;
  description: string;
  /** US-21: true for a strategy the student created (its code is CUSTOM:<id>). */
  custom?: boolean;
}
