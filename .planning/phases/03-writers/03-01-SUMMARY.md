---
phase: 03-writers
plan: "01"
subsystem: writers
tags: [python, markdown, yaml-frontmatter, staging, obsidian, zettelkasten]

# Dependency graph
requires:
  - phase: 02-ai-core
    provides: atom plan JSON schema (schema_version 1) with notes array containing id/title/note_type/tags/source_doc/date/body/proposed_new_tags fields
provides:
  - scripts/generate_notes.py — renders atom plan JSON into .md files with YAML frontmatter in staging_dir
affects:
  - 03-02 (vault_writer.py reads .md files from staging_dir produced by generate_notes.py)
  - process.py pipeline wrapper (chains atomize.py → generate_notes.py → vault_writer.py)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "stdout/stderr separation: staging path on stdout for pipe chaining, all diagnostics on stderr"
    - "UTF-8 byte truncation for Cyrillic-safe filename limiting (200B cap, not char count)"
    - "String interpolation for YAML frontmatter (not PyYAML) to guarantee exact field order and quoting"
    - "source_doc always double-quoted in frontmatter to handle colons in document titles"

key-files:
  created:
    - scripts/generate_notes.py
  modified: []

key-decisions:
  - "UTF-8 byte truncation (not char count) for filename length: Cyrillic = 2 bytes/char, 200B cap leaves margin within ext4's 255B limit"
  - "source_doc always double-quoted via string interpolation to handle colons in titles like 'Smart Connections: ...'"
  - "String interpolation over PyYAML to control exact frontmatter field order and quoting format"
  - "staging_dir/filename deduplication left to vault_writer.py (Plan 02); generate_notes.py overwrites unconditionally"

patterns-established:
  - "Atom plan JSON contract: notes[].{id,title,note_type,tags,source_doc,date,body,proposed_new_tags}"
  - "Staging write pattern: mkdir -p staging_dir, write each note as {sanitize_filename(title)}.md"

requirements-completed:
  - VAULT-04

# Metrics
duration: 3min
completed: 2026-02-26
---

# Phase 3 Plan 01: generate_notes.py — Atom Plan to Markdown Renderer Summary

**Python script that reads Phase 2 atom plan JSON and renders each note into an Obsidian-compatible .md file with 4-field YAML frontmatter (tags/date/source_doc/note_type) in the staging directory, with Cyrillic-safe UTF-8 byte filename truncation and always-double-quoted source_doc for colon handling**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-25T23:07:43Z
- **Completed:** 2026-02-25T23:10:30Z
- **Tasks:** 1 of 1
- **Files modified:** 1

## Accomplishments
- Implemented `sanitize_filename()` replacing Obsidian-forbidden chars and truncating by UTF-8 bytes (200B) for safe Cyrillic filenames on ext4
- Implemented `render_note_md()` using string interpolation to produce locked 4-field frontmatter with always-double-quoted source_doc
- Implemented `load_config()` following atomize.py pattern: tomllib with /tmp/dw/staging fallback
- Script prints staging_dir path to stdout for process.py pipe chaining; all diagnostics to stderr
- Verified: 3 .md files generated, Cyrillic filenames readable, colon-in-source_doc correctly quoted, no vault_path reference

## Task Commits

Each task was committed atomically:

1. **Task 1: Create generate_notes.py with frontmatter rendering and filename sanitization** - `e592d8c` (feat)

**Plan metadata:** (docs: complete plan — pending)

## Files Created/Modified
- `scripts/generate_notes.py` - Reads atom plan JSON, sanitizes filenames, renders YAML frontmatter .md files to staging_dir; prints staging path to stdout

## Decisions Made
- **UTF-8 byte truncation:** Used `encoded[:200].decode("utf-8", errors="ignore")` not `title[:N]` — Cyrillic is 2 bytes/char so char-count truncation can exceed ext4's 255B filename limit
- **String interpolation over PyYAML:** Guarantees exact field order and quoting without external dependency; source_doc double-quoting via f-string escape is explicit and auditable
- **Always double-quote source_doc:** Documents like "Smart Connections: Интеллектуальный мозг.docx" contain colons that break YAML parsing if unquoted

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- generate_notes.py complete and verified; staging .md files ready for vault_writer.py (Plan 02)
- Contract: `python3 scripts/generate_notes.py <atom-plan.json>` prints staging_dir path to stdout for pipe chaining
- Plan 02 (vault_writer.py) can read all .md files from staging_dir and commit them to the real Obsidian vault with idempotency and folder routing

## Self-Check: PASSED

- scripts/generate_notes.py: FOUND
- .planning/phases/03-writers/03-01-SUMMARY.md: FOUND
- Commit e592d8c: FOUND

---
*Phase: 03-writers*
*Completed: 2026-02-26*
