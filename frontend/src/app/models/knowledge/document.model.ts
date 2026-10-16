export type DocumentStatus = 'processing' | 'ready' | 'failed';

export interface KnowledgeDocument {
  id: string;
  filename: string;
  file_type: string;
  size_bytes: number;
  status: DocumentStatus;
  chunk_count: number;
  error: string | null;
  created_at: string;
}

/** Same rules as the backend (app/modules/documents/ingestion/extractors.py). */
export const ALLOWED_EXTENSIONS = ['pdf', 'txt', 'md', 'csv', 'docx'];
export const MAX_FILE_BYTES = 10 * 1024 * 1024;
