export interface ProposedChange {
  parameter: string;
  label: string;
  current: number | null;
  suggested: number;
  plan: string[];
}

export interface ChatResponse {
  reply: string;
  route: string | null;
  date: string | null;
  suggestions: string[];
  proposed_change: ProposedChange | null;
}

export interface ChatHistoryMessage {
  role: 'user' | 'assistant';
  content: string;
  route: string | null;
  date: string | null;
}

export interface ChatHistory {
  messages: ChatHistoryMessage[];
  suggestions: string[];
}

export type ChatStreamEvent =
  | { type: 'token'; text: string }
  | { type: 'done'; response: ChatResponse }
  | { type: 'error'; detail: string };

/** sessionStorage key used to hand a confirmed suggestion over to the risk step of the setup. */
export const PENDING_RISK_CHANGE_KEY = 'pending_risk_change';