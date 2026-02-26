# Roadmap: ObsidianDataWeave

## Overview

Four phases, each blocked on the previous. Phase 1 locks the config and schema decisions that every other component reads. Phase 2 builds the Claude skill that does all the thinking. Phase 3 builds the Python writers that do all the vault writing. Phase 4 hardens the install and publishes to GitHub. Nothing ships until the full pipeline works end-to-end.

## Phases

- [x] **Phase 1: Foundation** - Config, schema, rclone fetch, .docx parser, rules extraction (completed 2026-02-25)
- [x] **Phase 2: AI Core** - SKILL.md, atomization, tagging, wikilinks, MOC planning (completed 2026-02-26)
- [x] **Phase 3: Writers** - Note generation, vault placement, MOC management, idempotency (completed 2026-02-26)
- [x] **Phase 4: Publish** - Install script, README, Obsidian templates, GitHub release (completed 2026-02-26)
- [ ] **Phase 5: Publish Fixes** - PyYAML dependency, README typo, dead config cleanup (gap closure)

## Phase Details

### Phase 1: Foundation
**Goal**: The config schema is locked, .docx files can be fetched from Google Drive and parsed into structured JSON, and rules distilled from reference documents are in place for Claude to follow
**Depends on**: Nothing (first phase)
**Requirements**: CONF-01, CONF-02, CONF-03, RULE-01, RULE-02, RULE-03, DOCX-01, DOCX-02, DOCX-03
**Success Criteria** (what must be TRUE):
  1. Running the fetch script with a Google Drive filename downloads the .docx to /tmp/dw/staging/ and reports success or a clear error
  2. Running parse_docx.py on the downloaded file produces a structured JSON file preserving H1/H2/H3 heading hierarchy, lists, and paragraphs
  3. A config.toml with vault_path and rclone remote is read at startup; a config.example.toml is committed to git with no real paths
  4. A tags.yaml canonical taxonomy exists with 30-50 tags covering the user's vault topics
  5. rules/*.md files exist containing distilled methodology from the two reference .docx files, ready to be loaded into Claude context
**Plans:** 3 plans

Plans:
- [x] 01-01-PLAN.md — Config schema, tags.yaml taxonomy, project structure scaffold
- [x] 01-02-PLAN.md — rclone fetch script and .docx parser (structured JSON output)
- [x] 01-03-PLAN.md — Rules extraction from reference .docx files into rules/*.md

### Phase 2: AI Core
**Goal**: The Claude skill can read a parsed JSON document plus rules and produce a complete atom plan — a structured list of atomic notes with titles, bodies, tags, wikilinks, and MOC hints — ready for Phase 3 to render
**Depends on**: Phase 1
**Requirements**: DOCX-04, DOCX-05, META-01, META-02, META-03, META-04, LINK-01, LINK-02, LINK-03, LINK-04
**Success Criteria** (what must be TRUE):
  1. Claude processes a parsed JSON document and produces an atom plan JSON where every note is 150-600 words and covers exactly one idea
  2. Every note in the atom plan has YAML frontmatter fields (tags, date, source_doc, note_type) with tags drawn only from tags.yaml taxonomy
  3. Wikilinks in the atom plan reference only note titles that exist within the same run, with 3-7 links per note maximum
  4. The atom plan includes a MOC entry that mirrors the source document's H1/H2 structure as a two-level hierarchy
**Plans:** 2 plans

Plans:
- [x] 02-01-PLAN.md — SKILL.md with atomization prompt, processing steps, guardrails, and few-shot example
- [x] 02-02-PLAN.md — atomize.py orchestrator with prompt assembly, Claude invocation, and atom plan validation

### Phase 3: Writers
**Goal**: The atom plan produced in Phase 2 is rendered to .md files in staging, then committed to the real Obsidian vault with correct folder routing, idempotency, and MOC files created or updated
**Depends on**: Phase 2
**Requirements**: VAULT-01, VAULT-02, VAULT-03, VAULT-04
**Success Criteria** (what must be TRUE):
  1. Running the full pipeline on a real .docx file creates .md files in the correct Obsidian vault subfolders (MOCs in one folder, atomic notes in another)
  2. Running the same pipeline twice on the same document does not create duplicate notes — existing notes are skipped by source_doc + title registry
  3. A MOC file is created for the processed document linking all generated atomic notes, organized by the source document's heading structure
  4. No files are written directly to the vault — all generation goes through /tmp/dw/staging/ first, vault_writer.py commits last
**Plans:** 2 plans

Plans:
- [x] 03-01-PLAN.md — generate_notes.py: atom plan JSON to .md files in staging with YAML frontmatter and filename sanitization
- [x] 03-02-PLAN.md — vault_writer.py (staging to vault with dedup registry and folder routing) + process.py (full pipeline wrapper)

### Phase 4: Publish
**Goal**: A new user can install ObsidianDataWeave with a single command, run their first document through the pipeline following the README, and the GitHub repository contains no hardcoded personal paths or secrets
**Depends on**: Phase 3
**Requirements**: DIST-01, DIST-02, DIST-03, DIST-04
**Success Criteria** (what must be TRUE):
  1. Running `bash install.sh` on a clean Manjaro system installs all dependencies, creates a config from config.example.toml, and registers the Claude Code skill — with no manual edits required to run the first import
  2. The README contains copy-paste commands a user sends to Claude that walk through setup and first document import with no ambiguity
  3. The GitHub repo includes Obsidian vault templates (starter folder structure, MOC hub examples, atomic note examples) and a Smart Connections config ready to drop into any vault
  4. `git log --follow -- config.toml` returns no commits — personal config is gitignored, only config.example.toml is tracked
**Plans:** 2 plans

Plans:
- [ ] 04-01-PLAN.md — install.sh cross-platform installer, MIT license, .gitignore hardening
- [ ] 04-02-PLAN.md — Bilingual README with Quick Start, Obsidian templates, Smart Connections config

### Phase 5: Publish Fixes
**Goal**: All audit gaps closed — PyYAML declared as dependency and installed, README references correct script names, dead config key removed
**Depends on**: Phase 4
**Requirements**: DIST-01, DIST-02
**Gap Closure**: Closes gaps from v1.0 milestone audit
**Success Criteria** (what must be TRUE):
  1. `pip install -r requirements.txt` on a clean system installs PyYAML (no ModuleNotFoundError on `import yaml`)
  2. `bash install.sh` installs PyYAML alongside python-docx
  3. README.md references `scripts/parse_docx.py` (not `parse_doc.py`) in both EN and RU sections
  4. No `[processing]` section in config.example.toml (or a script reads it — dead config removed)
**Plans:** 1 plan

Plans:
- [ ] 05-01-PLAN.md — PyYAML dependency fix, README typo fix, dead config cleanup

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 3/3 | Complete | 2026-02-25 |
| 2. AI Core | 2/2 | Complete | 2026-02-26 |
| 3. Writers | 2/2 | Complete | 2026-02-26 |
| 4. Publish | 2/2 | Complete | 2026-02-26 |
| 5. Publish Fixes | 0/1 | Not started | - |
