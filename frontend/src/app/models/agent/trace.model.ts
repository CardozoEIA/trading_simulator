/** US-31: one tool the agent called, with the arguments it used and the value the tool returned. */
export interface ToolCallTrace {
  tool: string;
  arguments: Record<string, unknown>;
  result: string | null;
}

export interface RemovedStatement {
  statement: string;
  problems: string[];
}

/** What the agent's self-check found before showing the answer. */
export interface Verification {
  verified: boolean;
  tools_called: number;
  removed: RemovedStatement[];
}

export interface ExplainResponse {
  explanation: string;
  trace: ToolCallTrace[];
  verification: Verification | null;
}

export interface TraceRecord {
  id: number;
  source: 'explain' | 'chat';
  date: string | null;
  answer: string;
  tool_calls: ToolCallTrace[];
  verification: Verification | null;
  created_at: string;
}
