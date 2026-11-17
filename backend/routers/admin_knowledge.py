from fastapi import APIRouter, Body, Depends, Header, status
from sqlalchemy.orm import Session

from core.deps import require_role
from core.errors import bad_request, not_found
from database import get_db
from models import User
from schemas.knowledge import (
    KnowledgeDocumentOut,
    KnowledgeDocumentsOut,
    KnowledgeUploadOut,
)
from services import knowledge

router = APIRouter(
    prefix="/api/v1/admin/knowledge",
    tags=["Admin Knowledge"],
)

admin_only = require_role("admin")

MAX_KNOWLEDGE_BYTES = 5 * 1024 * 1024


@router.post(
    "",
    response_model=KnowledgeUploadOut,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    body: bytes = Body(..., media_type="application/octet-stream"),
    x_filename: str | None = Header(None, max_length=255),
    x_title: str | None = Header(None, max_length=200),
    x_content_type: str | None = Header(None, max_length=100),
    user: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    if not body:
        raise bad_request("The uploaded document is empty.")

    if len(body) > MAX_KNOWLEDGE_BYTES:
        raise bad_request("The document is larger than 5 MB.")

    source_name = (x_filename or "uploaded-document").strip()
    title = (x_title or source_name).strip()

    document = knowledge.create_document(
        db,
        user,
        title=title,
        source_name=source_name,
        content_type=x_content_type,
        file_content=body,
    )

    document = knowledge.process_document(db, document)

    return {"document": document}


@router.get(
    "",
    response_model=KnowledgeDocumentsOut,
)
def list_knowledge_documents(
    user: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    return {"documents": knowledge.list_documents(db)}


@router.get(
    "/{document_id}",
    response_model=KnowledgeDocumentOut,
)
def get_knowledge_document(
    document_id: int,
    user: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    document = knowledge.get_document(db, document_id)

    if document is None:
        raise not_found("Knowledge document")

    return document