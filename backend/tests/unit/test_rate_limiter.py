"""Unit coverage for authentication login throttling."""

from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio

from src.database import get_db
from src.main import app
from src.services.audit_service import AuditService
from src.services.auth_service import AuthService, RateLimitExceededError
from src.services.rate_limiter import InMemoryRateLimiter

EMAIL = "rate.limit@example.com"
IP_ADDRESS = "127.0.0.1"
KEY = f"{EMAIL}:{IP_ADDRESS}"


class FakeClock:
    """Controllable monotonic clock for rolling-window tests."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest_asyncio.fixture
async def client(mocker):
    """Exercise the login route with isolated database and audit collaborators."""

    session = AsyncMock()
    session.scalar.return_value = None

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    app.state.rate_limiter.clear()
    mocker.patch.object(AuditService, "log_event", new_callable=AsyncMock)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as test_client:
        yield test_client
    app.state.rate_limiter.clear()
    app.dependency_overrides.clear()


def test_five_failures_allowed() -> None:
    limiter = InMemoryRateLimiter()

    for _ in range(5):
        assert limiter.sliding_window_check(KEY) is False
        limiter.record_failure(KEY)

    assert limiter.sliding_window_check(KEY) is True


@pytest.mark.asyncio
async def test_sixth_returns_429(client: httpx.AsyncClient) -> None:
    responses = [
        await client.post(
            "/api/v1/auth/login",
            json={"email": EMAIL, "password": "WrongP@ssword1"},
        )
        for _ in range(6)
    ]

    assert [response.status_code for response in responses] == [
        401,
        401,
        401,
        401,
        401,
        429,
    ]


@pytest.mark.asyncio
async def test_429_response_no_email_disclosure(client: httpx.AsyncClient) -> None:
    for _ in range(5):
        app.state.rate_limiter.record_failure(KEY)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": EMAIL, "password": "WrongP@ssword1"},
    )

    assert response.status_code == 429
    assert response.json() == {
        "detail": "Too many login attempts. Please try again later."
    }
    assert EMAIL not in response.text


def test_successful_login_resets_counter() -> None:
    limiter = InMemoryRateLimiter()
    for _ in range(4):
        limiter.record_failure(KEY)

    limiter.record_success(KEY)

    assert limiter.sliding_window_check(KEY) is False
    assert limiter.attempt_count(KEY) == 0


def test_different_email_ip_independent() -> None:
    limiter = InMemoryRateLimiter()
    for _ in range(5):
        limiter.record_failure(KEY)

    assert limiter.sliding_window_check(KEY) is True
    assert limiter.sliding_window_check(f"other@example.com:{IP_ADDRESS}") is False
    assert limiter.sliding_window_check(f"{EMAIL}:203.0.113.8") is False


def test_rolling_window_expires() -> None:
    clock = FakeClock()
    limiter = InMemoryRateLimiter(clock=clock)
    for _ in range(5):
        limiter.record_failure(KEY)

    clock.advance(901)

    assert limiter.sliding_window_check(KEY) is False
    assert limiter.attempt_count(KEY) == 0


def test_rate_limit_not_permanent_lock() -> None:
    clock = FakeClock()
    limiter = InMemoryRateLimiter(clock=clock)
    for _ in range(5):
        limiter.record_failure(KEY)
    assert limiter.sliding_window_check(KEY) is True

    clock.advance(1800)

    assert limiter.sliding_window_check(KEY) is False
    limiter.record_failure(KEY)
    assert limiter.attempt_count(KEY) == 1


@pytest.mark.asyncio
async def test_rate_limit_audit_event(mocker) -> None:
    limiter = InMemoryRateLimiter()
    for _ in range(5):
        limiter.record_failure(KEY)
    session = AsyncMock()
    audit_log = mocker.patch.object(
        AuditService,
        "log_event",
        new_callable=AsyncMock,
    )

    with pytest.raises(RateLimitExceededError):
        await AuthService(session, rate_limiter=limiter).login(
            EMAIL.upper(),
            "WrongP@ssword1",
            IP_ADDRESS,
            "pytest",
        )

    audit_log.assert_awaited_once_with(
        session,
        "rate_limit",
        result="failure",
        reason="rate_limited",
        ip_address=IP_ADDRESS,
        user_agent="pytest",
        target_resource="/api/v1/auth/login",
    )
    session.scalar.assert_not_awaited()
    session.commit.assert_awaited_once_with()
