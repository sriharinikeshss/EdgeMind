from sqlalchemy.orm import Session
from database.models import ModelRoute, ToolCall, AuditLog

import logging
logger = logging.getLogger(__name__)

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

def log_audit_action(db: Session, action: str, details: str = None, user_id: str = None):
    """Log a general audit action."""
    try:
        audit = AuditLog(
            action=action,
            details=details,
            user_id=user_id
        )
        db.add(audit)
        db.commit()
        db.refresh(audit)
        return audit
    except Exception as exc:
        db.rollback()
        logger.warning("Failed to log audit action '%s': %s", action, exc)
        return None
