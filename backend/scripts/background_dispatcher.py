"""Continuously dispatch durable background work to Redis."""

from __future__ import annotations

import asyncio
import logging
import signal
from collections.abc import Iterable

from scripts.background_jobs import open_background_dispatcher
from src.config import get_settings
from src.database import engine
from src.services.background_jobs.dispatcher import BackgroundJobDispatcher

logger = logging.getLogger(__name__)


async def dispatch_forever(
    dispatcher: BackgroundJobDispatcher,
    *,
    poll_seconds: float,
    stop_event: asyncio.Event,
) -> None:
    """Dispatch immediately and then poll until clean shutdown is requested."""

    while not stop_event.is_set():
        try:
            await dispatcher.dispatch_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            # Dispatch failures are durably recorded by the dispatcher. Keep the
            # service alive without reflecting connection details into logs.
            logger.error("background_dispatch_cycle_failed")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=poll_seconds)
        except TimeoutError:
            pass


def install_shutdown_handlers(
    stop_event: asyncio.Event,
    *,
    signals: Iterable[signal.Signals] = (signal.SIGINT, signal.SIGTERM),
) -> tuple[signal.Signals, ...]:
    """Arrange for supported process signals to stop the dispatcher loop."""

    loop = asyncio.get_running_loop()
    installed: list[signal.Signals] = []
    for process_signal in signals:
        try:
            loop.add_signal_handler(process_signal, stop_event.set)
        except (NotImplementedError, RuntimeError):
            continue
        installed.append(process_signal)
    return tuple(installed)


async def run_dispatcher_service() -> None:
    """Run the configured dispatcher until SIGINT, SIGTERM, or cancellation."""

    settings = get_settings()
    stop_event = asyncio.Event()
    installed_signals = install_shutdown_handlers(stop_event)
    loop = asyncio.get_running_loop()
    try:
        async with open_background_dispatcher(settings) as dispatcher:
            await dispatch_forever(
                dispatcher,
                poll_seconds=settings.background_dispatch_poll_seconds,
                stop_event=stop_event,
            )
    finally:
        for process_signal in installed_signals:
            loop.remove_signal_handler(process_signal)
        await engine.dispose()


def main() -> None:
    """Run the long-lived dispatcher process."""

    asyncio.run(run_dispatcher_service())


if __name__ == "__main__":
    main()
