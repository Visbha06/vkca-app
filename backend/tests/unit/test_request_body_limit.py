"""Unit tests for bounded ASGI request-body handling."""

from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from src.middleware.request_body_limit import RequestBodyLimitMiddleware

ASGIMessage = dict[str, Any]


async def run_request(
    chunks: list[bytes], *, max_body_bytes: int
) -> tuple[bool, list[ASGIMessage]]:
    """Run a chunked request without a Content-Length header."""

    route_called = False
    messages = [
        {
            "type": "http.request",
            "body": chunk,
            "more_body": index < len(chunks) - 1,
        }
        for index, chunk in enumerate(chunks)
    ]
    sent: list[ASGIMessage] = []

    async def receive() -> ASGIMessage:
        return messages.pop(0)

    async def send(message: ASGIMessage) -> None:
        sent.append(message)

    async def app(
        scope: dict[str, Any],
        receive_request: Callable[[], Awaitable[ASGIMessage]],
        send_response: Callable[[ASGIMessage], Awaitable[None]],
    ) -> None:
        nonlocal route_called
        route_called = True
        replayed_body = bytearray()
        while True:
            message = await receive_request()
            replayed_body.extend(message.get("body", b""))
            if not message.get("more_body", False):
                break
        assert bytes(replayed_body) == b"".join(chunks)
        await send_response(
            {"type": "http.response.start", "status": 204, "headers": []}
        )
        await send_response({"type": "http.response.body", "body": b""})

    middleware = RequestBodyLimitMiddleware(app, max_body_bytes=max_body_bytes)
    await middleware(
        {"type": "http", "method": "POST", "headers": []},
        receive,
        send,
    )
    return route_called, sent


@pytest.mark.asyncio
async def test_chunked_request_within_limit_reaches_route() -> None:
    route_called, sent = await run_request([b"abc", b"de"], max_body_bytes=5)

    assert route_called is True
    assert sent[0]["status"] == 204


@pytest.mark.asyncio
async def test_chunked_request_over_limit_is_rejected_before_route() -> None:
    route_called, sent = await run_request([b"abc", b"def"], max_body_bytes=5)

    assert route_called is False
    assert sent[0]["status"] == 413
