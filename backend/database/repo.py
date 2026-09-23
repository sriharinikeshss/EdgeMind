import hashlib
from sqlalchemy.orm import Session
from database.models import ModelRoute, ToolCall, AuditLog

import logging
logger = logging.getLogger(__name__)

_GENESIS_HASH = "0" * 64


def log_model_selection(db: Session, task_id: str, task_type: str, selected_model: str, routing_reason: str = None):
    """Log the model routing decision (Phase 2)."""
    try:
        route_log = ModelRoute(
            task_id=task_id,
            task_type=task_type,
            selected_model=selected_model,
            routing_reason=routing_reason
        )
        db.add(route_log)
        db.commit()
        db.refresh(route_log)
        return route_log
    except Exception as exc:
        db.rollback()
        logger.warning("Failed to log model selection for task %s: %s", task_id, exc)
        return None


def _compute_audit_hash(prev_hash: str, action: str, details: str, user_id: str, created_at) -> str:
    payload = f"{prev_hash}|{action}|{details or ''}|{user_id or ''}|{created_at.isoformat()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def log_audit_action(db: Session, action: str, details: str = None, user_id: str = None):
    """
    Log a general audit action — Phase 9: each row is chained to the previous
    one (prev_hash -> hash), so the whole table forms a tamper-evident chain
    (see verify_audit_chain()). Any single row edited after the fact breaks
    every hash after it.
    """
    try:
        import datetime
        last = db.query(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).first()
        prev_hash = last.hash if last and last.hash else _GENESIS_HASH
        created_at = datetime.datetime.utcnow()
        row_hash = _compute_audit_hash(prev_hash, action, details, user_id, created_at)

        audit = AuditLog(
            action=action,
            details=details,
            user_id=user_id,
            prev_hash=prev_hash,
            hash=row_hash,
            created_at=created_at,
        )
        db.add(audit)
        db.commit()
        db.refresh(audit)
        return audit
    except Exception as exc:
        db.rollback()
        logger.warning("Failed to log audit action '%s': %s", action, exc)
        return None


def verify_audit_chain(db: Session) -> dict:
    """
    Phase 9 (M5): walk the entire audit_logs table in insertion order and
    recompute each row's hash from its own fields + the previous row's hash.
    Returns {"valid": bool, "checked": int, "broken_at": str | None}.

    A row is only checkable if it was written after hash-chaining was added
    (prev_hash/hash populated) — older rows are skipped and counted separately
    so a fresh dev DB (with pre-Phase-9 rows) doesn't report a false break.
    """
    rows = db.query(AuditLog).order_by(AuditLog.created_at.asc(), AuditLog.id.asc()).all()
    expected_prev = _GENESIS_HASH
    checked = 0
    skipped_legacy = 0

    for row in rows:
        if row.hash is None:
            skipped_legacy += 1
            continue
        recomputed = _compute_audit_hash(row.prev_hash or _GENESIS_HASH, row.action, row.details, row.user_id, row.created_at)
        if row.prev_hash != expected_prev or recomputed != row.hash:
            return {
                "valid": False,
                "checked": checked,
                "skipped_legacy": skipped_legacy,
                "broken_at": row.id,
                "detail": "Hash mismatch — audit_logs row was altered after being written, or the chain has a gap.",
            }
        expected_prev = row.hash
        checked += 1

    return {"valid": True, "checked": checked, "skipped_legacy": skipped_legacy, "broken_at": None}


def export_audit_report(db: Session) -> dict:
    """Phase 9 (M5): full audit trail + chain-verification result, for the
    Sovereignty Report / compliance export."""
    rows = db.query(AuditLog).order_by(AuditLog.created_at.asc(), AuditLog.id.asc()).all()
    return {
        "chain_verification": verify_audit_chain(db),
        "total_entries": len(rows),
        "entries": [
            {
                "id": r.id,
                "user_id": r.user_id,
                "action": r.action,
                "details": r.details,
                "prev_hash": r.prev_hash,
                "hash": r.hash,
                "created_at": r.created_at.isoformat() + 'Z' if r.created_at else None,
            }
            for r in rows
        ],
    }
