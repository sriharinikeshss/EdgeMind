with open("backend/api/artifacts.py", "r", encoding="utf-8") as f:
    code = f.read()

target = """    path = resolve_artifact_path(artifact.task_id, artifact.id, artifact.filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=410, detail="Artifact file is missing from storage")"""

replacement = """    path = resolve_artifact_path(artifact.task_id, artifact.id, artifact.filename)
    if not os.path.isfile(path):
        try:
            from artifacts.minio_client import download_file
            os.makedirs(os.path.dirname(path), exist_ok=True)
            download_file("artifacts", f"{artifact.id}_{artifact.filename}", path)
        except Exception as e:
            logger.error("Failed to recover artifact from MinIO: %s", e)
    
    if not os.path.isfile(path):
        raise HTTPException(status_code=410, detail="Artifact file is missing from storage and MinIO")"""

code = code.replace(target, replacement)

target2 = """    path = resolve_artifact_path(artifact.task_id, artifact.id, artifact.filename)
    if not os.path.isfile(path):
        return {"id": artifact_id, "status": "missing", "verified": False}"""

replacement2 = """    path = resolve_artifact_path(artifact.task_id, artifact.id, artifact.filename)
    if not os.path.isfile(path):
        try:
            from artifacts.minio_client import download_file
            os.makedirs(os.path.dirname(path), exist_ok=True)
            download_file("artifacts", f"{artifact.id}_{artifact.filename}", path)
        except Exception as e:
            logger.error("Failed to recover artifact from MinIO: %s", e)
            
    if not os.path.isfile(path):
        return {"id": artifact_id, "status": "missing", "verified": False}"""

code = code.replace(target2, replacement2)

with open("backend/api/artifacts.py", "w", encoding="utf-8") as f:
    f.write(code)
