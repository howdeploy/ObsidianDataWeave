# ObsidianDataWeave Agent Contract

## Purpose
This repository converts source `.docx` documents and existing Obsidian notes into Zettelkasten-style notes with MOC structure.

Agents should treat this file as the canonical integration contract for both Claude Code and Codex.

## Supported Workflows
1. Process a source document into atomic notes and MOC:
   `python3 scripts/process.py "Document.docx"`
   Safe automation form:
   `python3 scripts/process.py "Document.docx" --non-interactive --on-conflict skip`
2. Process an existing personal note in the vault:
   `python3 scripts/process_note.py "Note Title"`
   Safe automation form:
   `python3 scripts/process_note.py "Note Title" --mode atomize --non-interactive --on-conflict skip`
3. Generate markdown files from an existing atom plan JSON:
   `python3 scripts/generate_notes.py /path/to/atom-plan.json`
4. Copy staged markdown files into the vault:
   `python3 scripts/vault_writer.py --staging /path/to/staging --atom-plan /path/to/atom-plan.json`
5. Find duplicate note candidates or run semantic dedup:
   `python3 scripts/dedup_vault.py --dry-run`
6. Run environment checks before operating on the vault:
   `python3 scripts/doctor.py`

## Workflow Mapping
Common user intent -> command:

- "process/import this .docx" -> `python3 scripts/process.py "<file>.docx"`
- "process/import this .docx without prompts" -> `python3 scripts/process.py "<file>.docx" --non-interactive --on-conflict skip`
- "process/enrich/atomize this note" -> `python3 scripts/process_note.py "<note title or path>"`
- "atomize this note without prompts" -> `python3 scripts/process_note.py "<note title or path>" --mode atomize --non-interactive --on-conflict skip`
- "show duplicate candidates" -> `python3 scripts/dedup_vault.py --dry-run --skip-claude`
- "run full dedup review" -> `python3 scripts/dedup_vault.py`
- "write staged notes without prompts" -> `python3 scripts/vault_writer.py --staging "<dir>" --atom-plan "<plan.json>" --non-interactive --on-conflict skip`
- "run dedup without prompts" -> `python3 scripts/dedup_vault.py --non-interactive --decision skip`
- "render markdown from atom plan" -> `python3 scripts/generate_notes.py "<plan.json>"`
- "check setup/prereqs" -> `python3 scripts/doctor.py`

## Important Constraints
- `scripts/vault_writer.py` is the only script allowed to write generated note files into `vault_path`.
- `scripts/process.py` and `scripts/process_note.py` rely on the local `claude` CLI for the semantic rewrite step.
- Agents must prefer repo-local files over global home-directory files.
- `config.toml` is local, machine-specific state. Never overwrite it unless explicitly asked.
- `processed.json`, `dedup_reviewed.json`, staging artifacts, and vault contents are runtime state. Do not delete them unless explicitly asked.

## Required Local Files
- `config.toml`: local runtime configuration
- `tags.yaml`: canonical taxonomy
- `rules/atomization.md`: note-splitting rules
- `rules/taxonomy.md`: tags, MOC, wikilink rules
- `rules/personal_notes.md`: personal note rules
- `SKILL.md`: Claude-facing adapter over this contract
- `SKILL_PERSONAL.md`: prompt header for personal note processing

## CLI Contracts
- `scripts/process.py`
  - Input: `.docx` filename or atom plan JSON with `--from-plan`
  - Safe automation flags for final vault writes: `--non-interactive --on-conflict skip|overwrite`
  - Output: summary to stdout, diagnostics to stderr
- `scripts/process_note.py`
  - Input: note title, filename, or absolute path
  - Safe automation flags for atomize writes: `--non-interactive --on-conflict skip|overwrite`
  - Output: writes updated/generated notes into the vault
- `scripts/generate_notes.py`
  - Input: atom plan JSON
  - Output: staging directory path to stdout
- `scripts/vault_writer.py`
  - Input: `--staging`, optional `--atom-plan`
  - Safe automation flags: `--non-interactive --on-conflict skip|overwrite`
  - Output: summary to stdout and stderr
- `scripts/dedup_vault.py`
  - Input: vault notes from configured vault path
  - Safe automation flags: `--non-interactive --decision merge|keep|skip`
  - Output: diagnostics to stderr, updates vault on confirmed merges

## Recommended Agent Behavior
- Start with `python3 scripts/doctor.py` if setup is uncertain.
- Use `--dry-run` modes before destructive or high-impact operations.
- Prefer `--non-interactive` plus an explicit conflict/decision policy when running from an agent.
- Quote filenames with spaces or Cyrillic characters.
- When a task is unclear, inspect the relevant script help first.

## Validation Commands
- `pytest -q`
- `python3 scripts/process.py --help`
- `python3 scripts/process_note.py --help`
- `python3 scripts/dedup_vault.py --help`
- `python3 scripts/doctor.py`
