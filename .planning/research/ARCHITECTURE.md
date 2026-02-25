# Architecture Research

**Domain:** Document-to-Obsidian-notes pipeline (Claude Code skills package)
**Researched:** 2026-02-25
**Confidence:** HIGH (architecture derived from project constraints + established patterns in this domain)

---

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     ENTRY POINT (Claude conversation)           │
│   User: "обработай Research-X.docx"                             │
│   Claude invokes skill → passes filename + config               │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                   INGESTION LAYER                                │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │  gdrive-fetch.sh — rclone copy gdrive:/{file} /tmp/dw/   │  │
│   └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │ .docx file on local disk
┌────────────────────────▼────────────────────────────────────────┐
│                   EXTRACTION LAYER                               │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │  parse_docx.py — python-docx → structured JSON           │  │
│   │  Preserves: headings (H1-H6), paragraphs, lists,         │  │
│   │  tables, bold/italic markers, document structure          │  │
│   └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │ structured JSON (sections + content)
┌────────────────────────▼────────────────────────────────────────┐
│                   AI ANALYSIS LAYER (Claude in-conversation)     │
│   ┌──────────────────┐  ┌──────────────────┐  ┌─────────────┐  │
│   │ Topic Extractor  │  │ Atomizer         │  │ MOC Planner │  │
│   │ (main themes,    │  │ (splits content  │  │ (identifies │  │
│   │  key concepts)   │  │  into 1-idea     │  │  hub topics)│  │
│   │                  │  │  chunks)         │  │             │  │
│   └──────────────────┘  └──────────────────┘  └─────────────┘  │
│   All three run as a single Claude prompt pass over the JSON     │
└────────────────────────┬────────────────────────────────────────┘
                         │ atom plan: [{title, body, tags, links, folder}]
┌────────────────────────▼────────────────────────────────────────┐
│                   NOTE GENERATION ENGINE                         │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │  generate_notes.py — render atom plan → .md files        │  │
│   │  Outputs: YAML frontmatter, body, [[wikilinks]], tags     │  │
│   └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │ .md file set (in /tmp/dw/staging/)
┌────────────────────────▼────────────────────────────────────────┐
│                   VAULT WRITER                                   │
│   ┌─────────────────────────┐  ┌──────────────────────────────┐ │
│   │  vault_writer.py        │  │  moc_manager.py              │ │
│   │  Place notes in vault   │  │  Create/update MOC hub files │ │
│   │  Dedup by title slug    │  │  Inject links to new notes   │ │
│   │  Never overwrite        │  │                              │ │
│   └─────────────────────────┘  └──────────────────────────────┘ │
└────────────────────────┬────────────────────────────────────────┘
                         │ files written to /mnt/sda1/KISA's Space/
