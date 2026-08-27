"""Bound HTTP request bodies before route validation or persistence work."""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

BODY_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class RequestBodyLimitMiddleware:
    """Reject oversized mutation bodies while buffering at most the fixed limit.

    A declared oversized Content-Length is rejected without reading the body.
    Requests without a trustworthy length (including chunked requests) are read
    only until the configured limit is crossed, then rejected before FastAPI can
    validate a route payload or call application persistence services.
    """

    def __init__(self, app: ASGIApp, *, max_body_bytes: int) -> None:
        if max_body_bytes <= 0:
            raise ValueError("max_body_bytes must be positive")
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") not in BODY_METHODS:
            await self.app(scope, receive, send)
            return

        content_length = self._content_length(scope)
        if content_length is not None and content_length > self.max_body_bytes:
            await self._reject(scope, receive, send)
            return

        messages: list[Message] = []
        received_bytes = 0
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] == "http.disconnect":
                break
            if message["type"] != "http.request":
                continue
            received_bytes += len(message.get("body", b""))
            if received_bytes > self.max_body_bytes:
                await self._reject(scope, receive, send)
                return
            if not message.get("more_body", False):
                break

        async def replay() -> Message:
            if messages:
                return messages.pop(0)
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app(scope, replay, send)

    @staticmethod
    def _content_length(scope: Scope) -> int | None:
        for name, raw_value in scope.get("headers", ()):
            if name.lower() != b"content-length":
                continue
            try:
                value = int(raw_value)
            except ValueError:
                return None
            return value if value >= 0 else None
        return None

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse(
            status_code=413,
            content={"detail": "Request body is too large."},
        )
        await response(scope, receive, send)
