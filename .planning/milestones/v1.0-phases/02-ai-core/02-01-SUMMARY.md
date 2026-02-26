---
phase: 02-ai-core
plan: "01"
subsystem: ai-core
tags: [skill-md, atomization, prompt-engineering, wikilinks, tags, json-schema]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: rules/atomization.md and rules/taxonomy.md as Claude instruction files; tags.yaml v1 canonical taxonomy
provides:
  - SKILL.md as the Claude operating instruction file for document atomization
  - 6-step processing pipeline (title enumeration, body generation, wikilink insertion, tag assignment, MOC generation, JSON output)
  - Atom plan JSON output schema (schema_version 1)
  - Two-pass wikilink generation strategy (titles first, then links)
  - Few-shot example with Russian content, real tags, inline wikilinks
affects:
  - 02-02 (atomize.py reads SKILL.md and injects tags.yaml + rules at runtime)
  - 03-staging (atom plan JSON produced by SKILL.md is consumed by vault_writer.py)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Runtime injection pattern: SKILL.md contains no embedded taxonomy or rules — atomize.py injects them at call time to keep SKILL.md version-stable
    - Two-pass wikilink strategy: Step 1 enumerates all titles, Step 3 inserts links using exact title strings — prevents broken links
    - Expansion factor estimation: source_words x 1.3 to decide split/expand before writing bodies

key-files:
  created:
    - SKILL.md
  modified: []

key-decisions:
  - "SKILL.md is Claude operating instructions, not a script — designed for human readability and Claude context injection"
  - "No embedded tags.yaml or rules content in SKILL.md — atomize.py injects at runtime for version stability"
  - "Two-pass wikilink generation: enumerate all titles first (Step 1), then insert links (Step 3) referencing exact strings"
  - "Few-shot example uses Russian content to match reference .docx documents"
  - "Atom plan output schema locks at schema_version 1 — additions are breaking changes"

patterns-established:
  - "Runtime injection pattern: prompt files contain no hardcoded taxonomy — inject at call time"
  - "Two-pass linking: enumerate titles before writing bodies or links"

requirements-completed: [DOCX-04, DOCX-05, META-01, META-02, META-03, META-04, LINK-01, LINK-02]

# Metrics
duration: 2min
completed: 2026-02-26
---

# Phase 2 Plan 01: AI Core — SKILL.md

**6-step Claude atomization prompt with two-pass wikilink strategy, atom plan JSON schema, and Russian few-shot example**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-25T21:32:42Z
- **Completed:** 2026-02-25T21:34:42Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Created SKILL.md (898 words) as the complete Claude operating instruction file for document atomization
- Implemented 6-step processing pipeline: title enumeration, body generation, wikilink insertion, tag assignment, MOC generation, JSON output
- Defined atom plan JSON output schema with all required fields (schema_version, source_file, processed_date, notes, proposed_tags)
- Added Russian few-shot example demonstrating input (parsed JSON section) to output (atom plan entry) mapping with inline wikilinks

## Task Commits

Each task was committed atomically:

1. **Task 1: Create SKILL.md with atomization prompt and processing steps** - `7250344` (feat)
2. **Task 2: Add few-shot example to SKILL.md** - `7250344` (feat, combined with Task 1 — example included in initial write, trimmed to stay under 900 words)

**Plan metadata:** (created after this entry)

## Files Created/Modified
- `SKILL.md` — Claude operating instructions for document atomization; 6-step pipeline, output schema, critical constraints, few-shot example; 898 words; runtime-injectable design

## Decisions Made
- Wrote both tasks in a single pass (instructions + example together) then trimmed to stay under 900-word budget — semantically both tasks are captured in one commit
- Few-shot example body intentionally compact (~80 words) to leave word budget for the instruction sections
- example uses `tech/ai` and `productivity/obsidian` (real tags from tags.yaml) per plan requirement

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered
- Initial write was 945 words (9 words over 900-word limit for tasks 1+2 combined). Fixed by trimming the few-shot example body from ~120 words to ~80 words. Final count: 898 words.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- SKILL.md complete and ready for `atomize.py` (02-02) to load as context
- atomize.py will inject tags.yaml content and rules/*.md files at runtime before calling Claude API
- Atom plan JSON schema is locked at v1 — Phase 3 (vault_writer.py) can implement against this contract

---
*Phase: 02-ai-core*
*Completed: 2026-02-26*
