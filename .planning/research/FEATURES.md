# Feature Research

**Domain:** Obsidian knowledge management automation / second brain builders
**Researched:** 2026-02-25
**Confidence:** MEDIUM (training knowledge + project reference docs; Tavily/web tools unavailable this session)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| .docx parsing and text extraction | Every tool in this space processes documents; docx is the dominant export format from NotebookLM/Google Docs | MEDIUM | python-docx handles headings, paragraphs, lists, tables; pandoc as fallback for edge cases |
| Heading-aware document splitting | Users expect the tool to understand document structure, not split blindly at character counts | MEDIUM | Heading hierarchy (H1→H2→H3) maps naturally to atomic note granularity; naive line-splitting creates incoherent notes |
| YAML frontmatter generation | Every Obsidian user expects tags and metadata in frontmatter; it's the de facto standard | LOW | `tags:`, `date:`, `source:` fields; Obsidian parses this natively without plugins |
| Wikilink generation (`[[Note Name]]`) | Obsidian's core feature — users expect cross-references between notes to be automatic, not manual | HIGH | Requires semantic matching between note titles and content mentions; false positives are annoying but fixable |
| Target vault path configuration | Users have different vault locations; hardcoded paths break immediately | LOW | Config file with vault root; relative subfolder paths per note type |
| Subfolder routing by note type | MOC files go to one folder, atomic notes to another — this is basic Obsidian hygiene | LOW | Config-driven mapping: `moc_folder`, `notes_folder`, `source_folder` |
| Idempotent operation (no duplicate notes) | Users run the tool multiple times; creating duplicate notes every run destroys the vault | MEDIUM | Filename collision detection; skip-if-exists is the safe default |
| Source document attribution | Every atomic note must link back to the original document — basic academic/research hygiene | LOW | Frontmatter `source:` field + backlink to source note |
| Progress output / verbose logging | Users need to see what's happening: how many notes created, what was skipped, any errors | LOW | Print per-note status; summary at end (X notes created, Y skipped, Z errors) |
| One-command install | GitHub-distributed CLI tools are expected to have a single install entry point | MEDIUM | `bash install.sh` that handles dependencies, creates config, registers Claude skill |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| MOC generation with auto-populated links | Most tools create atomic notes but leave MOC creation manual. Auto-generating a MOC that indexes all produced notes is rare and immediately useful | HIGH | MOC file gets `[[wikilink]]` to every atomic note produced from the same source; optionally clusters by tag |
| LLM-driven atomization (not just heading splits) | Heading-based splitting is predictable but wrong — a single H2 section may contain 3 atomic concepts. LLM splitting produces genuinely atomic notes that map to one idea | HIGH | Claude reads section, decides if it's 1 note or N notes; produces a title per concept; dramatically better Zettelkasten output |
| Tag inference from content semantics | Most tools use document filename or user-supplied tags. Inferring tags from note content (domain, concept type, status) enables automatic Obsidian graph clustering | MEDIUM | Claude reads note content, outputs 3–5 semantic tags; must be constrained to a taxonomy to avoid tag explosion |
| Concept link suggestion (not just mention-matching) | Wikilinks based on exact title matches miss conceptual relationships. LLM can suggest `[[related concept]]` links even when the exact title doesn't appear in the text | HIGH | Two-pass: create all notes, then pass note list + content to LLM to suggest cross-links; expensive but produces genuine knowledge graph |
| Google Drive integration via rclone | Most tools work on local files only. Pulling directly from Drive (where NotebookLM exports live) removes the manual download step from the workflow | MEDIUM | rclone already configured in this project; `rclone copy gdrive:path local_temp/` before processing |
| Configurable atomization rules via reference documents | Users can define their own note architecture rules in plain .docx files that the tool reads as its operating guidelines — personalizable methodology enforcement | MEDIUM | The two .docx reference files in this project are the template; Claude is instructed to follow them when splitting |
| Zettelkasten ID generation | Purists expect a timestamp-based UID (`202602251430`) in each note filename or frontmatter — enables permanent addressing independent of title changes | LOW | Optional feature; adds `id:` to frontmatter; filename scheme configurable |
| Dry-run / preview mode | Before committing 40 notes to vault, user wants to see what will be created | LOW | `--dry-run` flag: print note titles + tag preview without writing; critical for trust-building |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Editing existing notes | "Update my existing notes with new info from this doc" sounds useful | Destroys user edits made in Obsidian; merging is undefined; data loss risk with no clear recovery path | Create new notes only; user manually decides what to merge. Keep vault as append-only from the tool's perspective |
| Real-time vault watching / auto-sync daemon | "Automatically process new Drive files as they appear" is the logical next step | Daemon complexity, rclone polling costs, race conditions when user is editing vault, silent failures | Manual trigger per document; user stays in control of when processing happens |
| Obsidian plugin (JS) | Some users ask for a native plugin that runs inside Obsidian | Entirely different tech stack (JS/TS, Obsidian API), separate maintenance burden, App Store review, breaks on Obsidian updates | Stay as Claude Code skill — more powerful (full LLM access), runs outside Obsidian, no plugin API constraints |
| Automated backlink creation in existing notes | "Add backlinks to my old notes that relate to the new ones" — seems like completing the graph | Modifies files the tool didn't create; user edits get overwritten on next run; scope creep that delays v1 | New notes link to relevant old notes via wikilinks (one-directional is sufficient); Obsidian builds backlink view automatically |
| Multi-vault support | "I have 3 vaults, process all of them" — power user request | Config complexity multiplies; different folder schemas per vault; testing surface explodes | One vault path in config; user runs tool once per vault if needed |
| GUI / TUI interface | "Make it graphical" — lower barrier to entry | Eliminates Claude Code skill architecture; massive scope; not the target user (Claude Code users are comfortable with CLI) | Rich terminal output with progress, dry-run preview, and clear summary is sufficient UX |
| Automatic tag taxonomy creation | "Generate my entire tag system from scratch" — appealing for new users | Tag taxonomy is personal and contextual; auto-generated taxonomies diverge from user's existing tags; creates tag explosion | Provide a default taxonomy in config that user customizes; tool applies it consistently |

