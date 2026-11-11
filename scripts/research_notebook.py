"""research_notebook.py — Run deep research into a NotebookLM notebook safely,
and clean up duplicate sources left by the broken upstream CLI.

Why this script exists
----------------------
The upstream `notebooklm-py` CLI command
    notebooklm source add-research "<query>" --mode deep --import-all
wraps `client.research.import_sources()` in a retry loop that kicks in on
`RPCTimeoutError`. Unfortunately each retry re-imports the full source list
without deduping, so an IMPORT_RESEARCH RPC that times out N times leaves
N× duplicates in the notebook. Bug is tracked upstream as
`teng-lin/notebooklm-py` issue #241 (open).

The upstream docstring in `src/notebooklm/cli/helpers.py::import_with_retry`
explicitly acknowledges the escape hatch:

    "This is intentionally CLI-only policy. Library consumers calling
    `client.research.import_sources()` directly still get one-shot behavior."

This script takes that escape hatch: it drives the research flow through the
`notebooklm-py` Python library directly, with zero retries on IMPORT_RESEARCH,
so duplication literally cannot happen. It also exposes a `dedupe` subcommand
for cleaning up notebooks that have already been poisoned by the CLI bug.

Note on task_id mismatch: NotebookLM sometimes assigns a different task_id in
`research.poll()` than the one returned by `research.start()` for the same
operation. The poll loop handles this by comparing the query text — if it
matches our request, we adopt the polled task_id and proceed normally.

Usage
-----
    # Start deep web research and import every found source safely:
    python3 scripts/research_notebook.py run <notebook_id> "<query>"

    # Fast research, cap at 10 sources, preview without writing:
    python3 scripts/research_notebook.py run <notebook_id> "<query>" \
        --mode fast --max-sources 10 --dry-run

    # Clean up duplicate + error sources in an existing notebook:
    python3 scripts/research_notebook.py dedupe <notebook_id> --include-error

    # Non-interactive dedupe (safe for agents):
    python3 scripts/research_notebook.py dedupe <notebook_id> \
        --include-error --non-interactive

Prerequisites
-------------
    python3 scripts/notebooklm_setup.py --skip-login
    .venv/bin/notebooklm login   # once, in a real terminal
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path


# ── Auth pre-flight (mirrors fetch_notebook.py so agents see the same marker) ──


AUTH_ERROR_MARKER = "NOTEBOOKLM_AUTH_REQUIRED"
AUTH_EXIT_CODE = 2


def _notebooklm_auth_paths() -> list[Path]:
    """Candidate session-file locations, upstream-aware.

    Honors `NOTEBOOKLM_HOME` via `notebooklm.paths.get_storage_path()` when the
    upstream package is importable, and falls back to the legacy hard-coded
    locations under `~/.notebooklm` / `~/.config/notebooklm` otherwise.
    """
    paths: list[Path] = []
    try:
        from notebooklm.paths import get_storage_path  # type: ignore[import-not-found]
        paths.append(Path(get_storage_path()))
    except Exception:
        pass

    home = Path.home()
    legacy = [
        home / ".notebooklm" / "storage_state.json",
        home / ".config" / "notebooklm" / "storage_state.json",
        home / ".notebooklm" / "default" / "storage_state.json",
    ]
    for p in legacy:
        if p not in paths:
            paths.append(p)
    return paths


def check_auth_or_exit() -> None:
    """Exit with a distinctive marker if `notebooklm login` has not been run.

    Also honors the `NOTEBOOKLM_AUTH_JSON` env var (inline session JSON), which
    upstream `notebooklm-py` accepts as a substitute for a session file.
    """
    if os.environ.get("NOTEBOOKLM_AUTH_JSON"):
        return
    if any(path.exists() for path in _notebooklm_auth_paths()):
        return
    print(
        f"{AUTH_ERROR_MARKER}: No NotebookLM session found.\n"
        "Run this one-shot installer+login script first:\n"
        "  python3 scripts/notebooklm_setup.py --skip-login\n"
        "  .venv/bin/notebooklm login   # in a real terminal\n"
        "Alternatively, set NOTEBOOKLM_HOME to your session directory, "
        "or pass NOTEBOOKLM_AUTH_JSON with an inline session JSON.",
        file=sys.stderr,
    )
    raise SystemExit(AUTH_EXIT_CODE)


def _import_notebooklm_client():
    """Import NotebookLMClient lazily so --help works without the package."""
    try:
        from notebooklm import NotebookLMClient  # type: ignore[import-not-found]
    except ImportError as exc:
        print(
            f"{AUTH_ERROR_MARKER}: notebooklm-py is not installed.\n"
            "Run: python3 scripts/notebooklm_setup.py --skip-login",
            file=sys.stderr,
        )
        raise SystemExit(AUTH_EXIT_CODE) from exc
    return NotebookLMClient


# ── Helpers ────────────────────────────────────────────────────────────────────


def _log(msg: str) -> None:
    print(f">> {msg}", file=sys.stderr)


def _err(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)


def _research_payload(result):
    """Normalize SDK results, including nested sources, while retaining legacy dicts."""
    return result.to_public_dict() if hasattr(result, "to_public_dict") else result


def _source_url(source_obj) -> str | None:
    """Normalize a Source dataclass or dict into its URL (or None)."""
    if source_obj is None:
        return None
    if isinstance(source_obj, dict):
        return source_obj.get("url")
    return getattr(source_obj, "url", None)


def _source_title(source_obj) -> str:
    if isinstance(source_obj, dict):
        return source_obj.get("title") or source_obj.get("url") or "<untitled>"
    return getattr(source_obj, "title", None) or getattr(source_obj, "url", None) or "<untitled>"


def _dedupe_key(source, *, key_mode: str) -> str | None:
    """Return a stable grouping key, or None if this source should not be grouped."""
    url = _source_url(source)
    title = _source_title(source)
    if key_mode == "url":
        return f"url::{url}" if url else None
    if key_mode == "title":
        return f"title::{title}" if title else None
    # auto: prefer url, fall back to title
    if url:
        return f"url::{url}"
    if title and title != "<untitled>":
        return f"title::{title}"
    return None


# ── run subcommand ─────────────────────────────────────────────────────────────


async def _run_research(args: argparse.Namespace) -> int:
    """Wait for the selected research run and import deduplicated sources once."""
    NotebookLMClient = _import_notebooklm_client()

    from_storage_kwargs: dict = {}
    if args.profile:
        from_storage_kwargs["profile"] = args.profile

    async with await NotebookLMClient.from_storage(**from_storage_kwargs) as client:
        _log(
            f"Starting {args.mode} {args.source} research on notebook "
            f"{args.notebook_id}: {args.query[:80]}"
        )
        start_result = await client.research.start(
            args.notebook_id,
            args.query,
            source=args.source,
            mode=args.mode,
        )
        typed_response = hasattr(start_result, "to_public_dict")
        start_result = _research_payload(start_result)
        if not start_result or not isinstance(start_result, dict):
            _err(f"research.start returned unexpected payload: {start_result!r}")
            return 1
        task_id = start_result.get("task_id")
        if not task_id:
            _err(f"research.start did not return a task_id (got: {start_result!r})")
            return 1
        if typed_response:
            task_id = start_result.get("report_id") or task_id
        _log(f"Research task_id={task_id}; polling every {args.poll_interval}s "
             f"(timeout {args.poll_timeout}s)")

        # ── Poll loop ──────────────────────────────────────────────────────────
        # Current SDKs require a run ID to disambiguate retained research tasks.
        poll_kwargs = {"task_id": task_id} if typed_response else {}
        deadline = time.monotonic() + args.poll_timeout
        status_dict: dict = {}
        adopted_task_id = False
        while True:
            status_dict = _research_payload(
                await client.research.poll(args.notebook_id, **poll_kwargs)
            ) or {}
            # Guard: make sure we are tracking the task we started, not a
            # stale/concurrent one. The poll endpoint may return state for a
            # different task_id (e.g. if the notebook had a prior research run
            # still completing). If the ids mismatch we check whether the
            # polled task carries our query — NotebookLM sometimes assigns a
            # different task_id to the same research operation started by
            # research.start(). When the query matches we adopt the polled id.
            polled_task_id = status_dict.get("task_id")
            if polled_task_id and polled_task_id != task_id:
                polled_query = status_dict.get("query", "")
                if polled_query and polled_query == args.query:
                    if not adopted_task_id:
                        _log(
                            f"Poll returned task_id={polled_task_id!r} "
                            f"(differs from start() id {task_id!r}), but "
                            f"query matches — adopting polled id."
                        )
                        task_id = polled_task_id
                        adopted_task_id = True
                    # fall through to normal status handling below
                else:
                    _log(
                        f"Poll returned task_id={polled_task_id!r} (expected "
                        f"{task_id!r}); query mismatch — ignoring stale task."
                    )
                    if time.monotonic() >= deadline:
                        _err(
                            f"Polling timed out after {args.poll_timeout}s while "
                            f"waiting for our task_id={task_id!r} (poll keeps "
                            f"returning stale task_id={polled_task_id!r})."
                        )
                        return 1
                    await asyncio.sleep(args.poll_interval)
                    continue

            status = status_dict.get("status", "unknown")
            if status == "completed":
                break
            if status == "failed":
                _err(f"Research task {task_id!r} failed.")
                return 1
            # A newly started task may not be visible in the first polls yet.
            if time.monotonic() >= deadline:
                _err(
                    f"Polling timed out after {args.poll_timeout}s "
                    f"(last status: {status!r}). Re-run with a larger --poll-timeout."
                )
                return 1
            await asyncio.sleep(args.poll_interval)

        sources_found = status_dict.get("sources") or []
        _log(f"Research completed: {len(sources_found)} sources found")

        # ── Dedupe against existing notebook contents ──────────────────────────
        existing = await client.sources.list(args.notebook_id)
        existing_urls = {s.url for s in existing if getattr(s, "url", None)}
        before_count = len(existing)

        filtered: list[dict] = []
        skipped_duplicate = 0
        for src in sources_found:
            url = _source_url(src)
            if url and url in existing_urls:
                skipped_duplicate += 1
                continue
            filtered.append(src if isinstance(src, dict) else dict(src))  # type: ignore[arg-type]

        if skipped_duplicate:
            _log(
                f"Skipping {skipped_duplicate} sources already present in the notebook"
            )

        if args.max_sources is not None and args.max_sources > 0:
            if len(filtered) > args.max_sources:
                _log(
                    f"Capping import list: {len(filtered)} -> {args.max_sources}"
                )
                filtered = filtered[: args.max_sources]

        if not filtered:
            _log("Nothing to import (all discovered sources already present or filtered out).")
            if args.dry_run:
                print(json.dumps([], ensure_ascii=False))
            return 0

        if args.dry_run:
            plan = [
                {
                    "url": _source_url(s),
                    "title": _source_title(s),
                }
                for s in filtered
            ]
            _log(f"--dry-run: would import {len(plan)} sources")
            print(json.dumps(plan, ensure_ascii=False, indent=2))
            return 0

        # ── One-shot import via the library API (no retry loop) ────────────────
        _log(
            f"Importing {len(filtered)} sources via library API (one-shot; "
            "library consumers are NOT affected by the CLI retry duplication bug)."
        )
        imported = await client.research.import_sources(
            args.notebook_id, task_id, filtered
        )
        imported_count = len(imported) if imported else 0

        after = await client.sources.list(args.notebook_id)
        after_count = len(after)
        delta = after_count - before_count
        _log(
            f"Sources before: {before_count} -> after: {after_count} "
            f"(delta: +{delta}, import_sources reported: {imported_count})"
        )
        if delta > len(filtered):
            _err(
                f"Unexpected duplication detected: delta {delta} > requested "
                f"{len(filtered)}. Run `research_notebook.py dedupe {args.notebook_id}` "
                "to clean up."
            )
            return 1
        return 0


# ── dedupe subcommand ──────────────────────────────────────────────────────────


async def _run_dedupe(args: argparse.Namespace) -> int:
    NotebookLMClient = _import_notebooklm_client()

    from_storage_kwargs: dict = {}
    if args.profile:
        from_storage_kwargs["profile"] = args.profile

    async with await NotebookLMClient.from_storage(**from_storage_kwargs) as client:
        _log(f"Listing sources in notebook {args.notebook_id}...")
        sources = list(await client.sources.list(args.notebook_id))
        _log(f"Found {len(sources)} sources total")

        def _is_error(src_obj) -> bool:
            return getattr(src_obj, "status", None) == 3  # SourceStatus.ERROR

        seen: dict[str, object] = {}
        duplicates: list[tuple[object, str]] = []
        for src in sources:
            key = _dedupe_key(src, key_mode=args.key)
            if key is None:
                continue
            existing = seen.get(key)
            if existing is None:
                seen[key] = src
                continue
            # A keeper already exists for this key. Normally we keep the
            # first occurrence. But if the current keeper is error-state and
            # the new candidate is healthy, swap them — otherwise, running
            # with `--include-error` would delete BOTH the keeper (as error)
            # AND the healthy candidate (as duplicate-of-keeper), wiping the
            # entire group.
            if _is_error(existing) and not _is_error(src):
                duplicates.append(
                    (
                        existing,
                        f"demoted from keeper (error state); "
                        f"{getattr(src, 'id', '?')} is healthy",
                    )
                )
                seen[key] = src
            else:
                duplicates.append(
                    (src, f"duplicate of {getattr(existing, 'id', '?')}")
                )

        error_flagged: list[tuple[object, str]] = []
        if args.include_error:
            for src in sources:
                status = getattr(src, "status", None)
                if status == 3:  # SourceStatus.ERROR
                    error_flagged.append((src, "status=error"))

        # Build unique deletion set (prefer duplicate reason if same id shows up twice)
        to_delete: dict[str, tuple[object, str]] = {}
        for src, reason in duplicates + error_flagged:
            sid = getattr(src, "id", None)
            if not sid:
                continue
            to_delete.setdefault(sid, (src, reason))

        _log(
            f"Duplicates: {len(duplicates)} across {len(set(k for k in seen))} groups; "
            f"error sources: {len(error_flagged)}; total to delete: {len(to_delete)}"
        )

        if not to_delete:
            _log("Nothing to delete.")
            return 0

        plan_lines = [
            f"{sid}\t{getattr(src, 'title', None) or _source_url(src) or ''}\t"
            f"{_source_url(src) or ''}\t{reason}"
            for sid, (src, reason) in to_delete.items()
        ]

        if args.dry_run:
            for line in plan_lines:
                print(line)
            _log(f"--dry-run: would delete {len(to_delete)} sources")
            return 0

        if not args.non_interactive:
            print("Planned deletions (id\\ttitle\\turl\\treason):", file=sys.stderr)
            for line in plan_lines:
                print(f"  {line}", file=sys.stderr)
            answer = input(f"Delete {len(to_delete)} sources? [y/N] ").strip().lower()
            if answer not in ("y", "yes"):
                _log("Aborted by user.")
                return 0

        failures = 0
        for sid, (src, reason) in to_delete.items():
            try:
                await client.sources.delete(args.notebook_id, sid)
                _log(f"deleted {sid} ({reason})")
            except Exception as exc:  # pragma: no cover - network failure path
                failures += 1
                _err(f"failed to delete {sid}: {exc}")

        after = await client.sources.list(args.notebook_id)
        _log(
            f"before: {len(sources)} -> after: {len(after)} "
            f"(deleted: {len(to_delete) - failures}, failed: {failures})"
        )
        return 1 if failures else 0


# ── CLI ────────────────────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="research_notebook.py",
        description=(
            "Safe NotebookLM research driver for ObsidianDataWeave. "
            "Bypasses the upstream `notebooklm source add-research --import-all` "
            "CLI retry loop (teng-lin/notebooklm-py#241) by calling the "
            "`notebooklm-py` Python API directly. Also provides a dedupe "
            "subcommand for cleaning up notebooks already poisoned by the CLI bug."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # run ----------------------------------------------------------------------
    run_p = sub.add_parser(
        "run",
        help="Start deep/fast research and import findings one-shot (no retry duplication).",
        description=(
            "Start a research task on an existing NotebookLM notebook, wait for it "
            "to complete, dedupe results against the notebook's current source list, "
            "and import the findings via a single library call (no CLI retry loop)."
        ),
    )
    run_p.add_argument("notebook_id", help="NotebookLM notebook ID")
    run_p.add_argument("query", help="Research query (natural language)")
    run_p.add_argument(
        "--mode",
        choices=("fast", "deep"),
        default="deep",
        help="Research mode (default: deep)",
    )
    run_p.add_argument(
        "--source",
        choices=("web", "drive"),
        default="web",
        help="Source type (default: web; deep mode supports web only)",
    )
    run_p.add_argument(
        "--max-sources",
        type=int,
        default=None,
        help="Cap the number of sources to import (default: import every discovered source)",
    )
    run_p.add_argument(
        "--poll-interval",
        type=int,
        default=10,
        help="Seconds between research.poll() calls (default: 10)",
    )
    run_p.add_argument(
        "--poll-timeout",
        type=int,
        default=1800,
        help="Maximum total seconds to wait for research to complete (default: 1800)",
    )
    run_p.add_argument(
        "--profile",
        help="NotebookLM profile name (for multi-account setups)",
    )
    run_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Do everything except the final import_sources call; print the plan to stdout",
    )
    run_p.add_argument(
        "--non-interactive",
        action="store_true",
        help="Reserved for future prompts; the run subcommand is already non-interactive",
    )

    # dedupe -------------------------------------------------------------------
    dd_p = sub.add_parser(
        "dedupe",
        help="Remove duplicate (and optionally error-state) sources from a notebook.",
        description=(
            "List all sources in a notebook, group them by URL (or title fallback), "
            "and delete everything except the first occurrence of each group. "
            "Useful after an accidental run of `notebooklm source add-research "
            "--import-all` triggered the upstream duplication bug."
        ),
    )
    dd_p.add_argument("notebook_id", help="NotebookLM notebook ID")
    dd_p.add_argument(
        "--profile",
        help="NotebookLM profile name (for multi-account setups)",
    )
    dd_p.add_argument(
        "--key",
        choices=("auto", "url", "title"),
        default="auto",
        help="Dedupe key (default: auto — prefer url, fall back to title)",
    )
    dd_p.add_argument(
        "--include-error",
        action="store_true",
        help="Also delete sources whose status == error (3)",
    )
    dd_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the deletion plan but do not delete anything",
    )
    dd_p.add_argument(
        "--non-interactive",
        action="store_true",
        help="Skip the interactive confirmation prompt",
    )

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    check_auth_or_exit()

    runners = {
        "run": _run_research,
        "dedupe": _run_dedupe,
    }
    runner = runners.get(args.command)
    if runner is None:
        parser.error(f"unknown command: {args.command}")

    try:
        rc = asyncio.run(runner(args))  # type: ignore[misc]
    except SystemExit:
        raise
    except KeyboardInterrupt:
        _err("Interrupted by user")
        sys.exit(130)
    except Exception as exc:  # surface the full error chain; no silent retry
        _err(f"{type(exc).__name__}: {exc}")
        sys.exit(1)

    sys.exit(rc)


if __name__ == "__main__":
    main()
