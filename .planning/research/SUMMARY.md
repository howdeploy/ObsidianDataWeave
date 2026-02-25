# Project Research Summary

**Project:** ObsidianDataWeave
**Domain:** Document-to-Obsidian automation — CLI/Claude Code skill toolkit (.docx → MOC + Zettelkasten atomic notes)
**Researched:** 2026-02-25
**Confidence:** MEDIUM overall (web search unavailable during research; based on strong domain knowledge and project-specific analysis)

## Executive Summary

ObsidianDataWeave fills a genuine gap: no existing tool covers the full ingestion pipeline from external documents (NotebookLM exports, Google Docs) into a properly structured Obsidian vault. Smart Connections and Obsidian Copilot operate on notes *already in* the vault — they don't ingest. The recommended approach is a layered pipeline: rclone pulls the .docx from Google Drive, python-docx extracts structured JSON preserving heading hierarchy, Claude performs the intelligent atomization and planning in-conversation (no API calls needed), and deterministic Python scripts handle all vault I/O. This clean separation of "understanding" (Claude) from "file operations" (scripts) is the central architectural principle that makes the tool both safe and effective.

The key risk is quality drift: without explicit constraints, AI-generated notes tend toward either micro-fragments or overlong summaries, tags proliferate into hundreds of uncategorized variants, and wikilinks become noise. All three failures share a common root — missing upfront schema decisions. The mitigation is to define the frontmatter schema, tag taxonomy, atomization word-count guardrails, and wikilink density limits *before* writing any generation code, and to enforce them through prompt constraints and post-processing validation rather than relying on the model to self-regulate. The staging directory pattern (all scripts write to /tmp first, vault writer commits last) protects the live vault from bad output at every stage.

The second significant risk is GitHub publishability: the project starts as a personal tool wired to specific paths and rclone remote names. Publishing without explicit portability design means every user hits the same errors. This should be treated as a first-class design requirement, not an afterthought — config.example.json, auto-detection of rclone remotes, and a zero-to-first-note README walkthrough are table stakes for the GitHub package, not polish.

## Key Findings

### Recommended Stack

The stack is Python-first and intentionally lean. Python 3.11+ is pre-installed on Manjaro and hosts the best .docx + markdown ecosystem. No Node.js, no database, no LangChain — the splitting logic is deterministic (heading-based), Claude handles semantic decisions in-conversation, and rclone is already configured for Drive access.

**Core technologies:**
- `python-docx 1.1.x`: Parse .docx preserving heading levels (H1/H2/H3), paragraphs, lists, tables — the only library that gives structural metadata needed for atomization decisions; mammoth is the fallback for edge cases only
- `PyYAML 6.0.x`: Write YAML frontmatter blocks; `allow_unicode=True` handles Cyrillic titles; `safe_dump()` with block style enforced
- `Click 8.1.x`: CLI entry point with auto-generated `--help`, decorator syntax for `--vault-path`, `--source-file`, `--dry-run` flags
- `Rich 13.x`: Terminal progress output — essential UX for a tool that creates 20-50 notes per run
- `python-frontmatter 3.x`: Read existing notes for idempotency checks (merge frontmatter without destroying edits)
- `rclone` (system): Google Drive fetch via subprocess — already configured, no Python wrapper needed
- `tomllib` (stdlib, Python 3.11+): Config parsing for `~/.config/obsidian-dataweave/config.toml`

