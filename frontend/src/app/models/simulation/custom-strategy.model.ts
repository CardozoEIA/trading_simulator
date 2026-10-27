export type BaseStrategy = 'SMA' | 'RSI' | 'BOLLINGER' | 'MOMENTUM';

export interface CustomStrategy {
  id: string;
  name: string;
  base_strategy: BaseStrategy;
  params: Record<string, number>;
  created_at: string;
  updated_at: string;
}

export interface CustomStrategyInput {
  name: string;
  base_strategy: BaseStrategy;
  params: Record<string, number>;
}

/** One editable parameter of a base strategy, with its default and allowed range. */
export interface ParameterSpec {
  name: string;
  label: string;
  description: string;
  kind: 'int' | 'float';
  default: number;
  min: number;
  max: number;
}

export type ParameterCatalog = Record<BaseStrategy, ParameterSpec[]>;
