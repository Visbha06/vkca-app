"""Dedicated ARQ background-worker entry point."""

from typing import cast

from arq.connections import RedisSettings
from arq.typing import WorkerSettingsBase
from arq.worker import run_worker

from src.config import get_settings
from src.services.background_jobs.contracts import (
    json_job_deserializer,
    json_job_serializer,
)
from src.services.background_jobs.runtime import (
    run_background_work,
    worker_shutdown,
    worker_startup,
)

settings = get_settings()


class WorkerSettings:
    """Bounded ARQ settings for the one generic application worker function."""

    functions = [run_background_work]
    on_startup = worker_startup
    on_shutdown = worker_shutdown
    redis_settings = RedisSettings.from_dsn(str(settings.redis_url))
    queue_name = settings.background_queue_name
    max_jobs = settings.background_worker_max_jobs
    job_timeout = settings.background_job_timeout_seconds
    max_tries = settings.background_max_attempts
    poll_delay = settings.background_dispatch_poll_seconds
    keep_result = 0
    keep_result_forever = False
    log_results = False
    retry_jobs = True
    job_serializer = json_job_serializer
    job_deserializer = json_job_deserializer


def main() -> None:
    """Run the dedicated worker until graceful process shutdown."""

    run_worker(cast(type[WorkerSettingsBase], WorkerSettings))


if __name__ == "__main__":
    main()
