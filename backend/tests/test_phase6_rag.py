import pytest
from fastapi.testclient import TestClient
from main import app
from database.session import Base, engine, get_db
from sqlalchemy.orm import sessionmaker
from database.models import Document
from rag.retrieval import rag_search, generate_citations, verify_source
from api.auth import get_current_user, UserInfo
from unittest.mock import patch, MagicMock

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    # Phase 9 added RBAC to every route — these tests exercise document
    # upload/RAG behavior, not auth, so authenticate as a permitted role.
    # Applied per-test (not at import time) since another test module's
    # `dependency_overrides.clear()` can otherwise wipe out a module-level
    # override before this file's tests actually run.
    app.dependency_overrides[get_current_user] = lambda: UserInfo(username="test-user", role="admin")
    yield
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.pop(get_current_user, None)

client = TestClient(app)

def test_upload_document():
    # Mock ingest pipeline
    with patch('api.documents.generate_embeddings', side_effect=lambda x: x), \
         patch('api.documents.store_chunks', return_value=None):
        
        response = client.post(
            "/api/documents/upload",
            files={"file": ("test.txt", b"This is a test document. It has some text.")}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test.txt"
        assert data["version"] == 1
        assert "id" in data
        
        # Test version increment
        response2 = client.post(
            "/api/documents/upload",
            files={"file": ("test.txt", b"This is a test document updated. It has some text.")}
        )
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["filename"] == "test.txt"
        assert data2["version"] == 2

def test_list_and_delete_documents():
    with patch('api.documents.generate_embeddings', side_effect=lambda x: x), \
         patch('api.documents.store_chunks', return_value=None):
        
        upload_resp = client.post(
            "/api/documents/upload",
            files={"file": ("list_test.txt", b"Test doc for listing.")}
        )
        doc_id = upload_resp.json()["id"]
        
        # List docs
        list_resp = client.get("/api/documents")
        assert list_resp.status_code == 200
        docs = list_resp.json()
        assert len(docs) > 0
        assert docs[-1]["id"] == doc_id
        
        # Delete doc
        del_resp = client.delete(f"/api/documents/{doc_id}")
        assert del_resp.status_code == 200
        
        # Verify deletion
        list_resp2 = client.get("/api/documents")
        assert len(list_resp2.json()) == len(docs) - 1

def test_retrieval_functions():
    chunks = [
        {"text": "Chunk 1", "doc_id": "123"},
        {"text": "Chunk 2", "doc_id": "456"}
    ]
    citations = generate_citations(chunks)
    assert "[1] (Doc: 123): Chunk 1" in citations
    assert "[2] (Doc: 456): Chunk 2" in citations
    
    # Test verify_source
    assert verify_source("The sky is blue", "The clear sky is indeed very blue today.") == True
    assert verify_source("Apples are tasty", "The clear sky is indeed very blue today.") == False

    with patch('rag.retrieval._search_qdrant', return_value=chunks), \
         patch('rag.retrieval._get_query_embedding', return_value=[0.0]*768):
        res = rag_search("test query")
        assert "[1] (Doc: 123): Chunk 1" in res
