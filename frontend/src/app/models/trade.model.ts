// src/app/models/trade.model.ts
export interface Trade {
  id: string;
  simulation_id: string;
  date: string;
  type: 'BUY' | 'SELL';
  price: number;
  quantity: number;
  cash_after: number;
  shares_after: number;
  portfolio_value_after: number;
}