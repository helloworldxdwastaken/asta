"""Bearer token auth middleware for remote access via Cloudflare Tunnel."""
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

_PUBLIC_PATHS = frozenset({"/", "/health", "/api/health"})


class BearerTokenMiddleware(BaseHTTPMiddleware):
    """Require Authorization: Bearer <token> for non-local requests.

    Rules:
    - ASTA_API_TOKEN empty → all requests pass (backward compatible).
    - OPTIONS (CORS preflight) → always pass.
    - Public paths (/, /health, /api/health) → always pass.
    - Local requests (127.0.0.1 / ::1) without Cf-Connecting-Ip → pass.
    - Everything else → require valid Bearer token or ?token= query param.
    """

    async def dispatch(self, request: Request, call_next):
        from app.config import get_settings

        token = (get_settings().asta_api_token or "").strip()

        # No token configured — open access (backward compatible)
        if not token:
            return await call_next(request)

        # Always allow CORS preflight
        if request.method == "OPTIONS":
            return await call_next(request)

        # Always allow public paths
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        # Detect if request came through Cloudflare Tunnel
        cf_ip = request.headers.get("cf-connecting-ip")
        is_tunnel = bool(cf_ip)

        # Local requests (not through tunnel) skip auth
        client_host = request.client.host if request.client else ""
        if client_host in ("127.0.0.1", "::1", "localhost") and not is_tunnel:
            return await call_next(request)

        # Check Authorization: Bearer <token>
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            provided = auth_header[7:].strip()
            if provided == token:
                return await call_next(request)

        # Fallback: ?token= query param (for SSE/EventSource which can't set headers)
        query_token = request.query_params.get("token", "")
        if query_token and query_token == token:
            return await call_next(request)

        logger.warning("Unauthorized request from %s to %s", cf_ip or client_host, request.url.path)
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
