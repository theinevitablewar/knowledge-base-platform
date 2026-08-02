from types import SimpleNamespace

import pytest

from app.workers import tasks


def test_run_disposes_engine_after_success(monkeypatch):
    events = []

    async def operation():
        events.append("operation")

    async def dispose():
        events.append("dispose")

    monkeypatch.setattr(tasks, "engine", SimpleNamespace(dispose=dispose))

    tasks._run(operation())

    assert events == ["operation", "dispose"]


def test_run_disposes_engine_after_failure(monkeypatch):
    disposed = False

    async def operation():
        raise RuntimeError("failed")

    async def dispose():
        nonlocal disposed
        disposed = True

    monkeypatch.setattr(tasks, "engine", SimpleNamespace(dispose=dispose))

    with pytest.raises(RuntimeError, match="failed"):
        tasks._run(operation())

    assert disposed is True
