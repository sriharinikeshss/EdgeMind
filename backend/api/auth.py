"""
JWT-based authentication for KAVACH — Phase 1 stub.

POST /api/auth/login  → returns a JWT access token
GET  /api/auth/me     → returns the current user from the token

In Phase 9 this will be replaced with full Keycloak OIDC integration.
For Phase 1, a simple hard-coded demo user is accepted so the team can
test the login → chat → sovereignty flow without an auth server.

Default demo credentials (DEV ONLY):
  username: admin    password: kavach123
  username: operator password: kavach123
  username: viewer   password: kavach123
"""
import os
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

# python-jose must be installed; passlib for bcrypt hashing
try:
    from jose import JWTError, jwt
    from passlib.context import CryptContext
    _JOSE_AVAILABLE = True
except ImportError:
    _JOSE_AVAILABLE = False

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Config ───────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "kavach-dev-secret-do-not-use-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))  # 8 hours

# ── Hard-coded dev users (Phase 1 only) ──────────────────────────────────────
# In Phase 9 these are replaced by Keycloak lookups.
if _JOSE_AVAILABLE:
    _pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    _DEMO_USERS: dict[str, dict] = {
        "admin": {
            "username": "admin",
            "role": "admin",
            "hashed_password": _pwd_ctx.hash("kavach123"),
        },
        "operator": {
            "username": "operator",
            "role": "operator",
            "hashed_password": _pwd_ctx.hash("kavach123"),
        },
        "viewer": {
            "username": "viewer",
            "role": "viewer",
            "hashed_password": _pwd_ctx.hash("kavach123"),
        },
    }
else:
    _pwd_ctx = None
    _DEMO_USERS = {}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ── Schemas ───────────────────────────────────────────────────────────────────
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class UserInfo(BaseModel):
    username: str
    role: str


# ── Helpers ───────────────────────────────────────────────────────────────────
def _create_access_token(data: dict) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload.update({"exp": expire})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInfo:
    """FastAPI dependency — decodes JWT and returns the current user."""
    if not _JOSE_AVAILABLE:
        # Fallback: accept any token in dev if jose is not installed
        return UserInfo(username="dev-user", role="operator")
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub", "")
        role: str = payload.get("role", "operator")
        if not username:
            raise credentials_exc
        return UserInfo(username=username, role=role)
    except JWTError:
        raise credentials_exc


# ── Routes ────────────────────────────────────────────────────────────────────
@router.post("/auth/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Accepts username + password (form-encoded).
    Returns a JWT token on success.
    """
    if not _JOSE_AVAILABLE:
        # python-jose not installed — return a fake token for very early dev
        logger.warning("python-jose not installed; returning insecure dev token.")
        # Map known usernames to roles for test cases
        role = "operator"
        if form_data.username == "viewer": role = "viewer"
        if form_data.username == "admin": role = "admin"
        return TokenResponse(
            access_token="dev-insecure-token",
            username=form_data.username,
            role=role,
        )

    user = _DEMO_USERS.get(form_data.username)
    if not user or not _pwd_ctx.verify(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = _create_access_token({"sub": user["username"], "role": user["role"]})
    return TokenResponse(
        access_token=token,
        username=user["username"],
        role=user["role"],
    )


@router.get("/auth/me", response_model=UserInfo)
def me(current_user: UserInfo = Depends(get_current_user)):
    """Returns info about the currently authenticated user."""
    return current_user
