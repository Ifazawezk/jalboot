"""Browser-facing protections applied to every request.

Cookies are sent by the browser on its own, so a request carrying one proves
nothing about which site asked for it. Three layers deal with that:

    SameSite=Lax    the browser leaves the cookie off cross-site POSTs
    Origin check    a state-changing request from an origin not on the list is refused
    CSRF token      staff writes must echo a token that another site cannot read

The Origin check sits here because it has to run for every state-changing route. The
CSRF token is checked per route, in the dependency that loads the staff session.

This is plain ASGI middleware on purpose. Starlette's BaseHTTPMiddleware wraps the
response body, which interferes with long-lived event streams.
"""

from __future__ import annotations

from typing import Iterable

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

CONTENT_SECURITY_POLICY = "; ".join((
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "object-src 'none'",
))


def request_origin(request: Request) -> str:
    return f"{request.url.scheme}://{request.headers.get('host', '')}".rstrip("/")


def origin_allowed(request: Request, allowed: Iterable[str]) -> bool:
    """A browser always sends Origin on a cross-origin write. A missing Origin means
    a tool such as curl, which has no ambient cookies to abuse, so it passes here and
    still has to authenticate. Sec-Fetch-Site covers a browser that dropped Origin."""
    origin = request.headers.get("origin")
    if origin:
        origin = origin.rstrip("/")
        return origin == request_origin(request) or origin in set(allowed)
    return request.headers.get("sec-fetch-site", "none") in {"same-origin", "same-site", "none"}


class BrowserGuards:
    def __init__(self, app: ASGIApp, allowed_origins: Iterable[str], https: bool):
        self.app = app
        self.allowed = tuple(allowed_origins)
        self.https = https

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        is_api = request.url.path.startswith("/api/")

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("X-Frame-Options", "DENY")
                headers.setdefault("Referrer-Policy", "no-referrer")
                headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
                headers.setdefault("X-Data-Notice", "simulated")
                if is_api:
                    headers.setdefault("Cache-Control", "no-store")
                if self.https:
                    headers.setdefault("Strict-Transport-Security", "max-age=31536000")
            await send(message)

        if request.method not in SAFE_METHODS and is_api and not origin_allowed(request, self.allowed):
            response = JSONResponse(
                status_code=403,
                content={"error": {
                    "code": "origin_not_allowed",
                    "message": "This origin may not call the API.",
                    "retryable": False,
                }},
            )
            await response(scope, receive, send_with_headers)
            return
        await self.app(scope, receive, send_with_headers)
