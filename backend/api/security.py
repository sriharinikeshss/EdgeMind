"""
Phase 9 security/sovereignty API (M5/M6).

  GET  /api/sovereignty/report          — full sovereignty report (egress + audit chain + model hashes)
  GET  /api/sovereignty/egress-check    — just the live egress probe
  GET  /api/audit/export                — full audit trail + chain-verification
  GET  /api/audit/verify                — chain-verification only
  GET  /api/approvals                   — list pending human-approval requests
  POST /api/approvals/{id}/decide       — approve/reject a pending request
"""
from __future__ import annotations
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.session import get_db
from security.rbac import require_any_role, require_operator, require_admin
from api.auth import UserInfo

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/models")
def list_models(current_user: UserInfo = Depends(require_operator)):
    """UI-facing model registry table: modality/VRAM/capabilities from
    ModelRegistry.models, plus each model's live hash-verification status
    (Phase 9) — reuses verify_model_hash(), no duplicated logic."""
    from models.registry import registry
    rows = []
    for model_id, info in registry.models.items():
        hash_status = registry.verify_model_hash(model_id)
        rows.append({
            "model_id": model_id,
            "modality": info.get("modality", []),
            "vram_gb": info.get("vram_gb"),
            "latency_profile": info.get("latency_profile"),
            "capabilities": info.get("capabilities", []),
            "loaded": registry.health_check_model(model_id),
            "hash_verified": hash_status["verified"],
            "hash_detail": hash_status["detail"],
        })
    return rows


@router.get("/sovereignty/report")
def sovereignty_report(db: Session = Depends(get_db), current_user: UserInfo = Depends(require_admin)):
    from security.sovereignty import generate_sovereignty_report
    return generate_sovereignty_report(db=db)


@router.get("/sovereignty/egress-check")
def egress_check(current_user: UserInfo = Depends(require_admin)):
    from security.sovereignty import verify_no_egress
    return verify_no_egress()


@router.get("/audit/export")
def audit_export(db: Session = Depends(get_db), current_user: UserInfo = Depends(require_admin)):
    from database.repo import export_audit_report
    return export_audit_report(db)


@router.get("/audit/verify")
def audit_verify(db: Session = Depends(get_db), current_user: UserInfo = Depends(require_admin)):
    from database.repo import verify_audit_chain
    return verify_audit_chain(db)


@router.get("/approvals")
def list_approvals(db: Session = Depends(get_db), current_user: UserInfo = Depends(require_operator)):
    from security.approvals import list_pending_approvals
    approvals = list_pending_approvals(db)
    return [
        {
            "id": a.id, "task_id": a.task_id, "step_id": a.step_id, "tool_name": a.tool_name,
            "status": a.status, "requested_by": a.requested_by, "created_at": a.created_at,
        }
        for a in approvals
    ]


class ApprovalDecision(BaseModel):
    decision: str  # "APPROVED" or "REJECTED"


@router.post("/approvals/{approval_id}/decide")
def decide_approval_route(
    approval_id: str, body: ApprovalDecision,
    db: Session = Depends(get_db), current_user: UserInfo = Depends(require_admin),
):
    """Only an admin may approve/reject a sensitive-tool request — this IS the
    human-approval gate the Phase 9 DoD's RBAC-negative-test targets."""
    from security.approvals import decide_approval

    if body.decision not in ("APPROVED", "REJECTED"):
        raise HTTPException(status_code=400, detail="decision must be 'APPROVED' or 'REJECTED'")

    approval = decide_approval(db, approval_id, body.decision, decided_by=current_user.username)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    return {
        "id": approval.id, "status": approval.status,
        "decided_by": approval.decided_by, "decided_at": approval.decided_at,
    }
