# Phase 4: Publish - Context

**Gathered:** 2026-02-26
**Status:** Ready for planning

<domain>
## Phase Boundary

A new user can install ObsidianDataWeave with a single command, run their first document through the pipeline following the README, and the GitHub repository contains no hardcoded personal paths or secrets. Also create Obsidian vault templates and MIT license.

</domain>

<decisions>
## Implementation Decisions

### README Structure
- Bilingual EN+RU in a single file (sections on both languages)
- Brief introduction to MOC + Zettelkasten methodology (1-2 paragraphs), then practical instructions
- Quick Start section: 2-3 copy-paste commands for Claude Code (1. Install, 2. Configure, 3. Process a document)
- Minimum explanations — user copies commands into Claude Code and it handles the rest

### install.sh Scope
- Cross-platform: Linux (pacman/apt/dnf) + macOS (brew) — detect package manager automatically
- Installs rclone if not present (via package manager or official script)
- Installs python-docx via pip
- Creates config.toml from config.example.toml interactively — prompts for vault_path and rclone remote name
- Automatically registers SKILL.md as a Claude Code skill
- Creates vault folders (notes_folder, moc_folder, source_folder) in the configured vault if they don't exist

### Obsidian Templates
- Starter vault structure with folders (Notes, MOCs, Sources) included in repo under templates/
- Example notes: 1 atomic note + 1 MOC — English language, showing proper frontmatter and wikilinks format
- Smart Connections config: Claude's discretion (ready JSON config or text recommendations in README)

### Security & Portability
- MIT license
- .gitignore: Claude's discretion (comprehensive list beyond config.toml and processed.json)
- Security audit approach: Claude's discretion (automated grep scan or robust .gitignore only)
- No git push in this phase — user tests locally first, pushes manually after verifying the pipeline works on their Obsidian vault

### Claude's Discretion
- Smart Connections config format (JSON file vs README text)
- Full .gitignore list (beyond the two already gitignored files)
- Security audit approach (grep scan vs .gitignore-only)
- install.sh error handling and rollback on failure
- README section ordering and formatting

</decisions>

<specifics>
## Specific Ideas

- User explicitly wants to test the full pipeline on their own Obsidian vault before any GitHub push
- Claude Code is the primary interface — README commands should be optimized for copy-paste into Claude Code
- install.sh should be idempotent — safe to re-run without breaking existing config

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-publish*
*Context gathered: 2026-02-26*
