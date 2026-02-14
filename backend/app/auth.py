from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings

# JWT token expiry duration (configurable via settings)
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 30

# Security scheme for Swagger UI
security = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a short-lived JWT access token."""
    to_encode = data.copy()
    # Mark as access token
    to_encode["type"] = "access"
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm="HS256")
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create a long-lived JWT refresh token."""
    to_encode = data.copy()
    # Mark as refresh token
    to_encode["type"] = "refresh"
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm="HS256")
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate JWT token. Returns payload or None if invalid/expired."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        return payload
    except JWTError:
        return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> dict:
    """
    FastAPI dependency to verify JWT token and extract user info.
    Use this as a dependency on protected endpoints:
        @router.get("/protected")
        async def protected_route(user: dict = Depends(get_current_user)):
            ...
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract user info from token payload
    user_id = payload.get("sub")
    email = payload.get("email")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {"id": user_id, "email": email}


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """
    Optional authentication - returns user if token is valid, None otherwise.
    Useful for endpoints that work for both authenticated and anonymous users.
    """
    if credentials is None:
        return None

    token = credentials.credentials
    payload = decode_token(token)

    if payload is None:
        return None

    user_id = payload.get("sub")
    email = payload.get("email")

    if not user_id:
        return None

    return {"id": user_id, "email": email}
