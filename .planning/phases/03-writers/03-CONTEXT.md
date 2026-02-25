# Phase 3: Writers - Context

**Gathered:** 2026-02-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Render the atom plan JSON from Phase 2 into .md files in staging, then commit them to the real Obsidian vault with correct folder routing, idempotency (no duplicates on re-run), and MOC file management. Also create a pipeline wrapper script (process.py) that chains the entire fetch → parse → atomize → write flow.

</domain>

<decisions>
## Implementation Decisions

### Folder Routing
- Flat structure inside each folder: all atomic notes in notes_folder, all MOCs in moc_folder — no subfolders
- Folders are defined in config.toml: notes_folder, moc_folder, source_folder
- Follows Zettelkasten methodology: navigation via wikilinks and MOC-hubs, not folder hierarchy
- File naming: title as-is (Cyrillic filenames for Russian notes, spaces preserved)
- PARA structure explicitly not used (mentioned as optional in reference docs, not adopted)

### Idempotency & Deduplication
- Duplicate detection: by source_doc + title (check frontmatter of existing files in vault)
- On conflict (note with same source_doc + title already exists): interactive prompt — user decides skip/overwrite per file
- JSON registry (processed.json) tracks all processed documents: {source_doc, date, note_count, note_titles} per document — fast lookup without vault scanning
- Registry stored in project directory (not in vault)

### MOC Management
- MOC always overwritten on re-run — MOC is auto-generated, manual edits not expected
- MOC created last (after all atomic notes written)
- One MOC per processed document

### Staging → Vault Process
- Write strategy: Claude's discretion (batch vs incremental)
- Logging: summary-level output ("Created 7 notes + 1 MOC, skipped 2 duplicates") — not per-file verbose
- Staging cleanup: Claude's discretion
- Pipeline wrapper: process.py (one command for the full chain: fetch → parse → atomize → write), but individual scripts remain callable separately for flexibility

### Claude's Discretion
- Special character handling in filenames (: / ? etc.) — replacement strategy
- Filename length limit (Cyrillic = 2 bytes/char on ext4)
- Write strategy (batch all-or-nothing vs incremental)
- Staging cleanup after successful vault write
- proposed-tags.md storage location (vault root vs project dir)

</decisions>

<specifics>
## Specific Ideas

- Claude Code is the primary consumer of these scripts — it runs them in sequence when user says "process this document"
- process.py wraps the full pipeline but each step (fetch, parse, atomize, write) stays independently callable
- Interactive conflict resolution via stdin (skip/overwrite) works naturally in Claude Code's subprocess model
- processed.json registry enables quick "already processed?" check without scanning vault frontmatter

</specifics>

<deferred>
## Deferred Ideas

- MOC update/append mode (LINK-V2-01) — v2, currently overwrite only
- Batch processing of a folder of .docx files (DOCX-V2-02) — v2
- Cross-document wikilinks (LINK-V2-02) — v2, requires vault scanning

</deferred>

---

*Phase: 03-writers*
*Context gathered: 2026-02-26*
