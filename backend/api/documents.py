import os
import uuid
import logging
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import Document
from rag.ingest import chunk_document, generate_embeddings, store_chunks

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Uploads document, chunks, embeds, and stores chunks. Tracks version."""
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
    else:
        text = content.decode("utf-8", errors="ignore")
    
    # Check if document exists for versioning
    existing_doc = db.query(Document).filter(Document.filename == file.filename).order_by(Document.version.desc()).first()
    version = 1
    if existing_doc:
        version = existing_doc.version + 1
        
    doc = Document(
        filename=file.filename,
        version=version
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    chunks = chunk_document(text)
    # Add doc_id metadata to chunks
    for c in chunks:
        c["doc_id"] = doc.id
    
    chunks = generate_embeddings(chunks)
    store_chunks(chunks)
    
    return {"id": doc.id, "filename": doc.filename, "version": doc.version, "status": "uploaded"}


@router.get("/documents")
def list_documents(db: Session = Depends(get_db)):
    """List all documents."""
    docs = db.query(Document).all()
    return [{"id": d.id, "filename": d.filename, "version": d.version, "uploaded_at": d.uploaded_at} for d in docs]


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: str, db: Session = Depends(get_db)):
    """Delete document by ID."""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    db.delete(doc)
    db.commit()
    return {"status": "deleted", "id": doc_id}
