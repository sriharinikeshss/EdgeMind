"""
Artifact Storage — Phase 7 implementation (M5).

Local-disk storage for generated artifacts (sovereign: no external/cloud
storage). Files are laid out at ARTIFACTS_DIR/{task_id}/{artifact_id}_{filename}
so the on-disk path can be reconstructed later purely from the `artifacts`
table row (id, task_id, filename) without needing an extra storage_path
column beyond what backend/schemas/artifact.schema.json declares.
"""
from __future__ import annotations
import hashlib
import os

ARTIFACTS_DIR = os.getenv("ARTIFACTS_DIR", "/tmp/artifacts")

# Phase 9 (M6): encrypt generated artifacts at rest. Off by default so Phase 7/8's
# format validators (which need to open a plaintext .docx/.xlsx/.pdf) keep working
# unchanged — enabling this is an operational choice made after Phase 8 validation
# has already run on the plaintext file (see Executor._write_artifact_if_generated).
ARTIFACT_ENCRYPTION_ENABLED = os.getenv("ARTIFACT_ENCRYPTION_ENABLED", "false").lower() == "true"


def artifact_path(task_id: str, artifact_id: str, filename: str) -> str:
    """Return the on-disk path for an artifact, creating the task's directory."""
    task_dir = os.path.join(ARTIFACTS_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)
    return os.path.join(task_dir, f"{artifact_id}_{filename}")


def resolve_artifact_path(task_id: str, artifact_id: str, filename: str) -> str:
    """Reconstruct an artifact's on-disk path from its DB fields (no side effects)."""
    return os.path.join(ARTIFACTS_DIR, task_id, f"{artifact_id}_{filename}")


def sha256_file(path: str) -> str:
    """Compute the SHA-256 hash of a file on disk, streaming in chunks."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _encryption_marker_path(path: str) -> str:
    return f"{path}.enc"


def is_encrypted_at_rest(path: str) -> bool:
    """A sidecar marker (rather than sniffing file bytes) — reliable and avoids
    false positives against legitimate binary formats like .docx/.xlsx/.pdf."""
    return os.path.isfile(_encryption_marker_path(path))


def encrypt_file_at_rest(path: str) -> bool:
    """Encrypt `path` in place if ARTIFACT_ENCRYPTION_ENABLED, recording a
    sidecar marker. No-op (returns False) when the flag is off. Call this
    AFTER Phase 8's validate_artifact() has already checked the plaintext."""
    if not ARTIFACT_ENCRYPTION_ENABLED:
        return False
    from security.encryption import encrypt_file
    encrypt_file(path)
    open(_encryption_marker_path(path), "w").close()
    return True
