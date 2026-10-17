from fastapi import APIRouter, Depends, File, UploadFile

from app.core.dependencies import get_current_user
from app.modules.documents.schema import DocumentOut
from app.modules.documents.service import (
    ingest_document,
    list_user_documents,
    remove_document,
)
from app.modules.documents.ingestion.extractors import MAX_FILE_BYTES

router = APIRouter(prefix="/documents", tags=["Documents"])


# Why plain `def` and not `async def`: ingest_document is blocking (embeddings take seconds).
# FastAPI runs plain `def` routes in a thread pool, so one upload does not freeze the whole server.


@router.post("", response_model=DocumentOut, status_code=201)
def upload_document(
    file: UploadFile = File(...), current_user=Depends(get_current_user)
):
    # TODO(Lucas):
    #   1. data = file.file.read(MAX_FILE_BYTES + 1)   (one byte more than allowed, so that
    #      validate_upload can reject an oversized file without loading all of it)
    #   2. return ingest_document(current_user.id, file.filename, data)
    data = file.file.read(MAX_FILE_BYTES + 1)

    return ingest_document(
        current_user.id,
        file.filename,
        data,
    )


@router.get("", response_model=list[DocumentOut])
def get_documents(current_user=Depends(get_current_user)):
    # TODO(Lucas): return list_user_documents(current_user.id)
    return list_user_documents(
    current_user.id
)


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: str, current_user=Depends(get_current_user)):
    # TODO(Lucas): remove_document(current_user.id, document_id)  (a 204 returns no body)
    remove_document(
    current_user.id,
    document_id,
)
