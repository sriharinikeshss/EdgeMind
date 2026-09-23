import os
import uuid
import logging
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import Document
from rag.ingest import chunk_document, generate_embeddings, store_chunks
from security.rbac import require_any_role, require_operator, require_admin
from api.auth import UserInfo

logger = logging.getLogger(__name__)
router = APIRouter()

_VALID_CLASSIFICATIONS = ("public", "internal", "confidential", "restricted")

@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    classification: str = Form("internal"),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_operator),
):
    """Uploads document, chunks, embeds, and stores chunks. Tracks version.
    Phase 9 (M3): tags every chunk with a data-classification level so RAG
    retrieval can later restrict what a viewer is allowed to see."""
    if classification not in _VALID_CLASSIFICATIONS:
        raise HTTPException(status_code=400, detail=f"classification must be one of {_VALID_CLASSIFICATIONS}")
    content = await file.read()
    
    if file.filename.lower().endswith('.pdf'):
        import io
        from pypdf import PdfReader
        try:
            reader = PdfReader(io.BytesIO(content))
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
        except Exception as e:
            text = f"Error extracting PDF: {e}"
    elif file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        text = "" # Skip text extraction for images
    else:
        text = content.decode("utf-8", errors="ignore")
    
    # Check if document exists for versioning
    existing_doc = db.query(Document).filter(Document.filename == file.filename).order_by(Document.version.desc()).first()
    version = 1
    if existing_doc:
        version = existing_doc.version + 1
        
    doc = Document(
        filename=file.filename,
        version=version,
        classification=classification,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    chunks = chunk_document(text)
    # Tag every chunk with its origin doc + classification so RAG retrieval
    # can enforce classification-based access control (Phase 9, M3).
    for c in chunks:
        c["doc_id"] = doc.id
        c["classification"] = classification

    chunks = generate_embeddings(chunks)
    store_chunks(chunks)

    from database.repo import log_audit_action
    log_audit_action(
        db=db, action="DOCUMENT_UPLOADED", user_id=current_user.username,
        details=f"Document {doc.id} ({file.filename}, v{doc.version}, classification={classification}) uploaded.",
    )

    return {"id": doc.id, "filename": doc.filename, "version": doc.version, "classification": doc.classification, "status": "uploaded"}


@router.get("/documents")
def list_documents(db: Session = Depends(get_db), current_user: UserInfo = Depends(require_any_role)):
    """List all documents."""
    docs = db.query(Document).all()
    return [
        {"id": d.id, "filename": d.filename, "version": d.version, "classification": d.classification, "uploaded_at": d.uploaded_at}
        for d in docs
    ]


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: str, db: Session = Depends(get_db), current_user: UserInfo = Depends(require_operator)):
    """Delete document by ID — destructive, operator or admin."""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    db.delete(doc)
    db.commit()

    from database.repo import log_audit_action
    log_audit_action(
        db=db, action="DOCUMENT_DELETED", user_id=current_user.username,
        details=f"Document {doc_id} ({doc.filename}) deleted.",
    )
    return {"status": "deleted", "id": doc_id}
