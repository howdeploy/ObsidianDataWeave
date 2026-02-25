---
phase: 01-foundation
plan: "02"
subsystem: infra
tags: [rclone, python-docx, bash, json, docx, google-drive, parsing]

# Dependency graph
requires:
  - phase: 01-01
    provides: config.example.toml with locked [rclone] remote/staging_dir schema; scripts/ directory

provides:
  - scripts/fetch_docx.sh — rclone copyto shell script with config.toml integration and error handling
  - scripts/parse_docx.py — .docx to structured JSON parser with normalized heading levels
  - parse_docx_to_json(path) importable function for Phase 2 atomization pipeline

affects:
  - 01-03 (rules distillation reads parse_docx.py output for content)
  - 02-01 and beyond (Phase 2 atomization imports parse_docx_to_json)

# Tech tracking
tech-stack:
  added:
    - python-docx 1.2.0 (already installed from Plan 01-01 research)
    - tomllib stdlib (Python 3.11+) used in parse_config bash helper
    - rclone v1.73.0 with gdrive: remote
  patterns:
    - Config-driven rclone remote: read [rclone].remote from config.toml, never hardcode gdrive:
    - Dynamic heading normalization: detect min_level, offset all levels so min becomes 1
    - Staging-first: fetch_docx.sh writes to staging_dir before any vault operations
    - Safe subprocess pattern: list-form rclone args to handle Cyrillic+colon+space filenames

key-files:
  created:
    - scripts/fetch_docx.sh
    - scripts/parse_docx.py
  modified: []

key-decisions:
  - "Architecture doc (Архитектура Второго мозга) has exactly 3 H3 headings — plan assertion of >5 sections was incorrect for this document; 4 sections (pre-heading + 3 H3) is the correct parser output"
  - "Table injection uses paragraph position mapping via XML element identity (id(p._p)) to insert markdown tables at correct position in section flow"
  - "List item detection uses both style name matching (List Paragraph, List Bullet) and heuristic bullet/number prefix regex — covers docs where lists are Normal-style paragraphs"
  - "Image detection checks for w:drawing in paragraph XML — marks as [image] placeholder per user decision in CONTEXT.md"

patterns-established:
  - "Heading normalization: min_level = min(all heading levels in doc); normalized_level = raw_level - (min_level - 1)"
  - "fetch_docx.sh: remote name stripped of trailing colon then reattached: REMOTE_BASE=${RCLONE_REMOTE%:}; SOURCE=${REMOTE_BASE}:${FILENAME}"
  - "parse_docx_to_json is importable: use 'if __name__ == __main__' guard with argparse in main()"

requirements-completed:
  - DOCX-01
  - DOCX-02
  - DOCX-03

# Metrics
duration: 3min
completed: "2026-02-25"
---

# Phase 1 Plan 02: DOCX Fetch and Parse Pipeline Summary

**rclone fetch script (config.toml-driven, exit-code-3 error handling) and python-docx JSON parser with dynamic heading normalization — both reference .docx files produce structured JSON with H3-as-level-1 normalization and bold/italic markdown**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-25T18:10:49Z
- **Completed:** 2026-02-25T18:13:55Z
- **Tasks:** 2
- **Files modified:** 2 created

## Accomplishments

- scripts/fetch_docx.sh: 105-line bash script with `set -euo pipefail`, reads `[rclone] remote` and `staging_dir` from config.toml via tomllib one-liner, falls back to `gdrive:/tmp/dw/staging` with warning, handles Cyrillic+colon+space filenames via list-form rclone args, prints local path to stdout for piping, lists available .docx files on exit code 3
- scripts/parse_docx.py: 331-line Python parser exporting `parse_docx_to_json(path)` function, produces normalized JSON with `heading_depth_offset` traceability, converts runs to `**bold**`/`*italic*`/`***bold-italic***` markdown, detects list items by style and heuristic, injects tables as markdown at correct document position, marks images as `[image]` placeholders
- Both reference .docx files parse successfully: Architecture doc (4 sections, offset=2, 3 H3 headings) and Smart Connections doc (7 sections, offset=2, 1 H3 + 5 H4 headings) — heading normalization confirmed working (H3 → level 1, H4 → level 2)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create fetch_docx.sh rclone download script** - `5a59b38` (feat)
2. **Task 2: Create parse_docx.py structured JSON parser** - `184b7d5` (feat)

**Plan metadata:** *(docs commit follows)*

## Files Created/Modified

- `scripts/fetch_docx.sh` - rclone copyto wrapper reading config.toml; exit code 3 = file not found with Drive listing; stdout = local path for piping
- `scripts/parse_docx.py` - .docx → structured JSON; parse_docx_to_json importable; CLI with argparse; preserve Cyrillic via ensure_ascii=False

## Decisions Made

- Architecture .docx has exactly 3 H3 headings → 4 sections total (pre-heading + 3). The plan's verification assertion required `> 5 sections` which was incorrect for this document. The parser is correct; the document simply has 3 top-level headings. Verified and documented as deviation.
- Table position injection uses `id(p._p)` for paragraph identity (XML element pointer), mapped to sequential index, to determine where tables fall relative to paragraphs in the document flow.
- Used `${RCLONE_REMOTE%:}:${FILENAME}` pattern in shell to handle both `gdrive:` and `gdrive` remote name formats uniformly.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan verification assertion incorrect for Architecture .docx**
- **Found during:** Task 2 verification (parse_docx.py against reference files)
- **Issue:** Plan asserts `len(d['sections']) > 5` for the Architecture doc but the document has exactly 3 H3 headings (Часть 1, Часть 2, Как это будет работать) plus a pre-heading section = 4 sections total. The parser is correct; the assertion was wrong about the document's heading count.
- **Fix:** Verified the raw document structure with python-docx directly (all headings listed); confirmed 4 sections is the correct output; updated comprehensive assertions to use `== 4` for Architecture doc and `>= 6` for Smart Connections.
- **Files modified:** No script files modified — the parser is correct; only the test expectations were wrong.
- **Verification:** `python3 -c "... assert len(d['sections']) == 4 ..."` passes for Architecture; Smart Connections produces 7 sections and passes `>= 6`.
- **Committed in:** `184b7d5` (Task 2 commit — parser unchanged, deviation documented)

---

**Total deviations:** 1 (plan assertion error — parser correct)
**Impact on plan:** Parser produces accurate output for both reference documents. The `must_haves` truth "sections preserving heading hierarchy" is satisfied; the specific `> 5` count assertion was based on incorrect assumptions about heading count. No scope creep.

## Issues Encountered

None — all tooling (rclone, python-docx, tomllib) confirmed working from Plan 01-01 research. The heading count discrepancy was a plan assertion error, not an implementation issue.

## User Setup Required

None — no new external service configuration required. Users will have copied `config.toml` from `config.example.toml` per Plan 01-01 setup instructions. The scripts fall back gracefully to `gdrive:/tmp/dw/staging` if `config.toml` is absent.

## Next Phase Readiness

- `scripts/parse_docx.py` is ready for Plan 01-03 (rules distillation) — can parse both reference .docx files to extract content for `rules/atomization.md` and `rules/taxonomy.md`
- `parse_docx_to_json` is importable for Phase 2 atomization (`from scripts.parse_docx import parse_docx_to_json`)
- `scripts/fetch_docx.sh` is ready for live Drive downloads — tested with exit-code-3 error path (file not found)
- No blockers for Plan 01-03 (rules distillation)

---
*Phase: 01-foundation*
*Completed: 2026-02-25*
