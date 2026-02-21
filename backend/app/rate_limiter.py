"""
Per-user rate limiting for TerraCube IDEAS.

Extends the IP-based rate limiting to support per-user limits.
Different rate limits can be configured per user role:
- admin: Higher limits (e.g., 1000/minute)
- editor: Standard limits (e.g., 200/minute)
- viewer: Lower limits (e.g., 100/minute)
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, HTTPException, status
from typing import Callable, Optional
from app.config import settings

# Default rate limits per role (per minute)
ROLE_LIMITS = {
    "admin": 1000,
    "editor": 200,
    "viewer": 100
}

# Default limit for unauthenticated users
DEFAULT_LIMIT = 60


def get_user_id(request: Request) -> Optional[str]:
    """
    Extract user ID from request if authenticated.

    Returns user ID or None for unauthenticated requests.
    """
    # Try to get user from request state (set by auth middleware)
    if hasattr(request.state, "user"):
        return request.state.user.get("id")

    # Try from X-User-ID header (could be set by middleware)
    if "x-user-id" in request.headers:
        return request.headers["x-user-id"]

    return None


async def get_rate_limit_key(request: Request) -> str:
    """
    Get the rate limit key for a request.

    Uses user ID if available, otherwise falls back to IP.
    Format: "user:{user_id}" or "ip:{ip_address}"
    """
    user_id = get_user_id(request)

    if user_id:
        return f"user:{user_id}"
    else:
        # Fall back to IP-based limiting
        ip = get_remote_address(request)
        return f"ip:{ip}"


async def get_user_role(user_id: str) -> Optional[str]:
    """
    Get user's role from database.

    Returns role (admin/editor/viewer) or None.
    """
    if not user_id:
        return None

    # Import here to avoid circular imports
    from sqlalchemy import select
    from app.db import AsyncSessionLocal
    from app.models import User

    async with AsyncSessionLocal() as db:
        import uuid as uuid_mod
        try:
            user_uuid = uuid_mod.UUID(user_id)
        except ValueError:
            return None

        result = await db.execute(select(User.role).where(User.id == user_uuid))
        role = result.scalar_one_or_none()
        return role


async def get_rate_limit_for_user(request: Request) -> int:
    """
    Get appropriate rate limit for the requesting user.

    Checks user role and returns the configured limit.
    """
    user_id = get_user_id(request)

    if not user_id:
        return DEFAULT_LIMIT

    role = await get_user_role(user_id)

    if not role:
        return DEFAULT_LIMIT

    return ROLE_LIMITS.get(role, DEFAULT_LIMIT)


class PerUserLimiter:
    """
    Rate limiter that considers user role.

    This replaces the default IP-based limiter with user-aware limiting.
    """

    def __init__(
        self,
        default_limits: str = "200/minute",
        exempt_routes: Optional[list] = None,
        storage_uri: Optional[str] = None
    ):
        self.default_limits = default_limits
        self.exempt_routes = exempt_routes or []
        self.storage_uri = storage_uri

        # Initialize limiter
        self._limiter = Limiter(
            key_func=self._get_key,
            default_limits=[self.default_limits],
            exempt_routes=self.exempt_routes,
            storage_uri=storage_uri,
            storage_options={"connect_args": {"decode_responses": True}}
        )

    async def _get_key(self, request: Request) -> str:
        """Get rate limit key for request."""
        user_id = get_user_id(request)

        if user_id:
            # Check user role for custom limit
            role = await get_user_role(user_id)
            if role and role in ROLE_LIMITS:
                # Use role-specific limit
                limit = ROLE_LIMITS[role]
                return f"user:{user_id}:{limit}/minute"

            # Use default user limit
            return f"user:{user_id}:100/minute"

        # Fall back to IP-based limiting
        ip = get_remote_address(request)
        return f"ip:{ip}:200/minute"

    async def __call__(self, request: Request) -> Request:
        """Called as FastAPI middleware."""
        return await self._limiter(request)

    async def check_limit(self, request: Request) -> None:
        """
        Check if request is within rate limit.

        Raises HTTPException if limit exceeded.
        """
        try:
            await self._limiter.check_request_limit(request)
        except RateLimitExceeded:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": "Rate limit exceeded. Please wait before making more requests.",
                    "retry_after": 60  # Suggest checking back after 60 seconds
                }
            )

    @property
    def limiter(self):
        """Access to underlying limiter instance."""
        return self._limiter


# Global per-user limiter instance
_per_user_limiter: Optional[PerUserLimiter] = None


def get_per_user_limiter() -> PerUserLimiter:
    """Get or create global per-user limiter."""
    global _per_user_limiter
    if _per_user_limiter is None:
        _per_user_limiter = PerUserLimiter(
            default_limits="200/minute",
            exempt_routes=[
                "/api/health",
                "/metrics",
                "/docs",
                "/openapi.json",
                "/api/auth/login",
                "/api/auth/register"
            ]
        )
    return _per_user_limiter
