# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-25)

**Core value:** One command turns any research document into properly structured, linked atomic notes inside Obsidian
**Current focus:** Phase 4 executing — 04-01 complete, 04-02 next

## Current Position

Phase: 4 of 4 (Publish)
Plan: 1 of 2 in current phase
Status: Executing
Last activity: 2026-02-26 — 04-01 install.sh, LICENSE, .gitignore complete

Progress: [█████████░] 90%

## Performance Metrics

**Velocity:**
- Total plans completed: 7
- Average duration: 2.3 min
- Total execution time: 0.3 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation | 3 | 6 min | 2 min |
| 02-ai-core | 2 | 5 min | 2.5 min |
| 03-writers | 2 | 5 min | 2.5 min |

**Recent Trend:**
- Last 5 plans: 02-01 (2 min), 02-02 (3 min), 03-01 (3 min), 03-02 (2 min), 04-01 (2 min)
- Trend: Consistent 2-3 min/plan

*Updated after each plan completion*
| Phase 01-foundation P02 | 3 | 2 tasks | 2 files |
| Phase 02-ai-core P01 | 2 | 2 tasks | 1 file |
| Phase 02-ai-core P02 | 3 | 2 tasks | 1 file |
| Phase 03-writers P01 | 3 | 1 task | 1 file |
| Phase 03-writers P02 | 2 | 2 tasks | 3 files |
| Phase 04-publish P01 | 2 | 2 tasks | 3 files |

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
- [Phase 03-writers 03-01]: UTF-8 byte truncation (not char count) for filenames — Cyrillic = 2 bytes/char, 200B cap leaves margin within ext4's 255B limit
- [Phase 03-writers 03-01]: source_doc always double-quoted in frontmatter via string interpolation to handle colons in document titles (e.g. "Smart Connections: ...")
- [Phase 03-writers 03-01]: String interpolation over PyYAML for frontmatter — guarantees exact field order and quoting without external dependency
- [Phase 03-writers 03-02]: vault_writer.py hard-errors on missing config.toml — vault_path is required, no fallback (unlike generate_notes.py which has a staging fallback)
- [Phase 03-writers 03-02]: MOC files always overwritten (auto-generated, no manual edits expected) — prevents stale MOC accumulation on repeated runs
- [Phase 03-writers 03-02]: Registry updated atomically after all vault writes (single save_registry call) — prevents partial-write state corruption
- [Phase 03-writers 03-02]: Non-TTY auto-skip for conflict resolution — sys.stdin.isatty() detects Claude Code subprocess context and skips rather than hanging on input()
- [Phase 03-writers 03-02]: process.py uses subprocess (not direct imports) — each script remains independently callable and testable
- [Phase 04-publish 04-01]: pip --break-system-packages applied ONLY for pacman-managed systems (Arch/Manjaro) — other distros use plain pip3 install
- [Phase 04-publish 04-01]: Python 3.10 supported with tomli backport, warns but does not fail — install.sh installs tomli automatically for 3.10
- [Phase 04-publish 04-01]: grep -qF guard on CLAUDE.md prevents duplicate ObsidianDataWeave Pipeline skill registration on repeated installs
- [Phase 04-publish 04-01]: vault_path non-existence warns but does not fail — user may configure Obsidian vault after initial install

### Pending Todos

None yet.

### Blockers/Concerns

- lxml C dependency: RESOLVED — install.sh runs `sudo pacman -S --noconfirm python-lxml || true` before pip3 install python-docx for pacman systems; other distros use plain pip3
- Cyrillic filename handling: RESOLVED — UTF-8 byte truncation (200B) confirmed working on Manjaro ext4; generate_notes.py verified with Cyrillic test filenames

## Session Continuity

Last session: 2026-02-26
Stopped at: Completed 04-01-PLAN.md (install.sh, LICENSE, .gitignore)
Resume file: .planning/phases/04-publish/04-02-PLAN.md