---

## Feature Dependencies

```
[Google Drive Download (rclone)]
    └──requires──> [rclone configured with gdrive: remote]
    └──enables──> [.docx parsing]

[.docx parsing]
    └──requires──> [python-docx installed]
    └──enables──> [document splitting]
    └──enables──> [source note creation]

[Document splitting (heading-based)]
    └──requires──> [.docx parsing]
    └──enables──> [atomic note creation]
    └──enables──> [YAML frontmatter generation]

[LLM-driven atomization]
    └──requires──> [document splitting] (as input unit)
    └──enhances──> [atomic note quality]
    └──requires──> [Claude API access via Claude Code skill]

[YAML frontmatter generation]
    └──requires──> [atomic note creation]
    └──enables──> [Obsidian tag filtering]

[Tag inference from content]
    └──requires──> [atomic note creation]
    └──enhances──> [YAML frontmatter generation]
    └──requires──> [LLM access]

[Wikilink generation (mention-matching)]
    └──requires──> [all atomic notes created] (needs complete title list)
    └──enhances──> [atomic notes]

[Concept link suggestion (semantic)]
    └──requires──> [wikilink generation] (builds on top of it)
    └──requires──> [LLM access]
    └──conflicts──> [performance] (expensive two-pass operation)

[MOC generation]
    └──requires──> [all atomic notes created]
    └──requires──> [wikilink generation] (MOC contains wikilinks to all notes)
    └──enhances──> [vault navigability]

[Dry-run mode]
    └──requires──> [document splitting] (must parse before previewing)
    └──conflicts with──> [vault write operations] (dry-run = no writes)

[Idempotency / collision detection]
    └──requires──> [vault path configuration]
    └──requires──> [atomic note creation logic]

[Vault path configuration]
    └──enables──> [all vault write operations]
    └──enables──> [idempotency check]

[One-command install]
    └──requires──> [all dependencies defined]
    └──enables──> [user onboarding]
```

### Dependency Notes

