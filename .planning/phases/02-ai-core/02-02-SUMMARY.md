---
phase: 02-ai-core
plan: "02"
subsystem: ai-orchestration
tags: [python, claude-cli, atomize, validation, json, wikilinks, tags]

# Dependency graph
requires:
  - phase: 02-ai-core-01
    provides: SKILL.md with atomization prompt and 6-step pipeline
  - phase: 01-foundation-03
    provides: tags.yaml, rules/atomization.md, rules/taxonomy.md
provides:
  - scripts/atomize.py — Python orchestrator that loads SKILL.md + rules + tags, calls Claude CLI, parses and validates atom plan JSON
  - validate_atom_plan() — validates required fields, note_type, tag count (2-5), MOC count (exactly 1), ID uniqueness
  - validate_tags() — identifies non-canonical tags not in tags.yaml (warning-level)
  - validate_wikilinks() — catches orphaned [[wikilink]] targets (warning-level)
  - write_proposed_tags() — always creates proposed-tags.md in staging (Phase 3 dependency)
  - --dry-run mode — prints assembled prompt without calling Claude
  - stdout piping — output path printed to stdout for Phase 3 chaining
affects:
  - 03-vault-writer (reads atom plan JSON from path printed to stdout)
  - 04-cli (invokes atomize.py as subprocess)

# Tech tracking
tech-stack:
  added: [PyYAML (already installed), tomllib (stdlib Python 3.11+), subprocess.run]
  patterns:
    - Runtime prompt injection: SKILL.md stays pure instructions; atomize.py injects tags + rules at call time
    - Defensive JSON extraction: strip markdown code fences before json.loads()
    - Two-tier validation: hard errors (exit 1) vs. warnings (stderr only, continue)
    - Always-create pattern: proposed-tags.md created even when empty to prevent Phase 3 FileNotFoundError

key-files:
  created:
    - scripts/atomize.py
  modified: []

key-decisions:
  - "Validation split: validate_atom_plan() errors are hard (exit 1); validate_tags() and validate_wikilinks() produce warnings only (Claude may intentionally use semantic links)"
  - "config.toml fallback: if config.toml missing, defaults to /tmp/dw/staging with stderr warning — no crash"
  - "tomllib: Python 3.11+ stdlib; graceful degradation to tomli fallback or default config if unavailable"
  - "proposed-tags.md append mode: new sections appended with date+source headers — preserves history across multiple runs"

patterns-established:
  - "Prompt assembly pattern: SKILL.md + atomization.md + taxonomy.md + tags list + document JSON as single prompt string"
  - "Pipe-friendly output: atom plan JSON path printed to stdout; all diagnostics to stderr"
  - "Validation before output: hard errors prevent writing invalid atom plans to staging"

requirements-completed:
  - LINK-03
  - LINK-04
  - DOCX-04
  - DOCX-05
  - META-01
  - META-02
  - META-03
  - META-04
  - LINK-01
  - LINK-02

# Metrics
duration: 3min
completed: 2026-02-26
---

# Phase 2 Plan 02: atomize.py Summary

**Python orchestrator that calls Claude CLI with SKILL.md + rules + tags.yaml to produce validated atom plan JSON, with wikilink/tag/structure validation and always-created proposed-tags.md**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-25T21:37:05Z
- **Completed:** 2026-02-25T21:40:00Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Created `scripts/atomize.py` (~270 lines Python) with 12 functions covering full orchestration pipeline
- All validation functions verified with 9 mock data test scenarios — all pass
- `--dry-run` mode confirmed working: prints assembled prompt (SKILL.md + rules + tags + document JSON) without calling Claude
- `proposed-tags.md` always created in staging even when no new tags proposed — prevents Phase 3 FileNotFoundError
- Output path printed to stdout enabling Phase 3 piping: `python3 scripts/atomize.py input.json | xargs python3 scripts/vault_writer.py`

## Task Commits

Each task was committed atomically:

1. **Task 1: Create atomize.py orchestrator** - `1fd59d6` (feat)
2. **Task 2: Validate with unit tests** - inline validation only, no files modified

**Plan metadata:** pending (docs: complete plan)

## Files Created/Modified

- `scripts/atomize.py` — Python orchestrator: load_config, load_tags, load_skill_md, load_rules, assemble_prompt, call_claude, extract_json, validate_atom_plan, validate_tags, validate_wikilinks, write_proposed_tags, main()

## Decisions Made

- Validation split: `validate_atom_plan()` errors exit 1; `validate_tags()` and `validate_wikilinks()` warn-only so Claude's intentional semantic links don't block execution
- `config.toml` absence gracefully falls back to default `/tmp/dw/staging` with stderr warning — no crash
- `tomllib` from Python 3.11 stdlib; graceful degradation to `tomli` fallback or default config if unavailable
- `proposed-tags.md` uses append mode with date+source headers to preserve history across multiple atomize.py runs

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Self-Check: PASSED

All files exist and commits verified:
- `scripts/atomize.py` — FOUND
- `.planning/phases/02-ai-core/02-02-SUMMARY.md` — FOUND
- commit `1fd59d6` — FOUND

## Next Phase Readiness

- Phase 3 (vault-writer) can now receive atom plan JSON via: `python3 scripts/atomize.py <parsed.json> | xargs python3 scripts/vault_writer.py`
- `proposed-tags.md` always exists in staging — no FileNotFoundError risk in Phase 3
- Atom plan schema validated before output — Phase 3 can trust the JSON structure
- Phase 2 complete: SKILL.md (plan 01) + atomize.py (plan 02) form the complete AI core

---
*Phase: 02-ai-core*
*Completed: 2026-02-26*