┌────────────────────────▼────────────────────────────────────────┐
│                   CONFIGURATION + RULES LAYER (cross-cutting)    │
│   config.json — vault path, folder map, tag prefixes, templates │
│   rules/  — methodology rules loaded from reference .docx        │
└─────────────────────────────────────────────────────────────────┘
```

---

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| `gdrive-fetch.sh` | Download named file from Google Drive to local staging area | bash + rclone copy; validates file exists, returns local path |
| `parse_docx.py` | Convert .docx to structured JSON preserving hierarchy | python-docx; emits `{sections:[{heading, level, paragraphs, lists}]}` |
| AI Analysis Layer | Read structured JSON + rules, output atom plan | Claude in-conversation (not a script); called with SKILL.md instructions |
| `generate_notes.py` | Render atom plan entries to .md files with frontmatter | Python Jinja2 template or simple string rendering |
| `vault_writer.py` | Place .md files in correct vault folders; handle conflicts | Python; checks slug existence, never overwrites, logs new vs skipped |
| `moc_manager.py` | Create or append links to MOC hub notes | Python; loads existing MOC if present, adds link section, preserves body |
| `config.json` | All user-configurable settings | JSON; vault path, folder map, tag prefixes, staging dir |
| `install.sh` | One-command setup: checks deps, copies skills, creates config | bash; installs python-docx, sets up vault folders, writes default config |

---

## Recommended Project Structure

```
ObsidianDataWeave/
├── skills/                        # Claude Code skill definitions
│   ├── process-document/
│   │   └── SKILL.md               # Main orchestration skill (Claude reads this)
│   ├── fetch-from-drive/
│   │   └── SKILL.md               # Thin wrapper: "run gdrive-fetch.sh <name>"
│   └── update-moc/
│       └── SKILL.md               # Standalone MOC update skill
├── scripts/                       # Python + bash workers
│   ├── gdrive-fetch.sh            # rclone download
│   ├── parse_docx.py              # .docx → structured JSON
│   ├── generate_notes.py          # atom plan → .md files
│   ├── vault_writer.py            # staging → vault placement
│   └── moc_manager.py             # MOC create/update
├── rules/                         # Methodology rules (loaded by AI analysis)
│   ├── moc-zettelkasten.md        # Extracted + condensed from reference .docx files
│   └── note-templates.md          # YAML frontmatter schema, wikilink conventions
├── templates/                     # Obsidian vault templates
│   ├── atomic-note.md             # Template for atomic notes
│   └── moc-hub.md                 # Template for MOC files
├── config.json                    # User configuration
├── install.sh                     # One-command installer
└── README.md                      # Bilingual documentation
```

### Structure Rationale

- **skills/:** Keeps skill definitions separate from implementation scripts. Claude Code discovers skills by SKILL.md file. Each skill is a focused entry point — skills should be thin orchestrators, not logic holders.
- **scripts/:** All actual computation lives in Python/bash. This keeps AI analysis concern separate from file I/O concern. Scripts are testable without Claude.
- **rules/:** Extracted condensed rules from the two reference .docx files. Committed to the repo so they travel with the skill. Claude reads these during the AI analysis pass.
- **templates/:** Vault-ready Obsidian templates installable into the user's vault.

---

## Architectural Patterns

### Pattern 1: Skill-as-Orchestrator, Script-as-Worker

**What:** The SKILL.md defines the conversation flow and calls external scripts for mechanical work (downloading, parsing, writing). Claude does the creative/analytical work in-conversation; scripts do deterministic I/O work.

**When to use:** Always in a Claude Code skills context. Claude cannot reliably do file placement, dedup checks, or rclone calls — those are scripted. Claude excels at atomization decisions, title generation, tag inference, and wikilink suggestion.

**Trade-offs:** Requires that scripts exist and are executable. The boundary is clear: anything that requires reading the filesystem or running a CLI goes to a script; anything that requires understanding content stays with Claude.

**Skill boundary definition:**
```
Script does:                         Claude does:
- rclone copy                        - Read structured JSON
- python-docx parsing                - Decide atom boundaries
- File existence checks              - Generate note titles
- Slug dedup                         - Assign tags
- Writing .md to disk                - Suggest [[wikilinks]]
- MOC file append                    - Decide which MOC to link from
- Config loading                     - Apply methodology rules
```

### Pattern 2: Staging Directory as Contract

**What:** Scripts write to `/tmp/dw/staging/` as an intermediate zone. Claude reviews the staging output (or a summary of it) before vault_writer.py commits to the real vault. In yolo mode this review is skipped; in review mode Claude shows a preview first.

**When to use:** Critical for protecting the live vault from bad output. Even in yolo mode, staging provides a rollback point — user can inspect `/tmp/dw/staging/` before anything permanent happens.

**Trade-offs:** Adds one more step but prevents corrupting the vault. The staging contract means vault_writer.py is the only component that touches the vault — all other scripts are staging-scoped.

**Example:**
```
parse_docx.py     → /tmp/dw/staging/raw.json
generate_notes.py → /tmp/dw/staging/notes/*.md
vault_writer.py   → /mnt/sda1/KISA's Space/{folder}/{note}.md
```

### Pattern 3: Rules as Loaded Context (not hardcoded)

**What:** Methodology rules (MOC structure, Zettelkasten principles, tag taxonomy, folder mapping) live in `rules/*.md` files that are loaded into Claude's context during the AI analysis pass. Rules are not baked into SKILL.md — they're injected at runtime from the rules/ directory.

**When to use:** Always. This allows rules to evolve without changing the skill definition. User can tune the methodology by editing `rules/moc-zettelkasten.md`.

**Trade-offs:** Adds context length. Mitigated by keeping rules/ files concise and principle-based (not verbose). The two reference .docx files should be distilled into ~2-3KB of rules, not copied verbatim.

### Pattern 4: Append-Only Vault Writer

**What:** vault_writer.py never modifies existing notes. If a note with the same title slug exists, it logs the conflict and skips. MOC files are the only files that get appended to (new link entries added to a links section).

**When to use:** Always for v1. This protects existing notes from accidental overwrite. User edits are never destroyed.

**Trade-offs:** Duplicate content can accumulate if the same document is processed twice. Mitigated by logging what was skipped and by using deterministic slug generation (same document → same slugs → same conflicts).

---

## Data Flow

### Primary Request Flow

```
User: "обработай Research-AI-2026.docx"
    │
    ▼
SKILL.md reads config.json → gets vault path, staging dir, folder map
    │
    ▼
gdrive-fetch.sh "Research-AI-2026.docx"
    → rclone copy gdrive:/Research-AI-2026.docx /tmp/dw/Research-AI-2026.docx
    │
    ▼
parse_docx.py /tmp/dw/Research-AI-2026.docx
    → /tmp/dw/staging/raw.json
    (output: {doc_title, sections:[{heading, level, content:[]}]})
    │
    ▼
Claude reads: raw.json + rules/moc-zettelkasten.md + rules/note-templates.md
    → internal atom plan: [{title, body, tags, links, folder, moc_hint}]
    │
    ▼
generate_notes.py receives atom plan (via stdin or temp file)
    → /tmp/dw/staging/notes/{slug}.md  (one file per atom)
    → /tmp/dw/staging/plan.json        (for audit trail)
    │
    ▼
vault_writer.py /tmp/dw/staging/notes/ → /mnt/sda1/KISA's Space/
    → places each .md in correct folder per config folder_map
    → logs: created / skipped (exists) / error
    │
    ▼
moc_manager.py receives moc_hint list from plan.json
    → creates MOC file if not exists (from templates/moc-hub.md)
    → appends [[wikilinks]] to relevant MOC files
    │
    ▼
Claude reports summary to user:
    "Создано 12 заметок, обновлено 2 MOC, пропущено 1 (конфликт)"
```

### Config Loading Flow

```
config.json
    ├── vault_path       → vault_writer.py, moc_manager.py
    ├── staging_dir      → all scripts
    ├── gdrive_remote    → gdrive-fetch.sh
    ├── folder_map       → vault_writer.py (topic → folder name)
    ├── tag_prefix       → generate_notes.py
    └── default_moc      → moc_manager.py (fallback MOC if no hint)
```

### Key Data Contracts

1. **raw.json schema** (parse_docx.py output):
```json
{
  "doc_title": "...",
  "source_file": "...",
  "sections": [
    {
      "heading": "...",
      "level": 2,
      "content": ["paragraph text", "..."],
      "lists": [["item1", "item2"]]
    }
  ]
}
```

2. **atom plan schema** (Claude output → generate_notes.py input):
```json
[
  {
    "title": "Атомарная заметка: название",
    "slug": "atomarnaya-zametka-nazvanie",
    "body": "Markdown content...",
    "tags": ["#ИИ", "#инструменты"],
    "wikilinks": ["[[Obsidian MOC]]", "[[Smart Connections]]"],
    "folder": "Ресерч и исследования",
    "moc_hint": "AI Tools MOC"
  }
]
```

3. **YAML frontmatter schema** (generate_notes.py output):
```yaml
---
title: "Атомарная заметка: название"
date: 2026-02-25
tags: [ИИ, инструменты]
source: "Research-AI-2026.docx"
type: atomic
---
```

---

## Component Boundaries (what talks to what)

| Boundary | Communication Method | Notes |
|----------|---------------------|-------|
| SKILL.md → scripts | Bash subprocess calls | SKILL.md instructs Claude to run `python3 scripts/parse_docx.py {path}` |
| parse_docx.py → Claude | File: /tmp/dw/staging/raw.json | Claude reads the file contents |
| Claude → generate_notes.py | Stdin or temp file: /tmp/dw/staging/plan.json | Claude writes atom plan, script reads it |
| generate_notes.py → vault_writer.py | Directory: /tmp/dw/staging/notes/ | Shared staging contract |
| vault_writer.py → moc_manager.py | File: /tmp/dw/staging/plan.json (moc_hints) | moc_manager reads which MOCs need updating |
| All scripts → config.json | File read at startup | Each script loads config.json at startup |
| Claude → rules/ | File read into context | SKILL.md tells Claude to read rules/moc-zettelkasten.md |

---

## Suggested Build Order (dependency chain)

The dependency graph drives this order:

```
1. config.json + install.sh
        ↓ (everything reads config)
2. gdrive-fetch.sh
        ↓ (need a file to parse)
3. parse_docx.py
        ↓ (need raw.json to define AI prompt)
4. rules/ (distilled from reference .docx)
        ↓ (rules + raw.json = AI analysis prompt design)
5. SKILL.md (process-document) + AI analysis pass design
        ↓ (need atom plan schema to build renderer)
6. generate_notes.py
        ↓ (need .md files to write to vault)
7. vault_writer.py
        ↓ (need notes in vault to know what MOCs to update)
8. moc_manager.py
        ↓ (need all components to test end-to-end)
9. Integration test + README
```

**Build order implications for phases:**
- Phase 1 (Foundation): items 1-3 — fetch + parse, verify raw.json output
- Phase 2 (AI Core): items 4-5 — rules distillation + skill design + atom plan schema
- Phase 3 (Writers): items 6-8 — note rendering + vault placement + MOC management
- Phase 4 (Polish): item 9 — integration, install.sh hardening, README, templates

---

## Anti-Patterns

### Anti-Pattern 1: Putting Methodology Rules Inside SKILL.md

**What people do:** Embed all MOC + Zettelkasten methodology directly in the skill definition prompt.

**Why it's wrong:** Rules become immutable (require editing skill code to change). Users cannot tune methodology without touching the skill. The reference .docx content doesn't version separately.

**Do this instead:** Keep rules in `rules/*.md`, load them into context dynamically. SKILL.md says "read rules/moc-zettelkasten.md before analyzing."

---

### Anti-Pattern 2: Claude Writes Files Directly

**What people do:** Ask Claude to use the Write tool to place notes directly into the Obsidian vault.

**Why it's wrong:** Claude's Write tool doesn't do deduplication, folder validation, or conflict handling. One hallucinated title can overwrite an existing note. No audit trail.

**Do this instead:** Claude writes the atom plan to a staging JSON file. vault_writer.py handles all actual vault I/O with proper checks.

---

### Anti-Pattern 3: Processing the Full .docx as a Single Prompt

**What people do:** Convert .docx to raw text and dump the entire document into a single "atomize this" prompt.

**Why it's wrong:** Large documents (>20 pages) exceed useful context density. Quality degrades — Claude generates fewer, shallower atoms. No structural signal (headings become meaningless in raw text).

**Do this instead:** parse_docx.py preserves section hierarchy. AI analysis sees structured JSON with heading levels, which guides atomization boundaries. For very large documents (>50 sections), process section-by-section.

---

### Anti-Pattern 4: One Giant Script Doing Everything

**What people do:** Write a single `process.py` that downloads, parses, atomizes (with hardcoded rules), generates, and writes.

**Why it's wrong:** Cannot use Claude's judgment for the atomization step. Hardcoded rules can't be updated without code changes. Impossible to debug individual stages. No staging checkpoint.

**Do this instead:** The architecture above — separate scripts at each stage, Claude as the AI analysis layer, staging as the integration point.

---

## Skill Boundary: What Claude Does vs. What Scripts Do

This is the central design question for Claude Code skills architecture.

### Claude's Role (in-conversation, no scripts)

- Read `raw.json` and internalize document structure
- Read `rules/` methodology files
- Decide where atomic note boundaries are (not at every paragraph — at every *idea*)
- Generate note titles that are searchable and self-contained
- Infer tags from content (not just headings)
- Suggest `[[wikilinks]]` to other concepts (even if those notes don't exist yet — they'll be created)
- Identify which topic is a "hub" worthy of a MOC vs. which is an atomic note
- Decide `folder` assignment per note based on topic
- Write the atom plan JSON

### Scripts' Role (deterministic, no intelligence)

- Download files (rclone)
- Parse binary formats (python-docx)
- Render templates (Jinja2 or f-strings)
- Check file existence / slug collision
- Write files to disk
- Append to existing files (MOC updates)
- Load and validate config

**The skill boundary is: Claude handles all decisions requiring understanding. Scripts handle all decisions requiring filesystem state.**

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Google Drive | `rclone copy gdrive:/{filename} /tmp/dw/` | rclone must be pre-configured; fail fast if not |
| Obsidian vault | Direct filesystem write to vault path | No Obsidian API needed; vault is just a folder |
| Smart Connections | No active integration; passive | Smart Connections auto-indexes new .md files on Obsidian open — nothing to do |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Ingestion → Extraction | Local file path | gdrive-fetch returns path; parse_docx reads path |
| Extraction → AI | File: raw.json in staging | Claude reads file content via Read tool |
| AI → Generation | File: plan.json in staging | Claude writes JSON; generate_notes.py reads it |
| Generation → Writing | Directory: staging/notes/ | vault_writer iterates over all .md in staging |
| Writing → MOC | File: plan.json (moc_hints field) | moc_manager reads moc_hints, acts on each |
| All → Config | File: config.json | Loaded by each script independently at startup |

---

## Scaling Considerations

This is a single-user local tool, not a server. Scaling concerns are about document size, not concurrent users.

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1-20 page docs | Current architecture handles fine |
| 20-100 page docs | parse_docx.py should chunk sections; AI analysis may need section-by-section pass |
| 100+ page docs | Section-by-section processing with intermediate plan.json merging; Claude processes in batches |

### Scaling Priorities

1. **First bottleneck:** Context window — a 100-page document as raw JSON overflows useful analysis range. Fix: section chunking in parse_docx.py + iterative AI analysis per chunk.
2. **Second bottleneck:** Staging disk space — not a real concern on local disk with text files.

---

## Sources

- Project constraints from `/home/kosya/vibecoding/ObsidianDataWeave/.planning/PROJECT.md` — HIGH confidence (primary source)
- Claude Code skills architecture patterns — HIGH confidence (established pattern from existing skills in this codebase)
- python-docx library capabilities — HIGH confidence (well-established, stable library)
- rclone integration pattern — HIGH confidence (already in use via obsidian-gdrive-sync skill)
- Obsidian markdown/wikilinks/YAML frontmatter spec — HIGH confidence (documented standard)
- Zettelkasten + MOC methodology — MEDIUM confidence (derived from project context; specific rules pending distillation from reference .docx files)

---

*Architecture research for: ObsidianDataWeave — Document-to-Obsidian-notes pipeline (Claude Code skills)*
*Researched: 2026-02-25*
