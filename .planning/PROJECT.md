# ObsidianDataWeave

## What This Is

CLI toolkit that turns research documents from Google Drive into structured, linked atomic notes in Obsidian. Claude Code skill fetches .docx files, splits them into atomic notes using MOC + Zettelkasten methodology, assigns tags and wikilinks, and writes results directly to the vault. Publishes as open-source on GitHub with one-command install.

## Core Value

One command turns any research document into properly structured, linked atomic notes inside Obsidian — no manual work.

## Requirements

### Validated

- ✓ Download .docx from Google Drive via rclone — v1.0
- ✓ Parse .docx preserving heading hierarchy, lists, tables — v1.0
- ✓ Split document into atomic notes (one idea, 150-600 words) — v1.0
- ✓ YAML frontmatter: tags, date, source_doc, note_type — v1.0
- ✓ Tags from canonical 42-tag taxonomy only — v1.0
- ✓ Wikilinks between atomic notes and MOCs — v1.0
- ✓ MOC file per document mirroring H1/H2 structure — v1.0
- ✓ Vault routing by note_type (atomic, moc, source) — v1.0
- ✓ Idempotent: no duplicates on second run — v1.0
- ✓ Staging-first safety: vault receives only final results — v1.0
- ✓ Rules from reference .docx files as Claude instructions — v1.0
- ✓ Config schema: vault_path, folders, rclone remote — v1.0
- ✓ Cross-platform install.sh (pacman/brew/apt/dnf) — v1.0
- ✓ Bilingual README with copy-paste Quick Start — v1.0
- ✓ Obsidian templates + Smart Connections config — v1.0

### Active

(No next milestone planned yet)

### Out of Scope

- Obsidian JS plugin — separate ecosystem, Claude Code skills are more powerful
- Reverse sync Obsidian → NotebookLM — one-directional flow
- Google Drive auto-monitoring — manual trigger is simpler and more reliable for v1
- Editing existing notes — append-only is safer, no risk of data loss
- Multi-vault support — one config per vault, run separately
- GUI/TUI interface — target audience is Claude Code CLI users

## Context

**Shipped:** v1.0 MVP (2026-02-26)
**Codebase:** 2,661 LOC across Python, Bash, Markdown, TOML, YAML
**Tech stack:** Python 3.10+ (python-docx, PyYAML), Bash (rclone), Claude Code (SKILL.md)
**Pipeline:** fetch_docx.sh → parse_docx.py → atomize.py → generate_notes.py → vault_writer.py

**Architecture:** Claude handles all understanding (atomization, tagging, linking); Python scripts handle all filesystem operations (staging, vault write, MOC management). Non-negotiable separation.

**Known tech debt (7 items):** README inline config examples show dead [processing] section, META-03 tag count spec mismatch, VAULT-03 dedup spec vs impl, minor cosmetics. See MILESTONES.md for full list.

## Constraints

- **Platform**: Linux (Manjaro primary), macOS/Debian compatible via install.sh
- **Dependencies**: python-docx, PyYAML, rclone, Claude Code
- **Obsidian**: Standard markdown, [[wikilinks]], YAML frontmatter
- **Schemas locked**: Frontmatter v1 (tags/date/source_doc/note_type), config v1 ([vault]+[rclone]), atom plan JSON schema_version 1 — additions are breaking changes

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| MOC + Zettelkasten methodology | User's research-backed choice, produces clusters on Obsidian graph | ✓ Good |
| One command, no review step | Fast flow over control; atomic notes are cheap to fix | ✓ Good |
| Full package on GitHub | Max community value: skills + templates + config + README | ✓ Good |
| Rules from .docx as reference | Two documents define note architecture, Claude follows at runtime | ✓ Good |
| Claude/Python separation | Claude thinks, Python writes — clean responsibility boundary | ✓ Good |
| Staging-first safety | All writes to /tmp/dw/staging/ first, vault_writer.py commits last | ✓ Good |
| String interpolation for frontmatter | Guarantees exact field order and quoting without PyYAML dep for rendering | ✓ Good |
| Subprocess chaining in process.py | Each script independently callable and testable | ✓ Good |
| English-only tags with / separator | Universal for GitHub audience, Obsidian-compatible hierarchy | ✓ Good |
| Bilingual EN+RU README in single file | One file, EN first, RU after separator — no maintenance overhead | ✓ Good |

---
*Last updated: 2026-02-26 after v1.0 milestone*
