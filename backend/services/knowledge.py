from sqlalchemy.orm import Session

from models import KnowledgeChunk, KnowledgeDocument, User


def create_document(
    db: Session,
    user: User,
    *,
    title: str,
    source_name: str,
    content_type: str | None,
    file_content: bytes,
) -> KnowledgeDocument:
    document = KnowledgeDocument(
        title=title,
        source_name=source_name,
        content_type=content_type,
        file_content=file_content,
        status="uploaded",
        chunk_count=0,
        uploaded_by=user.user_id,
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document


def list_documents(db: Session) -> list[KnowledgeDocument]:
    return (
        db.query(KnowledgeDocument)
        .order_by(KnowledgeDocument.created_at.desc())
        .all()
    )


def get_document(db: Session, document_id: int) -> KnowledgeDocument | None:
    return db.get(KnowledgeDocument, document_id)

def process_document(
    db: Session,
    document: KnowledgeDocument,
) -> KnowledgeDocument:
    document.status = "processing"
    document.error_message = None
    db.commit()

    try:
        content_type = (
            (document.content_type or "")
            .split(";")[0]
            .strip()
            .lower()
        )

        if content_type != "text/plain":
            raise ValueError(
                f"Unsupported content type: {document.content_type}"
            )

        text = document.file_content.decode("utf-8").strip()

        if not text:
            raise ValueError("Document contains no readable text.")

        chunk_size = 800
        overlap = 100

        chunks = []
        start = 0

        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end].strip()

            if chunk_text:
                chunks.append(chunk_text)

            if end >= len(text):
                break

            start = end - overlap

        db.query(KnowledgeChunk).filter(
            KnowledgeChunk.document_id == document.id
        ).delete()

        for index, chunk_text in enumerate(chunks):
            db.add(
                KnowledgeChunk(
                    document_id=document.id,
                    chunk_index=index,
                    content=chunk_text,
                )
            )

        document.chunk_count = len(chunks)
        document.status = "ready"

        db.commit()
        db.refresh(document)

        return document

    except Exception as exc:
        db.rollback()

        document = db.get(KnowledgeDocument, document.id)
        document.status = "failed"
        document.error_message = str(exc)

        db.commit()
        db.refresh(document)

        return document