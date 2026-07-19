"""Executable coverage for the 004 frontend-auth quickstart flow."""

import subprocess
from pathlib import Path


def test_full_fifteen_scenario_frontend_auth_quickstart_flow() -> None:
    """Run the browser journey that maps to all 15 quickstart scenarios."""

    repository_root = Path(__file__).resolve().parents[4]
    frontend_dir = repository_root / "frontend"
    result = subprocess.run(
        [
            "npm",
            "run",
            "test:e2e",
            "--",
            "e2e/auth-flow.spec.ts",
            "--project=chromium",
        ],
        cwd=frontend_dir,
        capture_output=True,
        check=False,
        text=True,
        timeout=180,
    )

    assert result.returncode == 0, (
        "Frontend authentication quickstart failed.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
