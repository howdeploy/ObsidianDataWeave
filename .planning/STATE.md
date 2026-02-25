# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-25)

**Core value:** One command turns any research document into properly structured, linked atomic notes inside Obsidian
**Current focus:** Phase 2 complete — both plans done; ready for Phase 3 (vault-writer)

## Current Position

Phase: 3 of 4 (Writers)
Plan: 0 of 2 in current phase
Status: Phase 2 complete, Phase 3 not started
Last activity: 2026-02-26 — Phase 2 complete (verification passed 4/4), ready for Phase 3

Progress: [█████░░░░░] 50%

## Performance Metrics

**Velocity:**
- Total plans completed: 5
- Average duration: 2.2 min
- Total execution time: 0.2 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation | 3 | 6 min | 2 min |
| 02-ai-core | 2 | 5 min | 2.5 min |

**Recent Trend:**
- Last 5 plans: 01-01 (2 min), 01-02 (2 min), 01-03 (2 min), 02-01 (2 min), 02-02 (3 min)
- Trend: Consistent 2-3 min/plan

*Updated after each plan completion*
| Phase 01-foundation P02 | 3 | 2 tasks | 2 files |
| Phase 02-ai-core P01 | 2 | 2 tasks | 1 file |
| Phase 02-ai-core P02 | 3 | 2 tasks | 1 file |

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
- [Phase 02-ai-core 02-01]: SKILL.md uses runtime injection pattern — no embedded tags.yaml or rules content; atomize.py injects at call time
- [Phase 02-ai-core 02-01]: Two-pass wikilink strategy: enumerate all titles in Step 1, insert links in Step 3 using exact title strings — prevents broken wikilinks
- [Phase 02-ai-core 02-01]: Atom plan JSON schema locked at schema_version 1 — additions are breaking changes requiring version bump
- [Phase 02-ai-core 02-02]: Validation split: validate_atom_plan() hard errors (exit 1) vs. validate_tags/wikilinks() warnings (continue) — allows Claude's intentional semantic links
- [Phase 02-ai-core 02-02]: proposed-tags.md always created even when empty — prevents Phase 3 FileNotFoundError; append mode with date+source headers preserves history
- [Phase 02-ai-core 02-02]: config.toml absence falls back to default /tmp/dw/staging with stderr warning — graceful degradation, no crash

### Pending Todos

None yet.

### Blockers/Concerns

- lxml C dependency: verify `pip3 install python-docx` works without `pacman -S python-lxml` on Manjaro — document in install.sh if pacman needed
- Cyrillic filename handling: confirm content-hash dedup and slug generation work without encoding errors on Manjaro ext4

## Session Continuity

Last session: 2026-02-26
Stopped at: Completed 02-ai-core plan 02 (atomize.py created — Phase 2 complete)
Resume file: .planning/phases/03-vault-writer/03-01-PLAN.md
