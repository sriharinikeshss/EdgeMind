with open("backend/api/documents.py", "r", encoding="utf-8") as f:
    code = f.read()

import re

# Upload to MinIO right after creating doc object
replacement = """    db.refresh(doc)

    # Store raw document in MinIO
    try:
        from artifacts.minio_client import upload_bytes
        upload_bytes("documents", f"{doc.id}_{doc.filename}", content)
    except Exception as e:
        logger.error("Failed to upload document to MinIO: %s", e)

    chunks = chunk_document(text)"""

code = code.replace("    db.refresh(doc)\n\n    chunks = chunk_document(text)", replacement)

with open("backend/api/documents.py", "w", encoding="utf-8") as f:
    f.write(code)
