"""
At-rest encryption for artifacts/documents — Phase 9 implementation (M6).

encrypt_file()/decrypt_file() use Fernet (AES-128-CBC + HMAC, from the
`cryptography` package — already a transitive dependency via python-jose, no
new install needed). Fully local: the key is generated on first use and kept
under ARTIFACTS_DIR, never transmitted anywhere.

Applied to Phase 7 artifacts behind the ARTIFACT_ENCRYPTION_ENABLED flag
(default off) — see artifacts/storage.py's encrypt_file_at_rest()/
decrypt_file_for_read(), called from the Executor after Phase 8 validation
and from the artifact download endpoint respectively. Default-off keeps
Phase 7/8's existing validators (which need to open a plaintext .docx/.xlsx/
.pdf) working unchanged; turning it on is an operational choice, not a code
change.
"""
from __future__ import annotations
import logging
import os

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_KEY_ENV_VAR = "ARTIFACT_ENCRYPTION_KEY"
_KEY_FILE_ENV_VAR = "ARTIFACT_ENCRYPTION_KEY_FILE"


def get_or_create_key() -> bytes:
    """
    Resolve the Fernet key: explicit env var > a key file on disk > generate
    and persist a new one. Never logged.
    """
    env_key = os.getenv(_KEY_ENV_VAR)
    if env_key:
        return env_key.encode() if isinstance(env_key, str) else env_key

    key_path = os.getenv(_KEY_FILE_ENV_VAR, os.path.join(os.getenv("ARTIFACTS_DIR", "/tmp/artifacts"), ".encryption_key"))
    if os.path.isfile(key_path):
        with open(key_path, "rb") as f:
            return f.read().strip()

    key = Fernet.generate_key()
    os.makedirs(os.path.dirname(key_path), exist_ok=True)
    with open(key_path, "wb") as f:
        f.write(key)
    logger.info("Generated new artifact encryption key at %s", key_path)
    return key


def encrypt_bytes(data: bytes, key: bytes | None = None) -> bytes:
    return Fernet(key or get_or_create_key()).encrypt(data)


def decrypt_bytes(token: bytes, key: bytes | None = None) -> bytes:
    return Fernet(key or get_or_create_key()).decrypt(token)


def encrypt_file(path: str, key: bytes | None = None) -> str:
    """Encrypt a file in place. Returns the same path."""
    with open(path, "rb") as f:
        plaintext = f.read()
    with open(path, "wb") as f:
        f.write(encrypt_bytes(plaintext, key=key))
    return path


def decrypt_file(path: str, key: bytes | None = None) -> bytes:
    """Return the decrypted plaintext bytes of an encrypted file (does not write to disk)."""
    with open(path, "rb") as f:
        ciphertext = f.read()
    try:
        return decrypt_bytes(ciphertext, key=key)
    except InvalidToken as exc:
        raise ValueError(f"Could not decrypt {path}: wrong key or corrupted/tampered file") from exc
