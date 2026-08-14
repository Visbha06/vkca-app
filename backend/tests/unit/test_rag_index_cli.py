"""Event-loop lifecycle coverage for the RAG indexing CLI."""

import argparse
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from scripts import rag_index


@pytest.mark.asyncio
async def test_cli_run_and_engine_disposal_share_the_running_loop(monkeypatch) -> None:
    running_loop = asyncio.get_running_loop()
    observed_loops = []

    async def run(_args):
        observed_loops.append(asyncio.get_running_loop())
        return 0

    async def dispose():
        observed_loops.append(asyncio.get_running_loop())

    monkeypatch.setattr(rag_index, "_run", run)
    monkeypatch.setattr(rag_index, "engine", SimpleNamespace(dispose=dispose))

    exit_code = await rag_index._run_cli(argparse.Namespace())

    assert exit_code == 0
    assert observed_loops == [running_loop, running_loop]


@pytest.mark.asyncio
async def test_cli_disposes_engine_after_sanitized_failure(monkeypatch, capsys) -> None:
    async def fail(_args):
        raise RuntimeError("token=raw-secret")

    dispose = AsyncMock()
    monkeypatch.setattr(rag_index, "_run", fail)
    monkeypatch.setattr(rag_index, "engine", SimpleNamespace(dispose=dispose))

    exit_code = await rag_index._run_cli(argparse.Namespace())

    assert exit_code == 2
    dispose.assert_awaited_once_with()
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "failed"
    assert output["failure_code"] == "indexing_failed"
    assert "raw-secret" not in output["failure_message"]


def test_main_uses_one_top_level_asyncio_run(monkeypatch) -> None:
    args = argparse.Namespace()
    run = AsyncMock(return_value=0)
    asyncio_run_calls = []

    def asyncio_run(awaitable):
        asyncio_run_calls.append(awaitable)
        return 0

    monkeypatch.setattr(rag_index, "_parse_args", lambda: args)
    monkeypatch.setattr(rag_index, "_run_cli", run)
    monkeypatch.setattr(rag_index.asyncio, "run", asyncio_run)

    with pytest.raises(SystemExit) as raised:
        rag_index.main()

    assert raised.value.code == 0
    assert len(asyncio_run_calls) == 1
    asyncio_run_calls[0].close()
    run.assert_called_once_with(args)
