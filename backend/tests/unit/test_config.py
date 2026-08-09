"""Configuration selection and backend test-database safety coverage."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.config import (
    DEFAULT_ENV_FILE,
    ENVIRONMENT_SELECTOR,
    TEST_ENV_FILE,
    Settings,
    get_settings,
    get_settings_env_file,
)
from tests.database_safety import (
    UnsafeTestDatabaseError,
    assert_safe_test_database_url,
    database_name_from_url,
)


def test_pytest_settings_resolve_project_root_env_test() -> None:
    """The live pytest process must resolve settings from .env.test."""

    assert os.environ[ENVIRONMENT_SELECTOR] == "test"
    assert get_settings_env_file() == TEST_ENV_FILE
    assert Path(Settings.model_config["env_file"]) == TEST_ENV_FILE

    database_name = database_name_from_url(str(get_settings().database_url))
    assert assert_safe_test_database_url(str(get_settings().database_url)) == (
        database_name
    )


def test_normal_process_defaults_to_project_root_env() -> None:
    """A non-pytest application import must retain the normal .env default."""

    backend_dir = Path(__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment.pop(ENVIRONMENT_SELECTOR, None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from src.config import Settings; "
                "print(Settings.model_config['env_file'])"
            ),
        ],
        cwd=backend_dir,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()) == DEFAULT_ENV_FILE


@pytest.mark.parametrize(
    "database_name",
    ["test", "test_academy", "academy_test", "academy_test_worker"],
)
def test_safety_guard_accepts_distinct_test_database_names(
    database_name: str,
) -> None:
    database_url = f"postgresql+asyncpg://user:password@localhost/{database_name}"

    assert assert_safe_test_database_url(database_url) == database_name


def test_safety_guard_rejects_non_test_database_name() -> None:
    """A test marker elsewhere in the URL must not make a dev DB safe."""

    database_url = (
        "postgresql+asyncpg://test-user:secret@test-host/academy_db"
        "?application_name=pytest"
    )

    with pytest.raises(
        UnsafeTestDatabaseError,
        match="database 'academy_db'",
    ) as rejected:
        assert_safe_test_database_url(database_url)

    assert "secret" not in str(rejected.value)


def test_pytest_bootstrap_refuses_unsafe_database_before_collection() -> None:
    """The configured pytest hook must enforce the guard, not merely expose it."""

    backend_dir = Path(__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment["DATABASE_URL"] = (
        "postgresql+asyncpg://postgres:unsafe-password@localhost/academy_db"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "tests/unit/test_password_service.py",
        ],
        cwd=backend_dir,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode != 0
    assert "Refusing to run backend tests against database 'academy_db'" in output
    assert "unsafe-password" not in output
