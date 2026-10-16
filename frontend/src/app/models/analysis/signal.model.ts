// src/app/models/signal.model.ts
export interface Signal {
  date: string;
  sma_short: number | null;
  sma_long: number | null;
  rsi: number | null;
  bollinger_upper: number | null;
  bollinger_lower: number | null;
  momentum: number | null;
}