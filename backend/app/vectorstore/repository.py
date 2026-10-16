"""Data access for documents and chunks (pgvector in Supabase).

Everything that touches the documents/document_chunks tables lives here, so the rest of the app
never writes SQL or Supabase calls for the knowledge base.

Every function receives user_id and filters by it: the backend uses the secret key (RLS is
bypassed), so ownership checks are OUR job.
"""
import logging

from app.core.supabase import supabase_admin as supabase

logger = logging.getLogger(__name__)

DOCUMENTS = "documents"
CHUNKS = "document_chunks"
INSERT_BATCH_SIZE = 100


# ---------------------------------------------------------------------------
# TODO(Lucas): fill in the five functions below. They are plain CRUD, the same pattern as
# app/modules/chat/history.py (supabase.table(...).insert/select/update/delete(...).execute()).
# ---------------------------------------------------------------------------

def create_document(user_id: str, filename: str, file_type: str, size_bytes: int) -> dict:
    """Insert a row in `documents` with status 'processing' and return the inserted row (dict)."""
    # TODO(Lucas): .insert({...}).execute().data[0]
    raise NotImplementedError


def set_document_status(document_id: str, status: str, chunk_count: int = 0, error: str | None = None) -> None:
    """Update status ('ready' | 'failed'), chunk_count and error of one document."""
    # TODO(Lucas): .update({...}).eq("id", document_id).execute()
    raise NotImplementedError


def insert_chunks(document_id: str, user_id: str, chunks: list[dict]) -> None:
    """Insert chunks. Each item has: chunk_index, content, page (or None), embedding (list[float]).

    Insert in batches of INSERT_BATCH_SIZE: one giant request can exceed PostgREST's body limit.
    """
    # TODO(Lucas): loop over slices of `chunks`, add document_id and user_id to every row, insert.
    raise NotImplementedError


def list_documents(user_id: str) -> list[dict]:
    """The user's own documents, newest first (do NOT include shared ones: user_id is null)."""
    # TODO(Lucas): select id, filename, file_type, size_bytes, status, chunk_count, error, created_at
    raise NotImplementedError


def delete_document(user_id: str, document_id: str) -> bool:
    """Delete one document of this user. True if something was deleted.

    The chunks disappear by themselves: document_chunks.document_id has ON DELETE CASCADE.
    Filter by BOTH id and user_id, otherwise a user could delete someone else's document.
    """
    # TODO(Lucas): .delete().eq("id", ...).eq("user_id", ...).execute(); return bool(result.data)
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Written by Claude: this is the core of retrieval, read it carefully.
# ---------------------------------------------------------------------------

def search_chunks(query_embedding: list[float], user_id: str, threshold: float, top_k: int) -> list[dict]:
    """The `top_k` chunks closest to the question that reach `threshold`.

    Calls the SQL function match_document_chunks (see the migration). `similarity` is
    1 - cosine distance, so it goes from 0 (unrelated) to 1 (same direction). The threshold is a
    similarity: a HIGHER threshold is STRICTER. Rows come back best first, each with the
    filename, so the answer can cite its source.
    """
    result = supabase.rpc(
        "match_document_chunks",
        {
            "query_embedding": query_embedding,
            "p_user_id": user_id,
            "match_threshold": threshold,
            "match_count": top_k,
        },
    ).execute()

    return result.data or []
