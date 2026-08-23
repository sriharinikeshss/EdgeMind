"""
Human-approval gate for sensitive tool calls — Phase 9 implementation (M1/M6).

detect_sensitive_operation() (here: requires_approval()) is deliberately
narrower than "the Tool Registry's risk_level == HIGH": that flag also covers
execute_python, which is already isolated by Phase 4's sandbox and is core to
the Phase 3/4 demo path ("calculate X using python, then save the result") —
gating it on human approval would block existing, already-safe functionality
for no security benefit. The Phase 9 plan's own examples of what needs a
human sign-off are state-mutating/destructive actions outside the sandbox
("finalize approval note", "overwrite/delete file") — so this module gates
exactly those: write_file (can overwrite any file the process can reach) and
query_db (can mutate persistent data). New sensitive tools register here
explicitly rather than inheriting it implicitly from risk_level.

The Executor checks requires_approval() before running a sensitive tool step;
if no approval has been granted yet for that exact task+tool+step, it opens a
PENDING Approval row and fails the step immediately (mirroring the existing
PermissionError/"not retried" pattern already used for RBAC denials in
Executor.execute_step) rather than burning through MAX_RETRIES pointlessly.
An admin then approves/rejects via POST /api/approvals/{id}/decide, and the
task can be resubmitted.
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

# Tools whose effects are destructive/state-mutating outside the sandbox and
# therefore require a human sign-off before the Executor will run them.
SENSITIVE_TOOLS = {"write_file", "query_db"}


def requires_approval(tool_name: str) -> bool:
    """detect_sensitive_operation(): does this tool call need human approval
    before the Executor may run it?"""
    return tool_name in SENSITIVE_TOOLS


def get_active_approval(db, task_id: str, step_id: str):
    from database.models import Approval
    return (
        db.query(Approval)
        .filter(Approval.task_id == task_id, Approval.step_id == step_id)
        .order_by(Approval.created_at.desc())
        .first()
    )


def create_approval_request(db, task_id: str, step_id: str, tool_name: str, arguments: dict, requested_by: str | None):
    from database.models import Approval
    import json

    approval = Approval(
        task_id=task_id,
        step_id=step_id,
        tool_name=tool_name,
        arguments=json.dumps(arguments, default=str)[:2000],
        status="PENDING",
        requested_by=requested_by,
    )
    db.add(approval)
    db.commit()
    db.refresh(approval)

    from database.repo import log_audit_action
    log_audit_action(
        db=db, action="APPROVAL_REQUESTED", user_id=requested_by,
        details=f"Task {task_id} step {step_id}: HIGH-risk tool '{tool_name}' awaiting human approval (approval_id={approval.id})",
    )
    return approval


def decide_approval(db, approval_id: str, decision: str, decided_by: str):
    """decision: 'APPROVED' or 'REJECTED'."""
    from database.models import Approval
    import datetime

    if decision not in ("APPROVED", "REJECTED"):
        raise ValueError("decision must be 'APPROVED' or 'REJECTED'")

    approval = db.query(Approval).filter(Approval.id == approval_id).first()
    if not approval:
        return None
    approval.status = decision
    approval.decided_by = decided_by
    approval.decided_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(approval)

    from database.repo import log_audit_action
    log_audit_action(
        db=db, action=f"APPROVAL_{decision}", user_id=decided_by,
        details=f"Approval {approval_id} for task {approval.task_id} tool '{approval.tool_name}' {decision.lower()} by {decided_by}",
    )
    return approval


def list_pending_approvals(db):
    from database.models import Approval
    return db.query(Approval).filter(Approval.status == "PENDING").order_by(Approval.created_at.desc()).all()
