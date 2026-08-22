"""
Security Engine — Phase 4 RBAC hook (M6).

Centralizes tool authorization so the Tool Registry doesn't do ad hoc
role checks inline, and so later phases (data classification, prompt
injection defenses, full Keycloak RBAC) have one module to extend
instead of scattering checks across the codebase.

Phase 4: role-membership check only.
Phase 9: full RBAC roles (Admin/Approver/Operator/Viewer), data
classification gating, encryption, prompt-injection detection.
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


def check_role_permission(user_role: str, allowed_roles: list[str]) -> bool:
    """Return True if user_role is one of allowed_roles."""
    return user_role in allowed_roles


def authorize_tool(tool_name: str, user_role: str, allowed_roles: list[str]) -> bool:
    """
    Authorize a tool call for a given role.
    Logs a warning on denial so RBAC blocks are visible in server logs
    even before Phase 9's full audit/security panel exists.
    """
    allowed = check_role_permission(user_role, allowed_roles)
    if not allowed:
        logger.warning(
            "RBAC denial: role '%s' is not allowed to call tool '%s' (allowed: %s)",
            user_role, tool_name, allowed_roles,
        )
    return allowed
