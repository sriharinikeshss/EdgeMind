from sqlalchemy.orm import Session
from database.models import ModelRoute, ToolCall, AuditLog

def log_model_selection(db: Session, task_id: str, task_type: str, selected_model: str, routing_reason: str = None):
    """Log the model routing decision (Phase 2)."""
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

def log_audit_action(db: Session, action: str, details: str = None, user_id: str = None):
    """Log a general audit action."""
    audit = AuditLog(
        action=action,
        details=details,
        user_id=user_id
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit
