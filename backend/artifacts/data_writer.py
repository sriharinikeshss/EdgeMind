"""
CSV / JSON Artifact Writers — Phase 7 implementation (M5).

Lightweight structured-data artifacts, hashed and stored the same way
as the document/spreadsheet writers.
"""
from __future__ import annotations
import csv
import json
import uuid
from typing import Any

from artifacts.storage import artifact_path, sha256_file


class CsvWriter:
    def create_csv(
        self,
        task_id: str,
        title: str,
        headers: list[str],
        rows: list[list[Any]],
        filename: str | None = None,
    ) -> dict:
        artifact_id = str(uuid.uuid4())
        filename = filename or f"{_slugify(title)}.csv"
        path = artifact_path(task_id, artifact_id, filename)

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)

        return {
            "status": "ok",
            "id": artifact_id,
            "task_id": task_id,
            "filename": filename,
            "content_type": "text/csv",
            "file_hash": sha256_file(path),
            "path": path,
        }


class JsonWriter:
    def create_json(
        self,
        task_id: str,
        title: str,
        data: dict | list,
        filename: str | None = None,
    ) -> dict:
        artifact_id = str(uuid.uuid4())
        filename = filename or f"{_slugify(title)}.json"
        path = artifact_path(task_id, artifact_id, filename)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

        return {
            "status": "ok",
            "id": artifact_id,
            "task_id": task_id,
            "filename": filename,
            "content_type": "application/json",
            "file_hash": sha256_file(path),
            "path": path,
        }


def _slugify(title: str) -> str:
    slug = "".join(c if c.isalnum() else "_" for c in title.strip()) or "artifact"
    return slug[:50]