- **LLM-driven atomization requires document splitting as input:** Heading-splits produce sections; LLM then decides how to further split each section. Cannot skip heading-split phase.
- **MOC generation requires complete note list:** MOC links to all notes produced in the run; must be created last, after all atomic notes are written.
- **Wikilink generation requires complete title list:** To find mentions, need to know all note titles first. Two-pass approach: create notes (pass 1), inject wikilinks (pass 2).
- **Concept link suggestion conflicts with performance:** Semantic linking is an LLM call per note pair — O(n²) complexity. Must be optional/flag-gated.
- **Idempotency requires vault path config:** Cannot check for existing notes without knowing where the vault is.

---

## MVP Definition

### Launch With (v1)

Minimum viable product — validates the full NotebookLM→Drive→Obsidian pipeline.

- [ ] **Google Drive download via rclone** — the entry point of the whole workflow; without it, user manually downloads
- [ ] **.docx parsing with heading-aware splitting** — core transformation; heading splits are good enough for v1
- [ ] **Atomic note creation with YAML frontmatter** — each note: title from heading, `tags:`, `date:`, `source:` in frontmatter
- [ ] **Wikilink injection (mention-matching)** — basic cross-references; makes the vault a graph not a folder of files
- [ ] **MOC file generation** — the signature feature; indexes all notes from the source document; validates the MOC+Zettelkasten thesis
- [ ] **Vault path + folder structure config** — required for any user other than the author
- [ ] **Idempotency (skip existing notes)** — essential for safe repeated use
- [ ] **One-command install** — required for GitHub distribution value proposition

### Add After Validation (v1.x)

Add once core pipeline is proven working and used.

- [ ] **LLM-driven atomization** — upgrade from heading splits to true atomic notes; trigger: users report notes are too large/mixed
- [ ] **Tag inference from content** — upgrade from config-defined tags; trigger: users have diverse documents and tag taxonomy becomes unwieldy
- [ ] **Dry-run / preview mode** — add when users report surprises from the tool's output
- [ ] **Zettelkasten ID in frontmatter** — add when users request permanent addressing; low-risk addition

### Future Consideration (v2+)

Defer until product-market fit is established.

- [ ] **Concept link suggestion (semantic cross-links)** — expensive LLM pass; only worth it after basic wikilinks are validated
- [ ] **Configurable atomization rule documents** — the architecture described in the reference .docx files; worth formalizing once the core is stable
- [ ] **Multi-source batch processing** — process a folder of .docx files in one run; defer until single-doc flow is solid

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| .docx parsing + heading split | HIGH | MEDIUM | P1 |
| YAML frontmatter (tags, date, source) | HIGH | LOW | P1 |
| Wikilink injection (mention-matching) | HIGH | MEDIUM | P1 |
| MOC generation | HIGH | MEDIUM | P1 |
| Vault path config + subfolder routing | HIGH | LOW | P1 |
| Idempotency (skip existing) | HIGH | LOW | P1 |
| Google Drive download (rclone) | HIGH | LOW | P1 |
| One-command install | HIGH | MEDIUM | P1 |
| Progress/verbose logging | MEDIUM | LOW | P1 |
| Dry-run mode | MEDIUM | LOW | P2 |
| LLM-driven atomization | HIGH | HIGH | P2 |
| Tag inference from content | MEDIUM | MEDIUM | P2 |
| Zettelkasten ID in frontmatter | LOW | LOW | P2 |
| Concept link suggestion (semantic) | HIGH | HIGH | P3 |
| Configurable rule documents | MEDIUM | HIGH | P3 |
| Batch processing (folder of .docx) | MEDIUM | MEDIUM | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

---

## Competitor Feature Analysis

Key tools in the Obsidian automation / second brain space:

| Feature | Smart Connections (plugin) | Obsidian Copilot (plugin) | note-gen / custom scripts | ObsidianDataWeave (this project) |
|---------|---------------------------|--------------------------|--------------------------|----------------------------------|
| Document ingestion from Drive | No (works on existing vault) | No (works on existing vault) | Varies | Yes (rclone integration) |
| .docx parsing | No | No | Sometimes | Yes |
| Heading-based splitting | No | No | Rarely | Yes |
| LLM atomization | No (embeds whole notes) | Partial (chat only) | Rarely | Yes (v1.x) |
| MOC generation | No | No | Rarely | Yes |
| Wikilink generation | Semantic suggestions only | No | Rarely | Yes |
| Tag inference | Via embedding similarity | Via chat | No | Yes (v1.x) |
| YAML frontmatter | No (reads existing) | No | Varies | Yes |
| Vault structure management | No | No | Varies | Yes |
| One-command install | Obsidian plugin UI | Obsidian plugin UI | Manual | Yes |
| Claude Code skill (no plugin required) | No | No | No | Yes |

