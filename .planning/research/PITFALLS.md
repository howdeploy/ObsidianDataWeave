# Pitfalls Research

**Domain:** Obsidian automation / AI note generation toolkit (MOC + Zettelkasten from .docx sources)
**Researched:** 2026-02-25
**Confidence:** MEDIUM — based on established community patterns for Obsidian/Zettelkasten automation; web search unavailable in this session; findings drawn from well-documented domain knowledge and project-specific analysis of PROJECT.md + reference .docx context

---

## Critical Pitfalls

### Pitfall 1: Note Atomization Extremes — Too Granular or Too Broad

**What goes wrong:**
AI splits a research document into either 30-word micro-fragments ("Atom: Claude is an AI") or produces 2000-word mega-notes that are basically the original document re-wrapped. Both defeat the purpose of atomic notes. Granularity decisions made per-document without a consistent rule produce a vault where some topics have 40 trivial notes and others have 1 enormous one.

**Why it happens:**
LLMs default to paragraph-level splitting (heading = note) without a concept of "one idea that can stand alone." Without explicit granularity rules in the prompt, the model follows document structure rather than idea structure. NotebookLM research docs are often structured as FAQ or thematic sections — these map poorly to atomic notes without explicit transformation logic.

**How to avoid:**
Define a concrete atomization rule in the skill prompt: one note = one claim that can be understood without reading anything else. Enforce a soft character limit: 150–600 words per atomic note as a guardrail. Notes outside this range should trigger a review flag in the output log. The two reference .docx files in this project should be parsed to extract their own atomization examples and use them as few-shot examples in the skill prompt.

**Warning signs:**
- Average note word count below 80 or above 800
- More than 15 notes generated from a single 1500-word document section
- Notes whose titles are full sentences rather than noun phrases ("Claude can connect to Obsidian" vs "Claude–Obsidian MCP connection")
- Notes with no outgoing wikilinks (too isolated to be meaningful atoms)

**Phase to address:**
Core note generation phase — define granularity rules before writing any parsing logic. Revisit during QA phase with real .docx input.

---

### Pitfall 2: Tag Explosion and Taxonomy Drift

**What goes wrong:**
AI invents tags per-document: `#ai-tools`, `#AI-Tools`, `#artificial-intelligence`, `#llm`, `#large-language-models` all appear in the same vault for the same concept. After 10 documents, there are 200+ tags with no organization. Tag hierarchies (`#tools/ai`) get mixed with flat tags (`#obsidian`), breaking filter views and Smart Connections category grouping.

**Why it happens:**
Without a controlled vocabulary, the AI generates the most contextually relevant tag for each note independently. No session memory means no consistency across documents processed at different times. Users rarely notice tag drift until the tag panel is unusable.

**How to avoid:**
Ship a `tags.yaml` canonical taxonomy file as part of the toolkit. The skill must load this file at runtime and constrain tag selection to the approved vocabulary. Include a mechanism for the AI to propose new tags (logged to a `proposed-tags.md` file) rather than silently inventing them. Use only lowercase, hyphenated tags — enforce this in post-processing. Start with 30–50 tags maximum; let users extend deliberately.

**Warning signs:**
- Tag count growing faster than note count (more than 1 unique tag per 3 notes)
- Same concept appearing under 3+ different tag spellings
- Tags with only 1–2 notes assigned (near-certain signs of invented tags)
- `#AI` and `#ai` both present

**Phase to address:**
Config/schema design phase — define the canonical taxonomy before the first document is processed. Extend in maintenance phase via controlled proposals.

---

### Pitfall 3: MOC Structure Becoming Stale and Over-Hierarchical

**What goes wrong:**
MOC files are generated once when a topic first appears, then never updated as new notes are added on the same topic. After 6 months, MOCs list 8 notes but the vault has 40 related notes that never got linked back. Alternatively, the system creates MOC hierarchies 4 levels deep (`MOC-AI > MOC-AI-Tools > MOC-AI-Tools-Claude > MOC-AI-Tools-Claude-MCP`) that users never navigate because the graph becomes a tree instead of a web.

