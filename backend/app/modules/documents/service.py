"""Document ingestion use case: validate -> extract -> chunk -> embed -> store -> confirm."""
import logging

from fastapi import HTTPException, status

from app.modules.documents.ingestion.chunking import chunk_sections
from app.modules.documents.ingestion.extractors import (
    EmptyDocumentError,
    UnsupportedFileError,
    extract,
    safe_filename,
    validate_upload,
)
from app.vectorstore import repository
from app.vectorstore.embeddings import embed_documents

logger = logging.getLogger(__name__)


def ingest_document(user_id: str, filename: str, data: bytes) -> dict:
    """Run the whole pipeline and return the stored document (status 'ready').

    The row is created first with status 'processing', so a crash in the middle leaves a visible
    'failed' document the user can delete, instead of a half-indexed file nobody knows about.
    """
    try:
        file_type = validate_upload(filename, len(data))
    except UnsupportedFileError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error))

    document = repository.create_document(user_id, safe_filename(filename), file_type, len(data))

    try:
        sections = extract(file_type, data)
        chunks = chunk_sections(sections)
        vectors = embed_documents([chunk.content for chunk in chunks])

        repository.insert_chunks(
            document["id"],
            user_id,
            [
                {"chunk_index": c.index, "content": c.content, "page": c.page, "embedding": v}
                for c, v in zip(chunks, vectors)
            ],
        )
        repository.set_document_status(document["id"], "ready", chunk_count=len(chunks))
    except EmptyDocumentError as error:
        repository.set_document_status(document["id"], "failed", error=str(error))
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error))
    except Exception as error:
        logger.exception("Could not process document %s", document["id"])
        repository.set_document_status(document["id"], "failed", error=str(error)[:300])
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The document could not be processed. Is the embedding model running?",
        )

    return {**document, "status": "ready", "chunk_count": len(chunks)}


def list_user_documents(user_id: str) -> list[dict]:
    return repository.list_documents(user_id)


def remove_document(user_id: str, document_id: str) -> None:
    if not repository.delete_document(user_id, document_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
