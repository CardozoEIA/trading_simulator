// src/app/models/decision.model.ts
export interface Decision {
  id: string;
  simulation_id: string;
  date: string;
  price: number;
  action: 'BUY' | 'SELL' | 'HOLD';
  reason: string;
  executed: boolean;
}