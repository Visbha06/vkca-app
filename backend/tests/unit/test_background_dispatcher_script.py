"""Unit coverage for the long-running background dispatcher entry point."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import pytest

from scripts import background_dispatcher, background_jobs


@pytest.mark.asyncio
async def test_dispatch_forever_continues_after_error_and_stops_cleanly(
    caplog: pytest.LogCaptureFixture,
) -> None:
    stop_event = asyncio.Event()
    calls = 0

    class Dispatcher:
        async def dispatch_once(self) -> None:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ConnectionError("redis://user:secret@redis:6379/0")
            stop_event.set()

    await background_dispatcher.dispatch_forever(
        Dispatcher(),  # type: ignore[arg-type]
        poll_seconds=0.001,
        stop_event=stop_event,
    )

    assert calls == 2
    assert "background_dispatch_cycle_failed" in caplog.text
    assert "redis://" not in caplog.text
    assert "secret" not in caplog.text


@pytest.mark.asyncio
async def test_dispatch_forever_propagates_cancellation() -> None:
    class Dispatcher:
        async def dispatch_once(self) -> None:
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await background_dispatcher.dispatch_forever(
            Dispatcher(),  # type: ignore[arg-type]
            poll_seconds=1,
            stop_event=asyncio.Event(),
        )


@pytest.mark.asyncio
async def test_open_background_dispatcher_reuses_cli_setup_and_closes_redis(
    mocker: Any,
) -> None:
    settings = SimpleNamespace(
        redis_url="redis://redis:6379/0",
        background_queue_name="test-queue",
        background_completed_retention_days=7,
        background_dead_retention_days=30,
        background_max_attempts=3,
        background_retry_base_seconds=1,
        background_retry_max_seconds=10,
        background_retry_jitter_seconds=0,
        background_job_timeout_seconds=20,
        background_dispatch_batch_size=12,
        background_claim_lease_seconds=45,
    )
    redis = mocker.Mock()
    redis.aclose = mocker.AsyncMock()
    create_pool = mocker.patch.object(
        background_jobs,
        "create_pool",
        new=mocker.AsyncMock(return_value=redis),
    )
    outbox = mocker.Mock()
    build_outbox = mocker.patch.object(
        background_jobs,
        "build_background_outbox",
        return_value=outbox,
    )
    dispatcher = mocker.Mock()
    dispatcher_type = mocker.patch.object(
        background_jobs,
        "BackgroundJobDispatcher",
        return_value=dispatcher,
    )

    async with background_jobs.open_background_dispatcher(
        settings,
        dispatcher_id="operator:test",
    ) as opened:
        assert opened is dispatcher

    create_pool.assert_awaited_once()
    build_outbox.assert_called_once_with(settings)
    assert dispatcher_type.call_args.kwargs["dispatcher_id"] == "operator:test"
    assert dispatcher_type.call_args.kwargs["batch_size"] == 12
    redis.aclose.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_run_dispatcher_service_closes_resources(mocker: Any) -> None:
    settings = SimpleNamespace(background_dispatch_poll_seconds=0.25)
    dispatcher = mocker.Mock()

    @asynccontextmanager
    async def open_dispatcher(_settings: object):
        yield dispatcher

    mocker.patch.object(background_dispatcher, "get_settings", return_value=settings)
    mocker.patch.object(
        background_dispatcher,
        "install_shutdown_handlers",
        return_value=(),
    )
    mocker.patch.object(
        background_dispatcher,
        "open_background_dispatcher",
        side_effect=open_dispatcher,
    )
    dispatch_forever = mocker.patch.object(
        background_dispatcher,
        "dispatch_forever",
        new=mocker.AsyncMock(),
    )
    engine = mocker.Mock()
    engine.dispose = mocker.AsyncMock()
    mocker.patch.object(background_dispatcher, "engine", engine)

    await background_dispatcher.run_dispatcher_service()

    assert dispatch_forever.await_args.args == (dispatcher,)
    assert dispatch_forever.await_args.kwargs["poll_seconds"] == 0.25
    engine.dispose.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_install_shutdown_handlers_accepts_empty_signal_set() -> None:
    assert (
        background_dispatcher.install_shutdown_handlers(
            asyncio.Event(),
            signals=(),
        )
        == ()
    )
