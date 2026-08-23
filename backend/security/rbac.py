"""
RBAC route guard — Phase 9 implementation (M6).

require_role() is a FastAPI dependency FACTORY: every route in api/*.py must
declare Depends(require_role(...)) so "no route is reachable without a role
check" (Phase 9 DoD). Reuses api.auth.get_current_user (JWT decoding, already
built in Phase 1) — this module only adds the authorization layer on top.

Role hierarchy is the same admin > operator > viewer used by the Tool
Registry's ToolDefinition.allowed_roles (Phase 3/4) — kept identical so a
route's RBAC and a tool's RBAC never disagree about who "operator" is.
"""
from __future__ import annotations
import logging

from fastapi import Depends, HTTPException, status

from api.auth import get_current_user, UserInfo

logger = logging.getLogger(__name__)

ALL_ROLES = ("admin", "operator", "viewer")


def require_role(*allowed_roles: str):
    """
    Returns a FastAPI dependency that requires the current user's role to be
    one of `allowed_roles`. Raises 403 otherwise. Always requires a valid JWT
    first (via get_current_user), so an unauthenticated request gets 401.
    """
    allowed = set(allowed_roles) or set(ALL_ROLES)

    def _dependency(current_user: UserInfo = Depends(get_current_user)) -> UserInfo:
        if current_user.role not in allowed:
            logger.warning(
                "RBAC denied: user=%s role=%s requires one of %s",
                current_user.username, current_user.role, sorted(allowed),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not permitted to perform this action.",
            )
        return current_user

    return _dependency


# Convenience shorthands matching the Tool Registry's own role vocabulary.
require_any_role = require_role(*ALL_ROLES)            # any authenticated user
require_operator = require_role("admin", "operator")   # mutating/execution actions
require_admin = require_role("admin")                  # destructive/administrative actions
