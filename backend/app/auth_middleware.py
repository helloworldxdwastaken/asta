"""Auth middleware: JWT-based multi-user auth with backward-compat fallback.

Priority:
1. If users table has rows → JWT mode (decode token, set user_id/role on request.state)
2. If users table empty + ASTA_API_TOKEN set → legacy Bearer token mode
3. If users table empty + no token → open access (local dev)
"""
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

_PUBLIC_PATHS = frozenset({"/", "/health", "/api/health", "/api/auth/login", "/api/auth/register"})

# Cache whether multi-user mode is active (refreshed on miss)
_multi_user_mode: bool | None = None


async def _check_multi_user() -> bool:
    """Check if users table has any rows (cached)."""
    global _multi_user_mode
    if _multi_user_mode is not None:
        return _multi_user_mode
    try:
        from app.db import get_db
        db = get_db()
        await db.connect()
        _multi_user_mode = await db.has_any_users()
    except Exception:
        _multi_user_mode = False
    return _multi_user_mode


def invalidate_multi_user_cache() -> None:
    """Call after creating/deleting users to refresh the cache."""
    global _multi_user_mode
    _multi_user_mode = None


class AuthMiddleware(BaseHTTPMiddleware):
    """JWT auth when users exist; legacy Bearer token fallback otherwise."""

    async def dispatch(self, request: Request, call_next):
        # Always allow CORS preflight
        if request.method == "OPTIONS":
            return await call_next(request)

        # Always allow public paths
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        multi_user = await _check_multi_user()

        if multi_user:
            return await self._jwt_auth(request, call_next)
        else:
            return await self._legacy_bearer_auth(request, call_next)

    async def _jwt_auth(self, request: Request, call_next):
        """Multi-user JWT mode: decode token, set request.state.{user_id, user_role, username}."""
        from app.auth_utils import decode_jwt

        token = self._extract_token(request)
        if not token:
            return JSONResponse({"detail": "Authentication required"}, status_code=401)

        payload = decode_jwt(token)
        if not payload:
            return JSONResponse({"detail": "Invalid or expired token"}, status_code=401)

        request.state.user_id = payload.get("sub", "")
        request.state.user_role = payload.get("role", "user")
        request.state.username = payload.get("username", "")
        return await call_next(request)

    async def _legacy_bearer_auth(self, request: Request, call_next):
        """No users → legacy single-user mode with optional Bearer token for tunnel."""
        from app.config import get_settings

        token = (get_settings().asta_api_token or "").strip()

        # No token configured → open access
        if not token:
            request.state.user_id = "default"
            request.state.user_role = "admin"
            request.state.username = "admin"
            return await call_next(request)

        # Local requests skip auth
        cf_ip = request.headers.get("cf-connecting-ip")
        is_tunnel = bool(cf_ip)
        client_host = request.client.host if request.client else ""
        if client_host in ("127.0.0.1", "::1", "localhost") and not is_tunnel:
            request.state.user_id = "default"
            request.state.user_role = "admin"
            request.state.username = "admin"
            return await call_next(request)

        # Check Bearer token
        provided = self._extract_bearer(request)
        if provided and provided == token:
            request.state.user_id = "default"
            request.state.user_role = "admin"
            request.state.username = "admin"
            return await call_next(request)

        # Check query param
        query_token = request.query_params.get("token", "")
        if query_token and query_token == token:
            request.state.user_id = "default"
            request.state.user_role = "admin"
            request.state.username = "admin"
            return await call_next(request)

        logger.warning("Unauthorized request from %s to %s", cf_ip or client_host, request.url.path)
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)

    @staticmethod
    def _extract_token(request: Request) -> str | None:
        """Extract JWT from Authorization header or ?token= query param."""
        bearer = AuthMiddleware._extract_bearer(request)
        if bearer:
            return bearer
        return request.query_params.get("token") or None

    @staticmethod
    def _extract_bearer(request: Request) -> str | None:
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:].strip() or None
        return None
