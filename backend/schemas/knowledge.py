from datetime import datetime
from typing import Literal

from schemas.base import ApiModel


KnowledgeStatus = Literal["uploaded", "processing", "ready", "failed"]


class KnowledgeDocumentOut(ApiModel):
    id: int
    title: str
    source_name: str
    content_type: str | None
    status: KnowledgeStatus
    chunk_count: int
    error_message: str | None
    uploaded_by: int | None
    created_at: datetime
    updated_at: datetime


class KnowledgeDocumentsOut(ApiModel):
    documents: list[KnowledgeDocumentOut]


class KnowledgeUploadOut(ApiModel):
    document: KnowledgeDocumentOut