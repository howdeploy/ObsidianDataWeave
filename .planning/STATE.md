# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-25)

**Core value:** One command turns any research document into properly structured, linked atomic notes inside Obsidian
**Current focus:** Phase 2 planned — ready to execute

## Current Position

Phase: 2 of 4 (AI Core)
Plan: 0 of 2 in current phase
Status: Planned, ready to execute
Last activity: 2026-02-26 — Phase 2 planned (2 plans in 2 waves, verification passed)

Progress: [███░░░░░░░] 25%

## Performance Metrics

**Velocity:**
- Total plans completed: 3
- Average duration: 2 min
- Total execution time: 0.1 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation | 3 | 6 min | 2 min |

**Recent Trend:**
- Last 5 plans: 01-01 (2 min), 01-02 (2 min), 01-03 (2 min)
- Trend: Consistent 2 min/plan

*Updated after each plan completion*
| Phase 01-foundation P02 | 3 | 2 tasks | 2 files |

## Accumulated Context

### Decisions

- Architecture: Claude handles all understanding (atomization, tagging, linking); Python scripts handle all filesystem operations (staging, vault write, MOC management). Non-negotiable separation.
- Safety: All generation writes to /tmp/dw/staging/ first; vault_writer.py is the only component that touches the real vault.
- Methodology: MOC + Zettelkasten from two reference .docx files (Архитектура Второго мозга, Smart Connections) — rules distilled into rules/*.md in Phase 1.
- Schema: Frontmatter fields locked at v1: tags, date, source_doc, note_type. Treat additions as breaking changes.
- Config schema locked at v1: [vault] vault_path/notes_folder/moc_folder/source_folder, [rclone] remote/staging_dir, [processing] default_note_type — additions are breaking changes. (01-01)
- English-only tags with / separator: #tech/ai not #тех/ии — universal for GitHub package audience. 42 tags across 7 domains in tags.yaml v1. (01-01)
- python-docx is the only non-stdlib dependency — mammoth and python-frontmatter excluded per research findings. (01-01)
- Rules-as-instructions pattern: rules/*.md written as imperative Claude instructions, 400-600 words each, loadable as context block for Phase 2 SKILL.md. (01-03)
- Bilingual examples: EN rule instructions + RU content examples sourced from actual reference .docx files. (01-03)
- [Phase 01-foundation]: Architecture .docx has 3 H3 headings = 4 sections total; parser correct, plan assertion was wrong about heading count
- [Phase 01-foundation]: Table position injection uses id(p._p) XML element identity for accurate paragraph-table ordering in JSON output
- [Phase 01-foundation]: rclone remote name: strip trailing colon then reattach — handles both 'gdrive:' and 'gdrive' remote name formats

### Pending Todos

None yet.

### Blockers/Concerns

- lxml C dependency: verify `pip3 install python-docx` works without `pacman -S python-lxml` on Manjaro — document in install.sh if pacman needed
- Cyrillic filename handling: confirm content-hash dedup and slug generation work without encoding errors on Manjaro ext4

## Session Continuity

Last session: 2026-02-26
Stopped at: Phase 2 planned, ready for /gsd:execute-phase 2
Resume file: .planning/phases/02-ai-core/02-01-PLAN.md
