---
phase: 01-foundation
plan: "03"
subsystem: infra
tags: [markdown, rules, zettelkasten, moc, obsidian, atomization, taxonomy]

# Dependency graph
requires:
  - phase: 01-01
    provides: tags.yaml with canonical 42-tag English taxonomy and rules/ directory

provides:
  - rules/atomization.md — 557-word operating instructions for Claude: 1-idea-per-note principle, 150-600 word constraints, noun-phrase titles, splitting heuristics, 2 few-shot examples from Smart Connections docx
  - rules/taxonomy.md — 601-word operating instructions for Claude: tags.yaml reference, 2-5 tags per note, 3-7 wikilinks, MOC structure, locked v1 YAML frontmatter schema (tags/date/source_doc/note_type), bilingual example

affects:
  - 02 (Phase 2 SKILL.md loads both rules files as Claude operating instructions)
  - all-phases (frontmatter schema locked at v1 — additions are breaking changes)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Rules-as-instructions pattern: rules/*.md written as imperative Claude instructions (not documentation), loadable into context
    - Few-shot bilingual examples: EN rules + RU examples sourced from actual reference .docx content

key-files:
  created:
    - rules/atomization.md
    - rules/taxonomy.md
  modified: []

key-decisions:
  - "Rules distilled directly from .docx content — not invented — atomization examples sourced from Smart Connections vector embeddings section"
  - "taxonomy.md few-shot example uses bilingual content per user decision (EN rules, RU example note body)"
  - "Frontmatter schema confirmed locked at v1: tags, date, source_doc, note_type — no additional fields"

patterns-established:
  - "Rules-as-instructions: Claude operating rules written in imperative mood, scoped to 400-600 words, loadable as context block"
  - "Bilingual examples: EN rule instructions + RU content examples from actual reference documents"

requirements-completed:
  - RULE-01
  - RULE-02
  - RULE-03

# Metrics
duration: 2min
completed: "2026-02-25"
---

# Phase 1 Plan 03: Rules Distillation Summary

**Atomic note rules (atomization.md) and taxonomy rules (taxonomy.md) distilled from two reference .docx files into 557+601-word Claude operating instructions with bilingual few-shot examples**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-25T18:11:04Z
- **Completed:** 2026-02-25T18:12:53Z
- **Tasks:** 2
- **Files modified:** 2 created

## Accomplishments

- rules/atomization.md: core principle (1 idea = 1 note), hard constraints (150-600 words, noun-phrase titles, self-contained), 4 splitting trigger conditions, 2 few-shot examples (good atomic note + bad broad note with fix) sourced from Smart Connections .docx
- rules/taxonomy.md: tag selection rules (2-5 per note, domain/subtag from tags.yaml, auto-expansion to proposed-tags.md), wikilink rules (3-7 per note, [[Note Title]], semantic not keyword), MOC structure (one per document, heading hierarchy), locked v1 frontmatter schema, complete bilingual example note
- Both files written as imperative Claude instructions ("Assign 2-5 tags", "Link only to note titles produced within the same processing run"), not as documentation

## Task Commits

Each task was committed atomically:

1. **Task 1: Distill atomization.md from reference .docx files** - `1a06682` (feat)
2. **Task 2: Distill taxonomy.md from reference .docx files** - `7658742` (feat)

**Plan metadata:** *(docs commit follows)*

## Files Created/Modified

- `rules/atomization.md` — 557 words: one-idea-per-note principle, 150-600 word constraints, noun-phrase title rule, 4 splitting heuristics, 2 few-shot examples from Smart Connections reference
- `rules/taxonomy.md` — 601 words: tag rules with tags.yaml reference, wikilink rules (3-7 per note), MOC structure, locked YAML frontmatter v1 schema, bilingual example note

## Decisions Made

- Rules distilled directly from .docx content — content was parsed during this session; examples use actual Smart Connections plugin features (vector embeddings, semantic search, Smart Chat, pricing)
- Bilingual format implemented as planned: English imperative instructions, Russian example content from "Архитектура Второго мозга" and "Smart Connections" documents
- taxonomy.md frontmatter schema confirms the STATE.md decision: fields locked at v1 (tags, date, source_doc, note_type) — any addition is a breaking change

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.
Phase 2 SKILL.md will load both rules files into Claude context via @rules/atomization.md and @rules/taxonomy.md includes.

## Next Phase Readiness

- rules/atomization.md ready for Phase 2 SKILL.md to load as operating instructions for note splitting
- rules/taxonomy.md ready for Phase 2 SKILL.md to load as operating instructions for tagging and linking
- Both files reference tags.yaml (already committed in Plan 01-01) — no missing dependencies
- All three Phase 1 plans complete — Phase 2 can begin

---
*Phase: 01-foundation*
*Completed: 2026-02-25*

## Self-Check: PASSED

- rules/atomization.md: FOUND
- rules/taxonomy.md: FOUND
- 01-03-SUMMARY.md: FOUND
- commit 1a06682 (Task 1): FOUND
- commit 7658742 (Task 2): FOUND