**Why it happens:**
MOC update logic is an afterthought — the skill creates MOCs during first import but has no mechanism to re-open and update them on subsequent imports. Deep hierarchies emerge when AI maps document folder structure directly to MOC hierarchy instead of using flat topic-based MOCs.

**How to avoid:**
Design MOC update as a first-class operation from day one: every import run should scan existing MOCs and append new links. Keep MOC hierarchy maximum 2 levels: top-level domain MOCs (e.g., `MOC-AI-Tools`) and one sub-level for heavy topics. Enforce a rule: if a topic needs more than 2 MOC levels, it needs to be split into separate domain MOCs instead. MOC files should contain only links and 1–2 sentences of context per link — not content.

**Warning signs:**
- MOC file was last modified more than 2 weeks before the most recent note in its topic area
- More than 3 levels of MOC nesting exist in the vault
- Notes exist in a topic folder with no corresponding MOC entry
- MOC files longer than 100 lines (becoming content dumps rather than navigation hubs)

**Phase to address:**
Architecture design phase for MOC update logic; verified in integration testing phase with multi-run imports.

---

### Pitfall 4: Wikilink Generation — Linking Everything to Everything

**What goes wrong:**
AI aggressively links every mention of a concept: the word "AI" in a note about cooking gets linked to `[[Artificial Intelligence]]`. A 400-word note ends up with 25 wikilinks, most of which are noise. Conversely, some implementations are too conservative and generate zero links between related notes, making the graph useless. Broken links (linking to `[[Note Title]]` when the actual file is named `note-title.md` or `Note Title (2024).md`) are common when file naming conventions are inconsistent.

**Why it happens:**
LLMs pattern-match keywords to link targets without semantic weight assessment. The "importance" of a link is not modeled — every co-occurrence looks like a valid link. Naming convention mismatches between what the AI generates and what Obsidian actually creates are discovered late, often after many notes are imported.

**How to avoid:**
Limit wikilinks to 3–7 per atomic note (enforced as a prompt constraint, not just a guideline). Links should only point to concepts that are the primary subject of an existing note — not every mention. Before generating links, build a link target index from the vault's existing note titles and pass it as context. Use exact-match title normalization: define one naming convention (Title Case, no dates in filename) and enforce it in both the note creation and link generation steps.

**Warning signs:**
- Obsidian graph showing dense clusters where every node connects to the same 5 hub notes
- Broken link count in Obsidian's "Unlinked mentions" panel above 10% of total links
- Notes with more than 10 wikilinks in 400 words
- Notes with 0 wikilinks that clearly relate to existing vault topics

**Phase to address:**
Note generation prompt engineering phase; link normalization as part of vault write logic.

---

### Pitfall 5: Frontmatter Schema Becoming Inconsistent and Overloaded

**What goes wrong:**
Early notes have `tags`, `created`, `source`. Later notes add `status`, `confidence`, `topic`, `related`, `area`, `project`. Different runs produce different schema versions. Dataview queries break when half the vault uses `tags:` and half uses `tag:`. YAML arrays vs inline strings for tags (`tags: [ai, tools]` vs `tags:\n  - ai\n  - tools`) cause parsing inconsistencies in Obsidian and Smart Connections indexing.

**Why it happens:**
Schema evolves as the project develops without versioning. AI adds fields that seem useful in context without checking the established schema. No validation step catches schema drift between runs.

**How to avoid:**
Define a locked frontmatter schema v1 before first use and treat changes as breaking changes requiring migration. Start minimal: `tags`, `created`, `source_doc`, `note_type` (atomic/MOC/index). Write a schema validator that runs after every import and reports any notes with unknown frontmatter fields. Use consistent YAML list format (block style `- item`) across all notes — enforce in post-processing, not just prompting.

