---
phase: 03-writers
plan: "02"
subsystem: writers
tags: [python, vault-writer, deduplication, pipeline, obsidian, registry, argparse]

# Dependency graph
requires:
  - phase: 03-writers
    plan: "01"
    provides: staging .md files with 4-field YAML frontmatter (tags/date/source_doc/note_type)
provides:
  - scripts/vault_writer.py — staging to vault copier with dedup registry and folder routing
  - scripts/process.py — full pipeline wrapper (fetch -> parse -> atomize -> generate -> write)
  - processed.json schema — per-user dedup registry (gitignored)
affects:
  - Phase 4 (if added): vault_writer.py is the designated vault write gate for all future phases

# Tech tracking
tech-stack:
  added: [shutil.copy2, tomllib]
  patterns:
    - "Hard error on missing config.toml: vault_path is required — no safe fallback for vault writes"
    - "Registry updated atomically after all vault writes complete (one save_registry call at end)"
    - "MOC-last sorting via _moc_sort_key(): (is_moc: int, filename: str) tuple sort"
    - "Non-TTY auto-skip: sys.stdin.isatty() guards interactive conflict resolution"
    - "Subprocess stdout chaining: each step's stdout becomes next step's input argument"
    - "Stderr passthrough: run() always forwards subprocess stderr to user; only stdout captured for chaining"

key-files:
  created:
    - scripts/vault_writer.py
    - scripts/process.py
  modified:
    - .gitignore

key-decisions:
  - "vault_writer.py is the sole script allowed to write to vault_path — non-negotiable architecture constraint per VAULT-04"
  - "MOC files always overwritten on conflict (auto-generated, no manual edits expected) — no conflict prompt for MOC"
  - "Registry updated atomically (single save_registry after all copies) — prevents partial-write corruption on crash"
  - "Non-TTY auto-skip: when stdin is not a TTY (Claude Code subprocess, CI), duplicates are silently skipped rather than blocking"
  - "process.py uses subprocess (not direct imports) — each script runs as an independent process for composability"
  - "proposed-tags.md excluded from vault write routing (not a note file) — filtered by name in staging glob"

patterns-established:
  - "Pipeline chaining contract: each script prints its output path to stdout; all diagnostics to stderr"
  - "Dedup key: (source_doc, title) pair — not content hash; matches frontmatter fields"
  - "processed.json registry schema v1: {source_doc, date, note_count, note_titles[]} per document"

requirements-completed:
  - VAULT-01
  - VAULT-02
  - VAULT-03
  - VAULT-04

# Metrics
duration: 2min
completed: 2026-02-26
---

# Phase 3 Plan 02: vault_writer.py and process.py — Writer Pipeline Completion Summary

**vault_writer.py copies staged .md files to the correct Obsidian vault subfolders by note_type with (source_doc, title) dedup registry (processed.json), interactive/auto conflict resolution, MOC-last sort, and atomic registry update; process.py wraps the full fetch-to-vault pipeline via subprocess chaining with --skip-fetch and --from-plan shortcuts**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-25T23:11:16Z
- **Completed:** 2026-02-25T23:14:13Z
- **Tasks:** 2 of 2
- **Files modified:** 3

## Accomplishments

- Implemented `vault_writer.py` (414 lines) as the sole vault-writing component per VAULT-04 architecture constraint
- Implemented `load_registry()`/`save_registry()`: processed.json dedup registry with (source_doc, title) keys, schema v1
- Implemented `parse_frontmatter()`: YAML block extraction with tag list handling and double-quote stripping
- Implemented `resolve_conflict()`: interactive skip/overwrite with `sys.stdin.isatty()` non-TTY auto-skip guard
- Implemented `get_vault_dest()`: routes atomic->notes_folder, moc->moc_folder, source->source_folder (fallback: notes_folder)
- Implemented `_moc_sort_key()`: ensures MOC files are always processed last via tuple sort (is_moc, filename)
- Registry updated atomically after all vault writes complete (single `save_registry()` call at end)
- Implemented `process.py` (194 lines) wrapping full pipeline: fetch_docx.sh -> parse_docx.py -> atomize.py -> generate_notes.py -> vault_writer.py
- `run()` helper captures subprocess stdout for chaining while always forwarding subprocess stderr to user
- `--skip-fetch` flag bypasses fetch step when .docx already in staging
- `--from-plan` flag skips fetch/parse/atomize — starts from atom plan JSON directly
- Added `processed.json` to `.gitignore` (per-user vault data, not for git)
- Verified: first run creates notes in correct folders; second run skips all atomic note duplicates (idempotent); MOCs overwritten on each run

## Task Commits

Each task was committed atomically:

1. **Task 1: Create vault_writer.py with dedup registry, conflict resolution, and folder routing** - `5d6d644` (feat)
2. **Task 2: Create process.py pipeline wrapper and update .gitignore** - `714ebae` (feat)

## Files Created/Modified

- `scripts/vault_writer.py` (414 lines) — Sole vault-writing component; routes staging .md files to vault subfolders by note_type; dedup via processed.json registry; interactive/auto conflict resolution; MOC written last; atomic registry update
- `scripts/process.py` (194 lines) — Full pipeline wrapper; chains 5 steps via subprocess stdout; --skip-fetch and --from-plan shortcuts; stderr passthrough for diagnostics
- `.gitignore` — Added `processed.json` entry with comment explaining why it is gitignored

## Decisions Made

- **vault_path hard error:** Unlike generate_notes.py which has a staging fallback, vault_writer.py cannot safely default — writing to the wrong path would corrupt the user's vault. Missing config.toml is exit(1).
- **MOC always overwrite:** MOC is auto-generated from the atom plan; expecting the user to never manually edit it. This avoids stale MOC accumulation on repeated runs.
- **Atomic registry update:** Save processed.json only after all `shutil.copy2` calls succeed. Prevents a state where the registry claims notes were written but some copies failed.
- **Non-TTY auto-skip:** Claude Code runs vault_writer.py as a subprocess. Blocking on `input()` would deadlock. `sys.stdin.isatty()` detects this and auto-skips rather than hanging.
- **process.py uses subprocess:** Each script remains independently callable and testable. Direct imports would couple the pipeline and prevent individual script reuse.
- **proposed-tags.md excluded:** The staging glob filters `proposed-tags.md` by name — it is not a Obsidian note and should not be routed to the vault.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None — no external service configuration required for vault_writer.py or process.py itself. Users must have `config.toml` configured (vault_path required for vault_writer.py).

## Phase 3 Complete

Phase 3 (Writers) is now fully complete:
- **Plan 01:** generate_notes.py — atom plan JSON -> staging .md files with 4-field YAML frontmatter
- **Plan 02:** vault_writer.py — staging .md files -> Obsidian vault subfolders with dedup and MOC-last ordering
- **Plan 02:** process.py — single command wrapping the full fetch-to-vault pipeline

The full pipeline is operational: `python3 scripts/process.py "Research.docx"` or `python3 scripts/process.py /path/to/atom-plan.json --from-plan`

## Self-Check: PASSED

- scripts/vault_writer.py: FOUND
- scripts/process.py: FOUND
- .gitignore contains processed.json: FOUND
- Commit 5d6d644: FOUND
- Commit 714ebae: FOUND

---
*Phase: 03-writers*
*Completed: 2026-02-26*