**Key insight:** Smart Connections and Obsidian Copilot work on notes already in the vault — they enhance existing content. No major tool covers the *ingestion pipeline* (external document → atomic notes). This is the open niche ObsidianDataWeave fills.

---

## Dimension-Specific Notes

### 1. Document Parsing and Content Extraction
**Table stakes:** .docx via python-docx. **Differentiator:** Preserving heading hierarchy for split granularity decisions (H1 = MOC, H2 = atomic note, H3 = sub-note or merged into parent). Tables and lists need special handling — flatten to markdown, don't lose data.

### 2. Note Splitting / Atomization Strategies
**Table stakes:** Heading-based split (deterministic, fast, explainable). **Differentiator:** LLM-driven split that detects when one heading contains multiple atomic ideas. The reference .docx files in this project explicitly discuss this — one idea per note is the Zettelkasten principle; heading splits approximate it but don't guarantee it.

### 3. Tagging and Categorization
**Table stakes:** User-defined taxonomy applied consistently. **Differentiator:** Content-inferred tags. **Anti-feature:** Unconstrained auto-tagging — produces 200 unique tags that fragment instead of connect. Config must include a `known_tags` list that constrains inference.

### 4. Link Generation (Wikilinks / Backlinks)
**Table stakes:** Mention-based wikilinks (if note title appears in text, wrap it). **Differentiator:** Semantic/conceptual links suggested by LLM even without exact title mention. **Key constraint:** Obsidian builds the backlink graph automatically — only wikilinks need to be explicit; backlinks are free.

### 5. MOC Generation
**Table stakes:** A single MOC per processed document, listing all produced notes. **Differentiator:** Hierarchical MOC that mirrors the document structure (H1 sections as MOC clusters, H2 atomic notes listed under each cluster). This creates an immediately navigable hub in the vault.

### 6. Obsidian Vault Structure Management
**Table stakes:** Config-driven folder routing. Files go to the right folders without user intervention. **Differentiator:** Creating the folder structure if it doesn't exist (first-run setup). **Anti-feature:** Moving or renaming existing notes — too destructive.

### 7. AI/LLM Integration
The unique advantage of a Claude Code skill vs a traditional script: LLM is available inline, not as an external API call with auth complexity. This enables LLM atomization and tag inference without any additional configuration from the user. **Table stakes for this project type:** Using LLM for at least one step (otherwise it's just a dumb splitter that any existing script provides). **Differentiator:** Multi-step LLM pipeline (split → tag → link → MOC) that produces progressively richer output.

### 8. Installation and Configuration Experience
**Table stakes:** Single install command, documented config file, clear README. **Differentiator:** The install script also creates Obsidian vault folder structure and deposits starter MOC templates — not just installing the tool but setting up the methodology. Users don't know what MOC folder structure to create; providing it as part of install is high value.

---

## Sources

- Project context: `/home/kosya/vibecoding/ObsidianDataWeave/.planning/PROJECT.md`
- Reference documents in project (content not extracted this session due to tool restrictions):
  - `Архитектура Второго мозга: Синхронизация Obsidian и Claude MCP.docx`
  - `Smart Connections: Интеллектуальный мозг вашей базы Obsidian.docx`
- Training knowledge: Obsidian ecosystem (plugins: Smart Connections, Obsidian Copilot, Templater, Dataview), Zettelkasten methodology (Luhmann), MOC methodology (Nick Milo / Linking Your Thinking), python-docx library, rclone capabilities — confidence MEDIUM (training cutoff, not live-verified this session)
- Note: Tavily web search was unavailable this session; live competitor research should be done in a follow-up pass

---
*Feature research for: Obsidian knowledge management automation toolkit (ObsidianDataWeave)*
*Researched: 2026-02-25*