**Warning signs:**
- Two notes on the same topic have different frontmatter fields
- `tags` field is sometimes a string and sometimes an array
- Dataview queries return unexpected empty results
- Smart Connections indexes notes differently based on frontmatter presence

**Phase to address:**
Config/schema design phase — define and document the schema before any note generation code is written.

---

### Pitfall 6: AI-Generated Content Quality — Hallucinated Connections and Generic Summaries

**What goes wrong:**
The skill generates notes claiming `[[ConceptA]] directly enables [[ConceptB]]` when the source document merely mentioned both concepts in the same paragraph. Summaries are generic restatements ("This note discusses the importance of AI in knowledge management") rather than capturing the specific insight from the source. Cross-document links are invented: a note from document A links to a concept from document B that was never actually connected in either source.

**Why it happens:**
LLMs are trained to produce coherent, well-connected text. In the absence of explicit instructions to stay strictly within source claims, the model "fills gaps" with plausible connections that sound authoritative. NotebookLM research docs often contain broad thematic summaries that the AI interprets as established facts rather than research notes.

**How to avoid:**
Add an explicit "no inference" constraint to the skill prompt: "only create wikilinks and claims that are explicitly stated or directly demonstrated in the source document — never infer connections." Include the source document title in every generated note's frontmatter (`source_doc:`) so users can always trace claims back. Cross-document links should only be created if the same concept title exactly matches an existing note — never speculatively. Add a `confidence: source` vs `confidence: inferred` frontmatter field to let users audit generated content.

**Warning signs:**
- Notes making causal claims ("enables", "requires", "causes") between topics that are merely co-mentioned in source
- Wikilinks to notes that don't exist yet (AI linking to concepts it invented)
- Summary sentences that could apply to any note in the vault ("This concept is important for building a second brain")
- No `source_doc` traceability in frontmatter

**Phase to address:**
Prompt engineering phase — these constraints must be in the core generation prompt, not added later. Audit phase using sample .docx imports.

---

## Moderate Pitfalls

### Pitfall 7: Vault Structure — Folder Bloat and Naming Convention Inconsistency

