"""Local launcher coverage with isolated migration and server commands."""

import os
import subprocess
from pathlib import Path

import pytest

START_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "start.sh"


@pytest.mark.parametrize("migration_exit_code", [0, 1])
def test_start_script_requires_successful_migrations_before_starting_servers(
    tmp_path: Path, migration_exit_code: int
) -> None:
    """A failed migration stops both servers; a successful one precedes them."""

    command_directory = tmp_path / "bin"
    command_directory.mkdir()
    virtualenv_bin = tmp_path / "backend" / ".venv" / "bin"
    virtualenv_bin.mkdir(parents=True)
    (virtualenv_bin / "activate").write_text("", encoding="utf-8")
    (tmp_path / "frontend").mkdir()
    command_log = tmp_path / "commands.log"

    for command in ("alembic", "uvicorn", "npm"):
        command_path = command_directory / command
        command_path.write_text(
            "#!/bin/bash\n"
            f'printf \'%s\\n\' "{command} $*" >> "$VKCA_START_COMMAND_LOG"\n'
            + (
                'exit "$VKCA_START_MIGRATION_EXIT_CODE"\n'
                if command == "alembic"
                else "exit 0\n"
            ),
            encoding="utf-8",
        )
        command_path.chmod(0o755)

    environment = {
        **os.environ,
        "PATH": f"{command_directory}{os.pathsep}{os.environ['PATH']}",
        "VKCA_START_COMMAND_LOG": str(command_log),
        "VKCA_START_MIGRATION_EXIT_CODE": str(migration_exit_code),
    }
    result = subprocess.run(
        ["/bin/bash", str(START_SCRIPT)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    commands = command_log.read_text(encoding="utf-8").splitlines()

    assert commands[0] == "alembic upgrade head"
    if migration_exit_code:
        assert result.returncode == 1
        assert commands == ["alembic upgrade head"]
        assert "Database migrations failed" in result.stderr
    else:
        assert result.returncode == 0, result.stderr
        assert sorted(commands[1:]) == [
            "npm run dev",
            "uvicorn src.main:app --reload",
        ]
