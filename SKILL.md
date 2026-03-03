---
description: "Claude Code adapter for ObsidianDataWeave workflows"
trigger_phrases:
  - process note
  - enrich note
  - atomize note
  - docx import
  - обработай заметку
  - обработай документ
  - импортируй документ
  - zettelkasten правила
---

# ObsidianDataWeave Claude Adapter

Use the repo-local `AGENTS.md` as the primary contract.

## Intent Mapping

- Process a source `.docx` document:
  `python3 scripts/process.py "Document.docx"`
- Process a personal note:
  `python3 scripts/process_note.py "Note Title"`
- Run duplicate review:
  `python3 scripts/dedup_vault.py --dry-run`
- Validate setup:
  `python3 scripts/doctor.py`

## Rules
- Prefer the repository's `AGENTS.md`, `rules/*.md`, and script help output over global instructions.
- Treat this file as a Claude-specific entrypoint, not as the canonical source of project behavior.
- Reuse the same local commands that Codex would run from the repository.