**What goes wrong:**
The skill creates folders per-document (`Research-2024-01-15/`, `Smart-Connections-Notes/`) instead of per-topic, leading to 30 folders after 10 imports. Naming conventions mix languages: some notes in Russian (matching source document language), some in English (from the skill's prompt). Obsidian's file system becomes unusable for manual navigation. The existing vault structure (`Гайды, разборы`, `Ресерч и исследования`) is ignored or duplicated.

**Why it happens:**
Without explicit vault structure mapping in the config, the skill defaults to whatever organization feels natural per run. Language mixing happens because the source .docx are in Russian but the skill prompt templates are in English.

**How to avoid:**
Hardcode the destination folder mapping in `config.json`: atomic notes go to `Ресерч и исследования/Атомарные заметки/`, MOCs go to `Ресерч и исследования/MOC/`. Never create new top-level folders dynamically. Define a language policy: note titles follow source document language, frontmatter field names are always English (YAML standard). Filenames use ASCII-safe slugs if the OS requires it, but display titles can be in any language.

**Warning signs:**
- New folders appearing after each import run
- Mix of Cyrillic and Latin characters in filenames in the same directory
- Duplicate notes about the same topic in different folders

**Phase to address:**
Config design phase — vault structure must be a config-driven decision, not a runtime AI decision.

---

### Pitfall 8: User Experience — Too Many Config Options and Fragile Setup

**What goes wrong:**
The install script requires setting 12 environment variables, 3 config files, and manual rclone remote naming. First-time users hit Python version errors, missing `python-docx` module, wrong vault path in config, or rclone remote named differently than the hardcoded `gdrive:`. The skill fails silently when the vault path doesn't exist rather than giving a clear error.

**Why it happens:**
Developers know their own setup and build around it. `gdrive:` is hardcoded because that's what the author uses. Path assumptions (`/mnt/sda1/`) are Linux-specific and break on macOS. Error handling is added as an afterthought.

**How to avoid:**
The install script should auto-detect: rclone remote name (list remotes, pick the Google Drive one), vault path (prompt with default, validate existence), Python dependencies (install automatically). Config must have only 3 required fields: `vault_path`, `gdrive_remote`, `gdrive_folder`. Everything else has sane defaults. Add explicit error messages with fix instructions for every failure mode (missing vault path, wrong rclone remote, missing python-docx). Test install script on a clean system before publishing.

**Warning signs:**
- Install instructions have more than 5 steps
- Config file has more than 10 fields without grouping
- Setup requires manual editing of script files (not just config)
- No validation step that checks all requirements before first run

**Phase to address:**
Install/packaging phase — design the UX before writing the installer, not after.

---

### Pitfall 9: Smart Connections Integration — Duplicate Embeddings and Performance Issues

**What goes wrong:**
Every time the skill runs, it re-imports notes that already exist (even with minor edits), causing Smart Connections to re-index them and bloat the `.smart-env/` embedding cache. Vaults with 500+ auto-generated notes become slow to open because Smart Connections re-embeds everything on vault load. Embeddings for very short notes (under 50 words) produce low-quality semantic matches that pollute search results.

**Why it happens:**
Smart Connections triggers re-indexing based on file modification timestamps. A skill that rewrites notes rather than appending always triggers full re-indexing. Short atomic notes below the semantic coherence threshold produce embedding vectors too close to random noise.

**How to avoid:**
Implement idempotent writes: before writing a note, hash its content and skip if unchanged. Only update the `modified` frontmatter field when content actually changes. Enforce the 150-word minimum for atomic notes — notes below this threshold either get merged with a related note or flagged for manual review rather than written as-is. Document the expected Smart Connections index size growth in the README so users can set expectations.

**Warning signs:**
- Smart Connections re-indexing taking more than 30 seconds after each import
- `.smart-env/` folder growing by more than 10MB per import run
- Semantic search returning notes that are clearly unrelated to the query
- Notes with identical content but different filenames in the vault

**Phase to address:**
Note write logic phase — idempotency must be designed into the file writing step, not retrofitted.

---

### Pitfall 10: GitHub Publishing — Hardcoded Paths, Missing Docs, Secrets in Config

**What goes wrong:**
The published config.json contains the author's vault path (`/mnt/sda1/KISA's Space/`), rclone remote name, and possibly the Google Drive folder ID. New users clone the repo, run the install, and get errors because all paths are wrong for their system. README explains the author's use case but not how to adapt it. The `.docx` reference files (which define the note generation rules) are not included in the repo, so users have no way to understand the generation logic.

**Why it happens:**
The project is built for personal use first. Publishing is treated as "upload the working version" rather than "build for a new user's first run." Config files get committed without reviewing for personal data.

**How to avoid:**
Commit only `config.example.json` with placeholder values and instructions. Add `config.json` to `.gitignore`. The install script generates `config.json` from `config.example.json` interactively. The two reference .docx files should either be included (as they define generation rules) or replaced with a `rules/` directory of markdown files that define the same rules in a format users can read and customize. README must include a "From zero to first note" walkthrough, not just feature descriptions.

**Warning signs:**
- `config.json` is tracked in git (check `.gitignore`)
- README describes the project from the author's perspective without a "getting started" section
- No `config.example.json` file exists
- Issues/PRs on GitHub asking "what path do I set for vault_path?"

**Phase to address:**
GitHub packaging phase — review everything in the repo as if you are a new user with a different OS and vault location before publishing.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcode vault path in skill | Faster to implement, works for author | Breaks for every other user, requires manual edit to install | Never — use config.json |
| Generate tags freely without taxonomy | More relevant tags per note | Tag explosion, unusable tag panel after 20 docs | Never — ship taxonomy file with toolkit |
| Skip MOC update logic on re-import | Simpler first implementation | MOCs become stale within weeks, users lose trust in navigation | Only in MVP if clearly documented as "MOCs require manual update" |
| Write notes even if content is unchanged | Simpler write logic | Smart Connections re-indexes entire vault on every run | Never — content hash check is 10 lines of code |
| Use document section headers as note titles | Easy to implement | Titles are procedural not conceptual ("Section 3.2: Integration") | Never — titles should reflect the idea, not source structure |
| Embed .docx rule files as binary in repo | Rules are versioned | New users can't read or customize rules | Acceptable for v1 only; migrate to markdown rules directory in v2 |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| rclone + Google Drive | Hardcode remote name as `gdrive:` | Auto-detect via `rclone listremotes`, pick Drive remote, store in config |
| python-docx .docx parsing | Treat all paragraphs as equal content | Check paragraph style (Heading1/2/3 vs Normal) to infer document structure for atomization |
| Obsidian wikilinks | Generate links with `[[Title]]` assuming titles are unique | Verify title uniqueness in vault before generating; use disambiguation suffixes if needed |
| Smart Connections | Re-write every note on every import | Hash note content; skip writes when content is unchanged to prevent re-indexing |
| YAML frontmatter | Mix block and flow YAML style | Enforce block style (`- item`) consistently; validate with PyYAML before writing |
| NotebookLM export format | Assume consistent .docx structure | Handle both FAQ-style and narrative-style docs; detect format and apply appropriate chunking strategy |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Re-embedding unchanged notes | Smart Connections slow on vault open; fan noise after every import | Content hash idempotency check before write | After ~200 notes with repeated imports |
| Generating too many wikilinks | Obsidian graph becomes a dense hairball, link resolution slow | Hard cap of 7 links per note in prompt | After ~500 notes with 20+ links each |
| Loading entire vault note list into prompt context | Import slow; Claude context window exceeded for large vaults | Build a lightweight note-title index file, load only that | When vault exceeds ~300 notes |
| Parsing entire .docx into one prompt | Token limit exceeded for long research documents (>10,000 words) | Chunk document by section before processing; process chunks sequentially | Documents over ~8,000 words |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Committing config.json with vault path | Leaks file system layout of user's machine to GitHub | Add config.json to .gitignore; use config.example.json only |
| Committing rclone config or tokens | Full Google Drive access to anyone who clones repo | Document that rclone config lives at `~/.config/rclone/rclone.conf` and is never part of this repo |
| Including personal .docx research files in repo | Leaks private research content | Ship only template/example .docx, never real user data |
| Vault path with spaces unquoted in shell scripts | Path injection in bash scripts (`/mnt/sda1/KISA's Space/`) | Always quote path variables in shell: `"${VAULT_PATH}"` |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Silent failure when vault path wrong | User runs import, sees no output, checks vault, nothing happened — no idea why | Validate all paths at startup; print clear error with fix instruction before any processing begins |
| No dry-run mode | Users afraid to run on real vault; can't preview what will be created | Implement `--dry-run` flag that shows note titles and counts without writing files |
| No import log | Can't tell which notes came from which document; can't debug quality issues | Write a `import-log.md` or stdout summary: document processed, notes created, links generated, warnings |
| Overwriting existing notes without warning | User has manually edited a note; re-import silently overwrites edits | Skip existing notes by default; add `--overwrite` flag for explicit overwrite |
| Config with no validation feedback | User sets wrong vault path; skill runs but writes to wrong location | Print "Config loaded: vault_path = /your/path [EXISTS / NOT FOUND]" before every run |

---

## "Looks Done But Isn't" Checklist

- [ ] **MOC Update Logic:** MOC files are created — but verify they are also *updated* on subsequent imports of related documents. Run two imports of related docs and check MOC file modification date.
- [ ] **Tag Consistency:** Tags look correct in individual notes — but verify the same concept doesn't appear under two different tag names across different notes. Run `grep -r "tags:" vault/ | sort` and inspect for duplicates.
- [ ] **Wikilink Resolution:** Links look correct in source — but verify Obsidian resolves them (no broken links in Obsidian's Unlinked Mentions panel). Import a test document and check graph view.
- [ ] **Idempotency:** First import works — but verify running the same import twice produces identical vault output (no duplicate notes, no Smart Connections re-indexing). Check file modification timestamps after second run.
- [ ] **Config Portability:** Works on author's machine — but verify on a fresh system with different vault path and rclone remote name. The `config.example.json` must work as a complete template.
- [ ] **GitHub README:** Documentation exists — but verify a new user can go from `git clone` to first imported note by following README alone, without asking questions.
- [ ] **YAML Frontmatter Validity:** Frontmatter looks right in text — but verify PyYAML parses every generated note without errors (malformed YAML silently breaks Dataview and Smart Connections).

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Tag explosion already in vault | HIGH | Export all notes, run tag normalization script against canonical taxonomy, re-import; manual review of proposed-new-tags |
| MOC files stale (missing 50+ notes) | MEDIUM | Re-run MOC generation pass over entire vault; compare note topics to MOC entries; add missing links |
| Broken wikilinks across 200+ notes | MEDIUM | Use Obsidian's "Find unresolved links" panel; write a batch rename script to align note titles to link targets |
| Duplicate notes from non-idempotent imports | MEDIUM | Hash all note contents, identify exact duplicates, delete newer copies; review near-duplicates manually |
| Hardcoded paths in published GitHub repo | LOW | Force-push sanitized config.example.json, add config.json to .gitignore, bump version — no vault data was leaked if config.json wasn't committed |
| Hallucinated cross-document links | HIGH | No automated fix — requires manual audit; add `confidence: inferred` field to future notes to limit scope |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Note atomization extremes | Core prompt engineering (Phase 1) | Sample import: check average note word count, title format |
| Tag explosion | Schema/config design (Phase 1) | After 3 test imports: count unique tags vs notes ratio |
| Stale / over-hierarchical MOCs | Architecture design (Phase 1) + re-import logic (Phase 2) | Run two sequential imports; verify MOC file timestamps updated |
| Wikilink noise / broken links | Prompt engineering (Phase 1) + link index (Phase 2) | Import test doc; open graph view; check Obsidian unlinked mentions |
| Frontmatter schema drift | Config/schema design (Phase 1) | PyYAML validate all generated notes after each test import |
| AI hallucinated connections | Prompt engineering (Phase 1) + audit (QA phase) | Trace 5 random wikilinks in generated notes back to source document |
| Vault folder bloat | Config design (Phase 1) | Check folder count before and after 5 test imports |
| Fragile install / too many options | Install/UX design (Phase 3) | Run install script on fresh environment with non-default settings |
| Smart Connections re-indexing | Note write logic (Phase 2) | Run same import twice; measure .smart-env/ folder size delta |
| GitHub secrets / paths in config | Packaging phase (Phase 3) | `git grep` for vault path, rclone remote name, any personal data before publish |

---

## Sources

- Project context: `/home/kosya/vibecoding/ObsidianDataWeave/.planning/PROJECT.md` (project requirements, constraints, existing setup)
- Domain knowledge: Obsidian community documented patterns for MOC + Zettelkasten automation (Luhmann's Zettelkasten methodology, Nick Milo's LYT framework pitfalls, standard Obsidian plugin ecosystem behavior)
- Smart Connections behavior: documented plugin behavior for embedding cache, re-indexing triggers, short-note quality thresholds
- rclone integration patterns: standard rclone remote configuration and path handling for Google Drive
- Confidence note: Web search was unavailable during this research session. Findings are based on well-established Obsidian/Zettelkasten community knowledge and direct project context analysis. Claims about specific thresholds (word counts, tag ratios) are heuristic guidelines, not empirical measurements — treat as LOW confidence until validated with real vault data.

---
*Pitfalls research for: ObsidianDataWeave — Obsidian automation toolkit (MOC + Zettelkasten from .docx sources)*
*Researched: 2026-02-25*
