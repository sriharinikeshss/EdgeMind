with open("backend/orchestrator/executor.py", "r", encoding="utf-8") as f:
    code = f.read()

import re

target = """        if not self.db:
            return
        try:"""

replacement = """        # Upload to MinIO
        try:
            from artifacts.minio_client import upload_file
            if meta.get("path"):
                upload_file("artifacts", f"{meta.get('id')}_{meta.get('filename')}", meta.get("path"))
        except Exception as e:
            logger.error("Failed to upload artifact to MinIO: %s", e)

        if not self.db:
            return
        try:"""

code = code.replace(target, replacement)

with open("backend/orchestrator/executor.py", "w", encoding="utf-8") as f:
    f.write(code)
