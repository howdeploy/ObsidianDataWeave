# ObsidianDataWeave

Convert `.docx` research documents and existing Obsidian notes into Zettelkasten-style atomic notes with MOC structure.

Works with **Claude Code** and **Codex** out of the box.

## Install

```bash
git clone https://github.com/<user>/ObsidianDataWeave.git
cd ObsidianDataWeave
bash install.sh --vault-path "/path/to/your/obsidian/vault"
```

Or tell Claude Code:

> Clone github.com/\<user\>/ObsidianDataWeave and run `bash install.sh --vault-path "/path/to/vault"`

### Install modes

| Mode | Flag | What it does |
|------|------|-------------|
| **claude** (default) | `--mode claude` | Deps + config + registers global skill in `~/.claude/` |
| **codex** | `--mode codex` | Deps + config + verifies `AGENTS.md` |
| **local** | `--mode local` | Deps + config only |

### Options

- `--vault-path "/path"` — absolute path to your Obsidian vault
- `--rclone-remote name:` — rclone remote for Google Drive (default: `gdrive:`)

## Usage

After install, use from **any directory**:

```bash
# Process an existing note (enrich or atomize)
python3 scripts/process_note.py "Note Title"

# Import a .docx document
python3 scripts/process.py "Document.docx"

# Preview without changes
python3 scripts/process_note.py "Note Title" --dry-run

# Safe automation (no prompts)
python3 scripts/process.py "Doc.docx" --non-interactive --on-conflict skip

# Dedup review
python3 scripts/dedup_vault.py --dry-run

# Check setup
python3 scripts/doctor.py
```

Or just tell Claude / Codex: `"process note My Note"`, `"import document Research.docx"`.

## How it works

1. **Enrich** — takes a short note, adds frontmatter, tags from `tags.yaml`, wikilinks to existing vault notes
2. **Atomize** — splits a long note into atomic notes (1 idea = 1 note, 150-600 words) + creates a MOC
3. **Import .docx** — parses document, atomizes sections, generates notes + MOC, writes to vault

The semantic rewrite step uses the local `claude` CLI. Only `vault_writer.py` writes to the vault.

## Repository structure

```
AGENTS.md           # Canonical agent contract (Claude Code + Codex)
SKILL.md            # Claude-specific adapter
SKILL_PERSONAL.md   # Prompt header for personal note processing
scripts/            # Pipeline entrypoints
rules/              # Atomization, taxonomy, personal note rules
templates/          # Note and MOC templates
tags.yaml           # Canonical tag taxonomy
config.example.toml # Configuration template
tests/              # Regression tests
```

## Requirements

- Python 3.10+
- `claude` CLI in PATH (for semantic rewriting)
- `rclone` (optional, for Google Drive .docx fetching)
