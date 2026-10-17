export interface KnowledgeSource {
  document_id: string;
  filename: string;
  page: number | null;
  chunk_index: number;
  similarity: number;
  snippet: string;
}

export interface KnowledgeAnswer {
  answer: string;
  /** true when the knowledge base did not have enough information and the agent said so. */
  refused: boolean;
  sources: KnowledgeSource[];
}

export interface KnowledgeHistoryMessage {
  role: 'user' | 'assistant';
  content: string;
  refused: boolean;
  sources: KnowledgeSource[];
}

export interface KnowledgeHistory {
  messages: KnowledgeHistoryMessage[];
}