**What not to use:** docx2txt (strips structure), textract (unmaintained, C deps), Apache Tika (JVM overhead), LangChain (deterministic splitting doesn't need it), watchdog (auto-sync is out of scope for v1), SQLite (frontmatter field suffices for state tracking).

**Version risk:** mammoth and python-frontmatter versions are unverified (web search unavailable). Run `pip3 index versions python-docx mammoth python-frontmatter` before pinning in requirements.txt. lxml (python-docx C dependency) may need `pacman -S python-lxml` on Manjaro.

### Expected Features

**Must have — table stakes (v1):**
- Google Drive download via rclone — the pipeline entry point; without it, users manually download files
- .docx parsing with heading-aware splitting — H1→H2→H3 hierarchy drives atomization granularity
- Atomic note creation with YAML frontmatter — `tags`, `date`, `source_doc`, `note_type` fields; locked schema v1
- Wikilink injection via mention-matching — two-pass: create all notes (pass 1), inject links (pass 2); 3-7 links per note maximum
- MOC file generation — the signature differentiator; indexes all notes from one source document; hierarchical MOC (max 2 levels)
- Vault path + subfolder routing config — `Ресерч и исследования/Атомарные заметки/` for notes, `Ресерч и исследования/MOC/` for hubs
- Idempotency — skip existing notes by content hash; never overwrite user edits
- One-command install — `bash install.sh` that auto-detects rclone remote, prompts for vault path, installs dependencies
- Progress/verbose logging — per-note status + summary ("12 created, 2 MOC updated, 1 skipped")

**Should have (v1.x, add after core validated):**
- LLM-driven atomization — upgrade from heading splits to true 1-idea-per-note; trigger when users report notes too large
- Tag inference from content — constrained to canonical taxonomy; propose unknown tags to `proposed-tags.md` rather than silently inventing
- Dry-run / preview mode — `--dry-run` flag shows note titles + tag counts without writing; builds trust before first real run
- Zettelkasten ID in frontmatter — timestamp UID for permanent addressing; low risk, low effort

**Defer to v2+:**
- Semantic concept link suggestion — expensive LLM O(n²) pass; only worth it after basic wikilinks are validated
- Configurable rule documents — formalize the reference .docx methodology into user-editable rule files
- Multi-source batch processing — process a folder of .docx files; defer until single-doc flow is solid

**Hard anti-features (never build):**
- Editing existing notes — data loss risk with no recovery path; append-only from tool's perspective
- Real-time vault watching / auto-sync daemon — daemon complexity + silent failures; manual trigger is the right model
- Obsidian plugin (JS) — entirely different tech stack; Claude Code skill is more powerful and doesn't require the plugin API

### Architecture Approach

The architecture is a five-layer pipeline with staging as the safety contract. Each layer has a single responsibility: Ingestion (rclone fetch), Extraction (python-docx → structured JSON), AI Analysis (Claude in-conversation reads JSON + rules, writes atom plan), Note Generation (Python renders atom plan to .md files in staging), Vault Writing (vault_writer.py and moc_manager.py commit from staging to real vault). Claude handles all decisions requiring understanding; scripts handle all decisions requiring filesystem state. This is non-negotiable — Claude's Write tool has no deduplication or conflict handling; vault_writer.py does.

**Major components:**
1. `gdrive-fetch.sh` — rclone copy to /tmp/dw/staging/; validates file exists, returns local path
2. `parse_docx.py` — .docx → structured JSON `{sections:[{heading, level, content, lists}]}`; preserves H1-H3 hierarchy
3. AI Analysis Layer (SKILL.md + rules/*.md) — Claude reads raw.json + methodology rules, outputs atom plan JSON `[{title, slug, body, tags, wikilinks, folder, moc_hint}]`
4. `generate_notes.py` — renders atom plan to .md files with YAML frontmatter in staging/notes/
5. `vault_writer.py` — places .md files in vault per config folder_map; append-only, content-hash dedup
6. `moc_manager.py` — creates/updates MOC hub files; reads moc_hints from plan.json; max 2-level hierarchy
7. `config.json` (user) / `config.example.json` (git) — vault path, gdrive remote, folder map, tag prefix, staging dir
8. `rules/*.md` — distilled methodology from reference .docx files; loaded dynamically into Claude context; user-editable

**Project structure:** `skills/process-document/SKILL.md`, `scripts/` (Python workers), `rules/` (methodology), `templates/` (Obsidian vault templates), `install.sh`, `README.md`.

### Critical Pitfalls

1. **Note atomization extremes (too granular or too broad)** — Define concrete guardrail upfront: 150-600 words per atomic note, noun-phrase titles (not full sentences), 0 links = flag for review. Use the reference .docx files' own examples as few-shot examples in the prompt. Address in Phase 1 prompt engineering.

2. **Tag explosion and taxonomy drift** — Ship a `tags.yaml` canonical taxonomy (30-50 tags max) as part of the toolkit. Skill must load it at runtime; AI proposes unknown tags to `proposed-tags.md` instead of silently inventing. Enforce lowercase hyphenated format in post-processing. Address before first document is processed.

3. **MOC becoming stale or over-hierarchical** — Design MOC update as first-class operation: every import run scans existing MOCs and appends new links. Hard limit: max 2 levels of MOC hierarchy. MOC files contain only links + 1-2 sentence context per link, never content. Address in architecture phase; verify with multi-run integration test.

4. **Wikilink noise and broken links** — Hard cap of 3-7 wikilinks per note in prompt. Links only to concepts that are the primary subject of an existing note. Build link-target index from vault before generating links. Use one naming convention (Title Case, no dates in filename) enforced in both note creation and link generation. Address in prompt engineering + vault write logic.

5. **Frontmatter schema drift** — Lock frontmatter schema v1 before first use: `tags`, `created`, `source_doc`, `note_type`. Treat additions as breaking changes. Write schema validator that runs after every import. Enforce block YAML list style (`- item`) in post-processing. Address in config/schema design before any code.

6. **AI hallucinated connections** — Add explicit "no inference" constraint: only create links and claims explicitly stated in source. Include `source_doc` in every note. Add `confidence: source` vs `confidence: inferred` field for auditability. Critical to put in core generation prompt, not added later.

7. **GitHub secrets and hardcoded paths** — Commit only `config.example.json`; add `config.json` to `.gitignore`. Install script generates config interactively. Include a zero-to-first-note README walkthrough. Review entire repo as a new user before publish.

## Implications for Roadmap

Based on the dependency graph from ARCHITECTURE.md and the pitfall-to-phase mapping from PITFALLS.md, a 4-phase structure is strongly indicated. The build order is dictated by hard dependencies: everything reads config (Phase 1 first), nothing can be tested without a parseable file (Phase 1), AI analysis can't be designed without knowing what raw.json looks like (Phase 2 follows Phase 1), note generation can't be built without the atom plan schema (Phase 2 before Phase 3), and MOC management requires notes to exist (Phase 3 follows Phase 2).

### Phase 1: Foundation — Schema, Fetch, Parse

**Rationale:** Config and schema decisions affect every downstream component. Getting raw.json right is the prerequisite for designing the AI analysis prompt. Most critical pitfalls (tag explosion, schema drift, vault structure) must be prevented here or they require costly migration later.

**Delivers:** Working rclone fetch, structured JSON from .docx, locked config schema, canonical tag taxonomy, locked frontmatter schema, vault folder structure setup.

**Addresses:** Google Drive download, .docx parsing + heading-aware splitting, vault path configuration, subfolder routing, one-command install (initial version).

**Avoids:** Pitfall 2 (tag explosion — taxonomy defined here), Pitfall 5 (frontmatter schema drift — locked here), Pitfall 7 (vault folder bloat — hardcoded folder map), Pitfall 10 (GitHub secrets — config.example.json committed here, config.json gitignored).

**Research flag:** Standard patterns — python-docx usage is well-documented; rclone subprocess pattern is established in existing project skills. No research-phase needed.

### Phase 2: AI Core — Atomization, Tagging, Linking

**Rationale:** Claude's analysis is the product's core value. This phase requires raw.json as input (produced in Phase 1) and produces the atom plan schema that Phase 3 renders. Prompt engineering decisions made here (atomization guardrails, link density caps, no-inference constraint) are the hardest to retrofit later.

**Delivers:** Working SKILL.md (process-document), distilled rules/*.md from reference .docx files, atom plan JSON schema, Claude prompt with atomization rules (150-600 word guardrail, 3-7 wikilink cap, "no inference" constraint), tag inference constrained to canonical taxonomy, wikilink mention-matching logic, MOC planning logic.

**Addresses:** LLM-driven atomization (v1 heading-based split as baseline, LLM refinement as upgrade path), tag inference from content, wikilink generation, MOC structure planning.

**Avoids:** Pitfall 1 (atomization extremes — guardrails defined here), Pitfall 4 (wikilink noise — hard cap enforced here), Pitfall 6 (hallucinated connections — no-inference constraint written here).

**Research flag:** Needs careful prompt engineering validation with real .docx input. The two reference .docx files in the project should be parsed and their atomization examples used as few-shot examples. The atom plan JSON schema must be finalized here — changing it in Phase 3 breaks the generation pipeline.

### Phase 3: Writers — Note Generation, Vault Placement, MOC Management

**Rationale:** With the atom plan schema finalized in Phase 2, the generation and writing components can be built. Staging as the safety contract must be implemented here — vault_writer.py is the only component that touches the real vault.

**Delivers:** generate_notes.py (atom plan → .md files with YAML frontmatter in staging), vault_writer.py (staging → vault with content-hash dedup, append-only, conflict logging), moc_manager.py (create/update MOC hub files; max 2-level hierarchy; appends links on re-import), schema validator (PyYAML parse every generated note; report unknown frontmatter fields).

**Addresses:** Atomic note creation, YAML frontmatter generation, MOC file generation (with update logic), idempotency, Smart Connections re-indexing prevention.

**Avoids:** Pitfall 3 (stale MOCs — update logic built here, not retrofitted), Pitfall 5 (schema drift — validator runs after every generation), Pitfall 9 (Smart Connections re-indexing — content hash idempotency).

**Research flag:** Standard patterns — vault_writer dedup and MOC append patterns are well-understood. No research-phase needed. Verify content hash idempotency handles Cyrillic filenames on Manjaro ext4 without encoding issues.

### Phase 4: Polish — Integration, Install, Publish

**Rationale:** End-to-end testing with real .docx files from the vault will surface integration issues. Install script portability and README quality are the difference between a personal tool and a publishable GitHub package.

**Delivers:** End-to-end integration test (full pipeline on real .docx from Google Drive), dry-run mode (`--dry-run` flag), install.sh hardening (auto-detect rclone remote, validate vault path, clear error messages), config portability test (clean environment with non-default paths), GitHub-ready repo (`config.example.json`, `.gitignore`, security review), bilingual README with zero-to-first-note walkthrough, import-log.md output.

**Addresses:** One-command install (hardened), dry-run / preview mode, progress logging, GitHub publishability.

**Avoids:** Pitfall 8 (fragile install / too many options), Pitfall 10 (GitHub secrets — final security review here).

**Research flag:** No research needed — install script patterns are standard. The validation checklist from PITFALLS.md "Looks Done But Isn't" section should be run as the phase exit criteria.

### Phase Ordering Rationale

- Phase 1 before all others: config and schema decisions are load-bearing; everything else reads config at startup. Tag taxonomy and frontmatter schema must be defined before the first line of generation code.
- Phase 2 before Phase 3: atom plan JSON schema (Phase 2 output) is the contract between AI analysis and note generation. Phase 3 cannot be implemented without it.
- Phase 3 before Phase 4: integration testing (Phase 4) requires working end-to-end pipeline (Phase 3 output).
- MOC update logic in Phase 3, not Phase 4: treating it as "polish" creates technical debt that requires vault migration to recover from. First-class from the start.
- Dry-run in Phase 4: useful but not blocking. Can be added after the pipeline is proven to work correctly.

### Research Flags

**No research-phase needed for any phase** — the architecture is well-documented, the stack is established, and the patterns are already in use in this codebase (obsidian-gdrive-sync skill uses rclone; existing skills use the same Claude Code skill structure). The research files provide sufficient detail to plan all phases.

**Validation steps that must happen during planning:**
- Phase 2: Extract and review the two reference .docx files (`Архитектура Второго мозга` and `Smart Connections`) to identify their atomization examples for use as few-shot examples in the skill prompt. This is content review, not additional research.
- Phase 3: Verify lxml installs cleanly on Manjaro without requiring `python-lxml` from pacman (or document the pacman step in install.sh).
- Phase 4: Test install.sh on a clean environment with a different rclone remote name and vault path before publishing.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | Core choices (python-docx, PyYAML, Click, Rich) are HIGH confidence — industry standard, no real alternatives. mammoth and python-frontmatter versions are unverified (web search unavailable). lxml C dependency needs Manjaro verification. |
| Features | MEDIUM | Table stakes and differentiators derived from strong domain knowledge of Obsidian/Zettelkasten ecosystem. No live competitor research was possible (Tavily unavailable). The open niche (ingestion pipeline) is clear and well-argued. |
| Architecture | HIGH | Architecture derived from project constraints + established Claude Code skill patterns already in use in this codebase. Staging pattern, skill-as-orchestrator/script-as-worker, and append-only vault writer are proven patterns with no significant uncertainty. |
| Pitfalls | MEDIUM | Based on well-documented Obsidian/Zettelkasten community patterns and direct project analysis. Word-count thresholds (150-600 words) and link density caps (3-7) are heuristic guidelines, not empirically validated. Treat as starting guardrails; adjust after first real-vault test run. |

**Overall confidence:** MEDIUM — sufficient to plan all 4 phases in detail. The architecture is the strongest finding; the stack and pitfall thresholds need validation during Phase 1-2 implementation.

### Gaps to Address

- **mammoth and python-frontmatter exact versions:** Run `pip3 index versions mammoth python-frontmatter` before pinning in requirements.txt. Low risk — both are stable libraries; version matters only for requirements.txt pinning.
- **lxml on Manjaro:** Verify `pip3 install python-docx` pulls a lxml wheel without needing `pacman -S python-lxml`. If pacman is needed, document it explicitly in install.sh as a prerequisite check.
- **Reference .docx content:** The two reference files (Архитектура Второго мозга, Smart Connections) have not been parsed for their specific atomization examples. These examples are needed as few-shot examples in the Phase 2 skill prompt. Parse them in Phase 2 planning.
- **Tag taxonomy initial content:** The canonical tags.yaml needs 30-50 starter tags reflecting the user's actual vault topics (Obsidian, AI tools, Zettelkasten, MCP, etc.). This requires a quick vault survey in Phase 1 planning — not research, just introspection.
- **Cyrillic filename handling:** Confirm that content-hash dedup and slug generation handle Cyrillic filenames without encoding errors on Manjaro ext4. Test early in Phase 3.
- **Atom plan word count guardrails:** The 150-600 word range is a reasonable starting point but needs validation against real NotebookLM export .docx files. First test import in Phase 2/3 should measure actual generated note word counts and adjust the range.

## Sources

### Primary (HIGH confidence)
- `/home/kosya/vibecoding/ObsidianDataWeave/.planning/PROJECT.md` — project constraints, existing setup, vault path, rclone configuration
- Claude Code skills architecture from existing project skills (obsidian-gdrive-sync, other skills in ~/.claude/skills/) — established patterns
- Obsidian markdown/wikilinks/YAML frontmatter spec — documented standard, stable

### Secondary (MEDIUM confidence)
- PyPI ecosystem knowledge (training data to Aug 2025) — python-docx, PyYAML, Click, Rich, python-frontmatter, mammoth
- Obsidian community patterns — MOC methodology (Nick Milo / LYT framework), Zettelkasten methodology (Luhmann), Smart Connections plugin behavior
- rclone documentation and patterns — already in use in this project via obsidian-gdrive-sync skill

### Tertiary (needs validation)
- mammoth 1.8.x, python-frontmatter 3.x — version numbers from training data; verify with pip before pinning
- Word count guardrails (150-600 words/note), link density caps (3-7/note), tag ratio thresholds — heuristic guidelines from community knowledge; validate with first real import

---
*Research completed: 2026-02-25*
*Ready for roadmap: yes*
