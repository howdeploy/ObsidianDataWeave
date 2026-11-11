"""Research response compatibility without authentication or network calls."""

import argparse
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from scripts import research_notebook


@pytest.fixture
def client(monkeypatch):
    """Provide an asynchronous SDK client without authentication or network access."""
    api = SimpleNamespace(
        research=SimpleNamespace(start=AsyncMock(), poll=AsyncMock(), import_sources=AsyncMock()),
        sources=SimpleNamespace(list=AsyncMock()),
    )
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=api)
    context.__aexit__ = AsyncMock(return_value=False)
    factory = SimpleNamespace(from_storage=AsyncMock(return_value=context))
    monkeypatch.setattr(research_notebook, "_import_notebooklm_client", lambda: factory)
    return api


def research_args(**overrides):
    """Build research arguments with an immediate polling interval for tests."""
    return argparse.Namespace(**{
        "notebook_id": "notebook", "query": "SQLite FTS5", "source": "web", "mode": "deep",
        "profile": None, "poll_interval": 0, "poll_timeout": 10, "max_sources": None,
        "dry_run": False, **overrides,
    })


@pytest.mark.parametrize("typed", [False, True], ids=["legacy-dicts", "typed-sdk"])
@pytest.mark.parametrize("dry_run", [False, True], ids=["import", "dry-run"])
@pytest.mark.parametrize("empty_query", [False, True], ids=["query-present", "empty-query"])
def test_research_response_compatibility(client, capsys, typed, dry_run, empty_query):
    """Preserve source data and run IDs across response formats and import modes."""
    run_id = "report" if typed else "task"
    parsed_query = "" if empty_query else "SQLite FTS5"
    duplicate = {"url": "https://example.com/existing", "title": "Existing"}
    source = {"url": "https://www.sqlite.org/fts5.html", "title": "FTS5", "result_type": 1}
    report = {
        "url": "", "title": "Research report", "result_type": 5,
        "report_markdown": "# FTS5 findings", "research_task_id": run_id,
    }
    start = {
        "task_id": "task", "report_id": "report", "notebook_id": "notebook",
        "query": "SQLite FTS5", "mode": "deep",
    }
    pending = {"task_id": run_id, "status": "in_progress", "query": parsed_query}
    not_visible = {"status": "no_research", "tasks": []}
    completed = {
        "task_id": run_id, "status": "completed", "query": parsed_query,
        "sources": [duplicate, source, report],
    }
    if typed:
        try:
            from notebooklm.types import ResearchSource, ResearchStart, ResearchStatus, ResearchTask
        except ImportError:
            pytest.skip("Installed notebooklm-py does not expose typed research results")
        start = ResearchStart(**start)
        not_visible = ResearchTask.not_found(run_id)
        pending = ResearchTask(run_id, ResearchStatus.IN_PROGRESS, query=parsed_query)
        completed = ResearchTask(
            run_id, ResearchStatus.COMPLETED, query=parsed_query,
            sources=tuple(ResearchSource.from_public_dict(s) for s in completed["sources"]),
        )

    existing = SimpleNamespace(url=duplicate["url"])
    client.research.start.return_value = start
    client.research.poll.side_effect = [not_visible, pending, completed]
    client.research.import_sources.return_value = [{"id": "new"}, {"id": "report"}]
    client.sources.list.side_effect = [[existing], [existing, source, report]]

    assert asyncio.run(research_notebook._run_research(
        research_args(dry_run=dry_run, max_sources=1 if dry_run else None)
    )) == 0
    client.research.start.assert_awaited_once_with(
        "notebook", "SQLite FTS5", source="web", mode="deep",
    )
    assert client.research.poll.await_count == 3
    poll_kwargs = {"task_id": run_id} if typed else {}
    client.research.poll.assert_has_awaits([call("notebook", **poll_kwargs)] * 3)
    if dry_run:
        assert json.loads(capsys.readouterr().out) == [{"url": source["url"], "title": "FTS5"}]
        client.research.import_sources.assert_not_awaited()
        client.sources.list.assert_awaited_once_with("notebook")
    else:
        client.research.import_sources.assert_awaited_once_with("notebook", run_id, [source, report])
        assert client.sources.list.await_count == 2
        client.sources.list.assert_has_awaits([call("notebook"), call("notebook")])


@pytest.mark.parametrize("payload", [None, {}, {"query": "SQLite FTS5"}])
def test_invalid_start_response_still_stops_before_polling(client, payload):
    """Reject malformed start responses before polling or importing sources."""
    client.research.start.return_value = payload
    assert asyncio.run(research_notebook._run_research(research_args())) == 1
    client.research.poll.assert_not_awaited()
    client.research.import_sources.assert_not_awaited()


def test_invisible_task_still_obeys_poll_timeout(client, monkeypatch, capsys):
    """Bound the wait when a started task never becomes visible."""
    client.research.start.return_value = {"task_id": "task"}
    client.research.poll.return_value = {"status": "no_research", "tasks": []}
    times = iter([0, 11])
    monkeypatch.setattr(research_notebook, "time", SimpleNamespace(monotonic=lambda: next(times)))

    assert asyncio.run(research_notebook._run_research(research_args())) == 1
    assert "Polling timed out" in capsys.readouterr().err
    client.research.poll.assert_awaited_once_with("notebook")
    client.research.import_sources.assert_not_awaited()


@pytest.mark.parametrize("typed", [False, True], ids=["legacy-dicts", "typed-sdk"])
def test_failed_research_stops_without_retrying_or_importing(client, capsys, typed):
    """Report terminal failures immediately, including typed deep runs with no query."""
    run_id = "report" if typed else "task"
    start = {"task_id": "task"}
    failed = {"task_id": run_id, "status": "failed", "query": ""}
    if typed:
        try:
            from notebooklm.types import ResearchStart, ResearchStatus, ResearchTask
        except ImportError:
            pytest.skip("Installed notebooklm-py does not expose typed research results")
        start = ResearchStart("task", "report", "notebook", "SQLite FTS5", "deep")
        failed = ResearchTask(run_id, ResearchStatus.FAILED)
    client.research.start.return_value = start
    client.research.poll.side_effect = [failed]

    assert asyncio.run(research_notebook._run_research(research_args())) == 1
    error = capsys.readouterr().err
    assert "failed" in error
    assert "timed out" not in error
    poll_kwargs = {"task_id": run_id} if typed else {}
    client.research.poll.assert_awaited_once_with("notebook", **poll_kwargs)
    client.sources.list.assert_not_awaited()
    client.research.import_sources.assert_not_awaited()


def test_typed_fast_research_uses_task_id_without_report_id(client):
    """Retain task_id as the polling key when fast research has no report_id."""
    try:
        from notebooklm.types import ResearchStart, ResearchStatus, ResearchTask
    except ImportError:
        pytest.skip("Installed notebooklm-py does not expose typed research results")
    client.research.start.return_value = ResearchStart(
        "task", None, "notebook", "SQLite FTS5", "fast",
    )
    client.research.poll.return_value = ResearchTask("task", ResearchStatus.COMPLETED)
    client.sources.list.return_value = []

    assert asyncio.run(research_notebook._run_research(research_args(mode="fast"))) == 0
    client.research.poll.assert_awaited_once_with("notebook", task_id="task")
    client.research.import_sources.assert_not_awaited()
