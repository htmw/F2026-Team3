import os

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from database import get_db
from models import KnowledgeChunk, KnowledgeDocument
from routers.admin_knowledge import admin_only, router


TEST_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://acadmate:acadmate123@localhost:5433/acadmate_risk_integration",
)


def build_test_app():
    engine = create_engine(TEST_DATABASE_URL)

    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        db = SessionLocal()

        try:
            yield db
        finally:
            db.close()

    class FakeAdmin:
        user_id = 3

    def override_admin():
        return FakeAdmin()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[admin_only] = override_admin

    return app, engine, SessionLocal


def test_admin_knowledge_upload_process_list_and_get():
    app, engine, SessionLocal = build_test_app()

    document_id = None

    try:
        with TestClient(app) as client:
            payload = (
                b"Graduate students must complete all required core courses "
                b"before graduation.\n\n"
                b"Students must maintain satisfactory academic progress.\n\n"
                b"Course substitutions require advisor approval."
            )

            response = client.post(
                "/api/v1/admin/knowledge",
                content=payload,
                headers={
                    "x-filename": "pytest-graduate-policy.txt",
                    "x-title": "Pytest Graduate Policy",
                    "x-content-type": "text/plain",
                    "Content-Type": "application/octet-stream",
                },
            )

            assert response.status_code == 201, response.text

            body = response.json()
            document = body["document"]

            assert document["status"] == "ready"
            assert document["chunkCount"] > 0
            assert document["errorMessage"] is None

            document_id = document["id"]

            list_response = client.get(
                "/api/v1/admin/knowledge"
            )

            assert list_response.status_code == 200

            documents = list_response.json()["documents"]

            assert any(
                item["id"] == document_id
                for item in documents
            )

            get_response = client.get(
                f"/api/v1/admin/knowledge/{document_id}"
            )

            assert get_response.status_code == 200

            fetched = get_response.json()

            assert fetched["id"] == document_id
            assert fetched["status"] == "ready"
            assert fetched["chunkCount"] > 0

        with SessionLocal() as db:
            chunks = db.scalars(
                select(KnowledgeChunk).where(
                    KnowledgeChunk.document_id == document_id
                )
            ).all()

            assert len(chunks) > 0
            assert chunks[0].chunk_index == 0
            assert "Graduate students" in chunks[0].content

    finally:
        if document_id is not None:
            with SessionLocal() as db:
                db.query(KnowledgeChunk).filter(
                    KnowledgeChunk.document_id == document_id
                ).delete()

                db.query(KnowledgeDocument).filter(
                    KnowledgeDocument.id == document_id
                ).delete()

                db.commit()