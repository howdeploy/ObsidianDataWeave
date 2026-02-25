# Phase 2: AI Core - Research

**Researched:** 2026-02-26
**Domain:** Claude SKILL.md prompt engineering, atom plan JSON schema design, wikilink generation strategy
**Confidence:** HIGH (all Phase 1 artifacts verified working; SKILL.md pattern derived from existing skills in environment; JSON schema design grounded in concrete parser output measurements)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Atomization Strategy
- Text handling: Hybrid — preserve original phrases and formulations (user's research, user's words), but Claude adds introductory context and connective tissue so each note is self-contained
- Splitting: Claude decides based on rules/atomization.md (one idea = one note, 150-600 words). No hard word-count threshold — Claude evaluates semantic boundaries
- Language: Notes written in the language of the source document (Russian doc → Russian notes, English doc → English notes)
- Title style: Claude's discretion — picks appropriate style (noun phrase, claim, etc.) based on content

#### Tag & Type Inference
- Tag selection: 2-5 tags per note from tags.yaml taxonomy
- New tags: When no existing tag fits, Claude uses the new tag BUT logs it in proposed-tags.md for user review later. Does NOT modify tags.yaml directly.
- note_type: Claude analyzes content to determine type (atomic, moc, source). MOC is always one per document. Source type used when note describes a product/book/tool.

#### Wikilink Generation
- Strategy: Explicit mentions + semantic links — Claude inserts [[wikilinks]] both where titles are mentioned and where ideas are semantically related
- Placement: Inline within text only (no separate "Related notes" section at bottom)
- Scope: v1 links only to notes created in the same processing run (same document). No vault scanning.
- Limit: Claude's discretion on quantity per note (guided by rules/taxonomy.md)

### Claude's Discretion
- Output format (JSON intermediate vs direct .md)
- SKILL.md processing strategy (single-shot vs iterative)
- Title style per note (noun phrase, claim, descriptive)
- Wikilink quantity per note
- When to split sections vs keep whole

### Deferred Ideas (OUT OF SCOPE)
- Cross-document wikilinks (LINK-V2-02) — v2, requires vault scanning
- Dry-run mode (DOCX-V2-01) — v2
- Zettelkasten timestamp IDs (DOCX-V2-03) — v2
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DOCX-04 | Claude анализирует каждую секцию и решает — одна заметка или несколько атомарных идей (LLM-атомизация) | Section sizes measured from actual .docx files: 52-371 words each. Most map 1:1 to notes; 371-word section may yield 2-3 notes. SKILL.md atomization prompt must express per-section decision logic. |
| DOCX-05 | Каждая атомарная заметка содержит одну идею (150-600 слов), с осмысленным заголовком | rules/atomization.md already encodes this; SKILL.md loads it as operating context. Success criterion: verify word count range in atom plan output. |
| META-01 | Каждая заметка имеет YAML frontmatter с полями: tags, date, source_doc, note_type | Atom plan JSON must include these four fields per note. YAML rendering is Phase 3's job; Phase 2 outputs them as JSON fields. |
| META-02 | Теги назначаются из каноничной таксономии (tags.yaml в конфиге), а не придумываются произвольно | SKILL.md must load tags.yaml content into Claude context verbatim. tags.yaml is 42 tags, ~25 lines — fits in context comfortably. |
| META-03 | Claude выводит 3-5 тегов из содержания заметки, ограничиваясь таксономией | Tag inference prompt section in SKILL.md must be explicit: select 2-5 from the provided list, log any new tags separately. |
| META-04 | note_type различает типы: atomic, moc, source (для фильтрации в Obsidian) | SKILL.md must include type detection logic: MOC = one per document with heading hierarchy; source = when note describes a product/book/tool; atomic = default. |
| LINK-01 | Wikilinks [[]] автоматически вставляются когда заголовок заметки упоминается в тексте другой | Wikilink pass requires full title list to be built before link insertion. Two-pass architecture: (1) generate all note titles, (2) insert links. |
| LINK-02 | Claude предлагает семантические связи между заметками, даже если заголовок не упоминается буквально | Semantic linking requires Claude to consider conceptual relationships after all notes are drafted. Best done in a final wikilink-review pass. |
| LINK-03 | MOC-файл генерируется для каждого обработанного документа со ссылками на все атомарные заметки | MOC is a special note_type; must be generated last, after all atom titles are confirmed. MOC body = structured wikilink list. |
| LINK-04 | MOC зеркалит структуру документа — секции H1 как кластеры, H2-заметки внутри | JSON input sections have normalized level 1/2 hierarchy. MOC generation reads section headings to produce two-level structure. |
</phase_requirements>

---

## Summary

Phase 2 builds SKILL.md — a Claude operating instruction file that accepts the parsed JSON from Phase 1 (via `parse_docx.py`) and produces an atom plan: a JSON array where every element is a fully-formed atomic note ready for Phase 3 to write to disk. There are no new Python libraries to install, no external services to call, and no complex infrastructure. The entire phase is prompt engineering work: writing a SKILL.md that reliably orchestrates Claude's reading, splitting, tagging, linking, and MOC generation into a deterministic output.

The critical design decision this phase makes is the atom plan JSON schema. This schema is the contract between Phase 2 and Phase 3. Based on measurement of the actual reference .docx files — sections range from 52 to 371 words, with most under 200 — the atom plan will yield roughly 5-12 atomic notes per document plus one MOC. SKILL.md uses an iterative processing strategy (section-by-section, not single-shot) because Russian documents of 500+ words risk output truncation in a single generation. The final atom plan is a JSON file written to `/tmp/dw/staging/` by Phase 2's orchestration script, then consumed by Phase 3's vault_writer.py.

The wikilink problem requires two-pass generation: first establish all note titles, then insert links. Single-pass linking is unreliable because you cannot reference titles that haven't been written yet. The atom plan JSON must carry enough information that Phase 3 can render it without calling Claude again.

**Primary recommendation:** Use JSON file in staging as atom plan output (not direct .md files), iterative section-by-section SKILL.md processing with a final linking pass, and a two-file Phase 2 deliverable: SKILL.md (Claude instructions) + scripts/atomize.py (Python orchestrator that loads SKILL.md and calls Claude API).

---

## Standard Stack

### Core (Phase 2 adds no new dependencies)

| Component | Version | Purpose | Why |
|-----------|---------|---------|-----|
| SKILL.md | — | Claude operating instructions; loaded into context at processing time | Consistent pattern in this environment; all Claude skills use this format; no custom tooling needed |
| scripts/atomize.py | new | Python orchestrator: loads SKILL.md + parsed JSON, calls Claude via subprocess/stdin, writes atom plan JSON to staging | Pure stdlib — json, pathlib, subprocess, sys; no new pip dependencies |
| json (stdlib) | stdlib | Atom plan JSON schema serialization/deserialization | Already used in parse_docx.py; atom plan written as JSON, not YAML or .md directly |
| yaml (PyYAML 6.0.3) | pre-installed | Load tags.yaml taxonomy into SKILL.md context at runtime | Already on system; used in Phase 1 tag loading pattern |
| tomllib (stdlib) | Python 3.11+ | Read config.toml for staging_dir | Already on system; used in Phase 1 |

### No New pip Installs Required

Phase 2 is pure prompt engineering + Python orchestration using only what Phase 1 already verified:
- python-docx 1.2.0 (installed)
- PyYAML 6.0.3 (pre-installed)
- tomllib (stdlib)
- Claude CLI (available as `claude` command in this environment)

---

## Architecture Patterns

### Recommended Project Structure (Phase 2 additions)

```
ObsidianDataWeave/
├── SKILL.md                    # Claude operating instructions (Phase 2 primary artifact)
├── scripts/
│   ├── fetch_docx.sh           # Phase 1 (existing)
│   ├── parse_docx.py           # Phase 1 (existing)
│   └── atomize.py              # Phase 2: orchestrator — loads SKILL.md, runs Claude, writes atom plan
├── rules/
│   ├── atomization.md          # Phase 1 (existing) — loaded into SKILL.md context
│   └── taxonomy.md             # Phase 1 (existing) — loaded into SKILL.md context
├── tags.yaml                   # Phase 1 (existing) — loaded into SKILL.md context
└── /tmp/dw/staging/
    ├── {docname}.docx          # fetched by Phase 1
    ├── {docname}.json          # parsed by Phase 1
    └── {docname}-atom-plan.json # produced by Phase 2 (consumed by Phase 3)
```

### Pattern 1: SKILL.md as Claude Operating Instructions

**What:** A markdown file read by Claude at activation time that encodes all processing rules, input format, output schema, and few-shot examples. Claude treats SKILL.md as its operating context — not a script to execute, but instructions to follow.

**When to use:** Always for this phase. The environment already uses this pattern for all skills (css-graphics, st-character-forge, obsidian-gdrive-sync). It matches how Claude Code skills work in this environment.

**SKILL.md structure for Phase 2:**

```markdown
# ObsidianDataWeave — Atomization Skill

## Input
[Describes the parsed JSON schema from Phase 1]

## Operating Rules
@rules/atomization.md
@rules/taxonomy.md

## Tag Taxonomy
[Verbatim content of tags.yaml embedded or loaded]

## Processing Strategy
[Section-by-section iterative instructions]

## Output Schema
[Atom plan JSON schema with field definitions]

## Few-Shot Example
[Complete worked example: input section → output atom note JSON]
```

**Key insight:** SKILL.md does NOT call Python. atomize.py is the Python glue that feeds SKILL.md + the parsed JSON to Claude and captures output. SKILL.md is pure instructions — Claude reads it and produces the atom plan JSON as its text response.

### Pattern 2: Atom Plan JSON Schema

**What:** The contract between Phase 2 output and Phase 3 input. Each entry in the atom plan represents one note — atomic or MOC.

**Recommended schema (based on requirements and measured section data):**

```json
{
  "schema_version": "1",
  "source_file": "Filename.docx",
  "processed_date": "2026-02-26",
  "notes": [
    {
      "id": "note-001",
      "title": "Атомарность заметок в Zettelkasten",
      "note_type": "atomic",
      "tags": ["productivity/zettelkasten", "productivity/pkm"],
      "source_doc": "Архитектура Второго мозга: Синхронизация Obsidian и Claude MCP.docx",
      "date": "2026-02-26",
      "body": "Текст заметки с [[Wikilink]] к другим заметкам...",
      "proposed_new_tags": []
    },
    {
      "id": "moc-001",
      "title": "Архитектура Второго мозга — MOC",
      "note_type": "moc",
      "tags": ["productivity/pkm", "productivity/moc"],
      "source_doc": "Архитектура Второго мозга: Синхронизация Obsidian и Claude MCP.docx",
      "date": "2026-02-26",
      "body": "## Часть 1\n- [[Атомарность заметок в Zettelkasten]]\n## Часть 2\n- [[Claude как смарт-коннектор]]",
      "proposed_new_tags": []
    }
  ],
  "proposed_tags": []
}
```

**Field definitions:**
- `id`: sequential identifier (note-001..N, moc-001) — for internal cross-referencing only; not written to vault
- `title`: the note filename (without .md); exactly matches [[wikilink]] targets
- `note_type`: one of `atomic`, `moc`, `source` — Phase 3 uses this for folder routing
- `tags`: 2-5 strings from tags.yaml taxonomy in `domain/subtag` format
- `source_doc`: verbatim .docx filename for YAML frontmatter
- `date`: ISO 8601 processing date
- `body`: complete note body in markdown, including all [[wikilinks]] inline
- `proposed_new_tags`: tags Claude invented that are NOT in tags.yaml — Phase 3 appends to proposed-tags.md

**Why JSON not direct .md files:** Phase 3 needs to validate and route notes before writing; JSON intermediate allows schema validation, atomic batch writes, and rollback. Direct .md would scatter files before Phase 3's safety checks run.

### Pattern 3: Two-Pass Wikilink Generation

**What:** Generate all note titles first (pass 1), then insert [[wikilinks]] into note bodies (pass 2). Cannot do this in a single pass because a note cannot link to a title that hasn't been named yet.

**Why it matters:** The LINK-01 and LINK-02 requirements both require accurate wikilinks. Single-pass generation produces placeholder links or misses connections because titles are being invented as the output is written.

**Implementation in SKILL.md:**

```
Step 1: For each section in the parsed JSON:
  - Decide: single note or split?
  - If split: enumerate the sub-notes with tentative titles
  - Output: {section_id → [tentative_title, ...]} mapping

Step 2: Confirm all titles. Produce final title list.

Step 3: For each note, write body with [[wikilinks]] referencing titles from step 2.

Step 4: Generate MOC using confirmed titles and source document heading structure.

Step 5: Collect proposed_new_tags from all notes.

Step 6: Output complete atom plan JSON.
```

**Tradeoff:** Iterative processing means multiple Claude responses, not one. atomize.py orchestrates these passes. This is more reliable than single-shot for documents with 500+ words.

### Pattern 4: Tag Loading into SKILL.md Context

**What:** tags.yaml must be available to Claude during tag inference. Two options: (a) embed verbatim in SKILL.md, or (b) have atomize.py inject it at runtime.

**Recommended: runtime injection via atomize.py.** atomize.py reads tags.yaml with yaml.safe_load(), flattens it to a list of "domain/subtag" strings, and injects into the prompt. This keeps SKILL.md version-agnostic (tags.yaml can be updated without editing SKILL.md).

```python
# In atomize.py
import yaml, json, tomllib, subprocess
from pathlib import Path

def load_tags(tags_path: Path) -> list[str]:
    data = yaml.safe_load(tags_path.read_text(encoding="utf-8"))
    return [f"{domain}/{subtag}"
            for domain, subtags in data["tags"].items()
            for subtag in subtags]

# Inject into prompt: "\n".join(tags) — flat list
```

### Pattern 5: proposed-tags.md Accumulation

**What:** When Claude selects a tag not in tags.yaml, it must log it for user review. In the atom plan JSON, proposed new tags appear in `proposed_new_tags` field per note and in top-level `proposed_tags` for easy extraction. atomize.py writes proposed-tags.md from this field.

**Format for proposed-tags.md:**

```markdown
# Proposed New Tags

Tags proposed by Claude during processing that are not in tags.yaml.
Review and add to tags.yaml if appropriate.

## 2026-02-26 — Архитектура Второго мозга.docx
- `personal/spirituality` — proposed for note "Медитация как практика фокуса"
- `tech/graph-databases` — proposed for note "Граф знаний в Obsidian"
```

### Anti-Patterns to Avoid

- **Single-shot atomization for large documents:** Asking Claude to produce the complete atom plan in one response for a 400-word document is fine; for larger documents (500+ words across multiple sections) it risks truncation and inconsistent wikilinks. Use iterative section-by-section generation.
- **Wikilinks before titles are confirmed:** Always complete the title-enumeration pass before writing note bodies. A note body with `[[Векторные эмбеддинги в Smart Connections]]` is only valid if that title was produced in the same run.
- **Embedding tags.yaml verbatim in SKILL.md:** Fragile — any update to tags.yaml requires updating SKILL.md. Inject at runtime from atomize.py instead.
- **Writing .md files directly from SKILL.md pass:** Phase 2 produces JSON only. Phase 3 does filesystem writes. This separation is a locked architectural decision (non-negotiable per prior decisions).
- **MOC before all atomic notes are confirmed:** MOC must be generated last — it links to all atomic note titles, which must all be finalized.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tag validation | Custom tag-checking code | Inject tags.yaml flat list into Claude prompt; let Claude match against it | Claude's language understanding handles fuzzy matching better than string comparison; edge cases (plural forms, synonyms) need semantic understanding |
| Wikilink injection | Regex post-processor to find title mentions | Two-pass SKILL.md strategy where Claude inserts links in pass 2 | Regex cannot handle semantic links (LINK-02); only Claude understands that "embeddings" and "векторное представление" are the same concept |
| Word count enforcement | Python word counter rejecting notes | Soft guidance in SKILL.md prompt + verification step | Word counts vary by language (Russian is denser than English); hard rejection creates retry loops; better to verify post-generation |
| JSON schema validation | Custom JSON Schema validator | `json.loads()` + assert required fields present | The atom plan is simple enough for manual field checks; full JSON Schema adds dependency without value at this scale |
| Proposed-tags deduplication | Complex deduplication logic | Simple set() in atomize.py across all note proposed_new_tags | Tags are short strings; set() is sufficient; no edge cases at this scale |

**Key insight:** This phase's "library" is Claude itself. The prompt engineering in SKILL.md IS the implementation. Don't build Python logic for things Claude can do in the prompt.

---

## Common Pitfalls

### Pitfall 1: Title Instability Across Passes

**What goes wrong:** Claude generates "Векторные эмбеддинги в Smart Connections" in the title-listing pass, then writes "Векторные эмбеддинги для семантического поиска" in the body pass. The [[wikilink]] from another note points to a title that no longer exists.

**Why it happens:** Without explicit constraint, Claude paraphrases titles between generation passes. Each generation is stateless relative to previous passes unless you include the confirmed title list in the next prompt.

**How to avoid:** Pass 2 prompt MUST include the complete confirmed title list from Pass 1. Instruction in SKILL.md: "Use exactly these titles — do not rephrase them: [list]"

**Warning signs:** Atom plan JSON has titles in notes[] that don't appear in any [[wikilink]], or wikilinks referencing titles not present in notes[].

### Pitfall 2: Single Large Section Yields Oversized Note

**What goes wrong:** "Часть 2. Правила (Промпт) для Claude Code" section has 371 words and 29 paragraphs. If treated as one note, it exceeds the 600-word target after Claude adds context and connective tissue.

**Why it happens:** The 371 source words become 450-600 words after Claude adds introduction and connective tissue. The splitting decision must happen BEFORE note body generation.

**How to avoid:** SKILL.md must instruct Claude to estimate final note length = source_words × 1.3 (expansion factor for context-adding). Pre-declare split plan in Pass 1 title enumeration. For "Часть 2" (371 source words), pre-split into 2-3 atomic notes.

**Warning signs:** Any section with `len(paragraphs) > 10` or `word_count > 280` in parsed JSON likely needs splitting.

### Pitfall 3: MOC Wikilinks Pointing to Non-Existent Titles

**What goes wrong:** MOC is generated before atomic note titles are finalized. MOC contains [[Old Title]] while atomic notes array has "New Title". Phase 3 writes both; Obsidian shows broken links.

**Why it happens:** Generating MOC in the same pass as atomic notes — Claude doesn't have the full final title list yet.

**How to avoid:** MOC generation is always the LAST step. SKILL.md must make this explicit: "After all atomic notes are confirmed, generate the MOC using the final title list."

**Warning signs:** MOC body contains [[wikilinks]] that don't appear in notes[].title in the atom plan JSON.

### Pitfall 4: Tags Outside Taxonomy Silently Passing Through

**What goes wrong:** Claude assigns `tech/embeddings` (not in taxonomy) to a note. atomize.py writes the atom plan JSON with this invalid tag. Phase 3 writes the note to vault with a non-canonical tag. The user never sees a proposed-tags.md entry.

**Why it happens:** SKILL.md doesn't clearly distinguish "select from this list" from "this list is advisory." If the instruction is ambiguous, Claude uses its general knowledge of tag formats.

**How to avoid:** SKILL.md must make taxonomy constraint explicit: "Tags MUST come from this exact list only. If none fit, use the closest match AND add the ideal tag to proposed_new_tags field." atomize.py validates that all tags in notes[].tags appear in the flat tag list before writing atom plan.

**Warning signs:** `proposed_new_tags: []` on every note despite processing content that should suggest new tags — means Claude is silently inventing tags without flagging them.

### Pitfall 5: proposed-tags.md Not Created When Empty

**What goes wrong:** atomize.py only creates proposed-tags.md if there are proposed tags. Phase 3 tries to append to it and fails with FileNotFoundError.

**Why it happens:** Conditional file creation logic. Phase 3 always appends — it doesn't check existence.

**How to avoid:** atomize.py always creates proposed-tags.md (even empty with just the header) after each run.

**Warning signs:** Phase 3 errors with "proposed-tags.md not found" on first run of a document that had no new tags.

### Pitfall 6: SKILL.md Too Long for Reliable Context Window Usage

**What goes wrong:** SKILL.md grows to 2000+ words (rules + tags + schema + examples). When atomize.py prepends SKILL.md to a long document's parsed JSON, total context size approaches limits. Later tokens (the actual document content) receive less attention.

**Why it happens:** Attempting to embed everything — tags list, both rules files, schema, examples — directly in SKILL.md.

**How to avoid:** SKILL.md itself stays under 800 words. atomize.py injects tags.yaml content and the parsed JSON as separate context blocks. rules/atomization.md and rules/taxonomy.md are referenced, not pasted inline. The assembled prompt = SKILL.md header + rules content + tags list + parsed JSON + output schema.

**Warning signs:** SKILL.md file is over 100 lines before atomize.py adds anything.

---

## Code Examples

### Atom Plan JSON Schema (Complete)

```python
# From atomize.py — the schema atomize.py validates against
REQUIRED_ATOM_FIELDS = {"id", "title", "note_type", "tags", "source_doc", "date", "body", "proposed_new_tags"}
VALID_NOTE_TYPES = {"atomic", "moc", "source"}

def validate_atom_plan(plan: dict) -> list[str]:
    """Return list of validation errors, empty if valid."""
    errors = []
    if "notes" not in plan:
        errors.append("Missing top-level 'notes' key")
        return errors
    for i, note in enumerate(plan["notes"]):
        missing = REQUIRED_ATOM_FIELDS - set(note.keys())
        if missing:
            errors.append(f"Note {i}: missing fields {missing}")
        if note.get("note_type") not in VALID_NOTE_TYPES:
            errors.append(f"Note {i}: invalid note_type '{note.get('note_type')}'")
        if not 2 <= len(note.get("tags", [])) <= 5:
            errors.append(f"Note {i}: tags count {len(note.get('tags', []))} not in [2-5]")
    moc_count = sum(1 for n in plan["notes"] if n.get("note_type") == "moc")
    if moc_count != 1:
        errors.append(f"Expected exactly 1 MOC, got {moc_count}")
    return errors
```

### atomize.py Skeleton

```python
#!/usr/bin/env python3
"""
atomize.py — Orchestrate Claude to convert parsed .docx JSON into atom plan JSON.

Usage:
    python3 scripts/atomize.py <parsed.json> [-o atom-plan.json]
"""

import json, yaml, sys, subprocess
from pathlib import Path
from datetime import date

PROJECT_ROOT = Path(__file__).parent.parent

def load_config() -> dict:
    import tomllib
    config_path = PROJECT_ROOT / "config.toml"
    if not config_path.exists():
        return {"rclone": {"staging_dir": "/tmp/dw/staging"}}
    with open(config_path, "rb") as f:
        return tomllib.load(f)

def load_tags(tags_path: Path = PROJECT_ROOT / "tags.yaml") -> list[str]:
    data = yaml.safe_load(tags_path.read_text(encoding="utf-8"))
    return [f"{domain}/{subtag}"
            for domain, subtags in data["tags"].items()
            for subtag in subtags]

def load_skill_md() -> str:
    return (PROJECT_ROOT / "SKILL.md").read_text(encoding="utf-8")

def load_rules() -> tuple[str, str]:
    atomization = (PROJECT_ROOT / "rules" / "atomization.md").read_text(encoding="utf-8")
    taxonomy = (PROJECT_ROOT / "rules" / "taxonomy.md").read_text(encoding="utf-8")
    return atomization, taxonomy

def assemble_prompt(parsed_json: dict, tags: list[str],
                    skill_md: str, atomization_rules: str, taxonomy_rules: str) -> str:
    tags_block = "\n".join(f"- {t}" for t in tags)
    parsed_block = json.dumps(parsed_json, ensure_ascii=False, indent=2)
    return f"""{skill_md}

---
## Atomization Rules
{atomization_rules}

---
## Taxonomy Rules
{taxonomy_rules}

---
## Available Tags (from tags.yaml)
{tags_block}

---
## Document to Process
```json
{parsed_block}
```

Produce the complete atom plan JSON now. Output ONLY the JSON, no prose."""

def call_claude(prompt: str) -> str:
    """Call Claude CLI with prompt via stdin. Returns Claude's response text."""
    result = subprocess.run(
        ["claude", "--print"],
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8"
    )
    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI error: {result.stderr}")
    return result.stdout.strip()

def write_proposed_tags(plan: dict, staging_dir: Path, source_file: str) -> None:
    proposed = plan.get("proposed_tags", [])
    pt_path = staging_dir / "proposed-tags.md"
    header = "# Proposed New Tags\n\nTags proposed by Claude not in tags.yaml. Review and add if appropriate.\n\n"
    if not pt_path.exists():
        pt_path.write_text(header, encoding="utf-8")
    if proposed:
        entry = f"## {date.today().isoformat()} — {source_file}\n"
        for tag_info in proposed:
            entry += f"- `{tag_info['tag']}` — {tag_info.get('reason', 'no reason given')}\n"
        with open(pt_path, "a", encoding="utf-8") as f:
            f.write("\n" + entry)

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Convert parsed JSON to atom plan via Claude")
    parser.add_argument("input", help="Parsed .docx JSON from parse_docx.py")
    parser.add_argument("-o", "--output", help="Output atom plan JSON path")
    args = parser.parse_args()

    parsed_json = json.loads(Path(args.input).read_text(encoding="utf-8"))
    config = load_config()
    staging_dir = Path(config["rclone"]["staging_dir"])
    staging_dir.mkdir(parents=True, exist_ok=True)

    tags = load_tags()
    skill_md = load_skill_md()
    atomization_rules, taxonomy_rules = load_rules()

    prompt = assemble_prompt(parsed_json, tags, skill_md, atomization_rules, taxonomy_rules)
    response = call_claude(prompt)

    # Extract JSON from response (Claude may wrap in code fences)
    if "```json" in response:
        response = response.split("```json")[1].split("```")[0].strip()
    elif "```" in response:
        response = response.split("```")[1].split("```")[0].strip()

    plan = json.loads(response)

    output_path = args.output or str(
        staging_dir / (Path(args.input).stem + "-atom-plan.json")
    )
    Path(output_path).write_text(
        json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_proposed_tags(plan, staging_dir, parsed_json["source_file"])
    print(f"Atom plan written to: {output_path}", file=sys.stderr)
    print(output_path)

if __name__ == "__main__":
    main()
```

### SKILL.md Header Section (Template)

```markdown
# ObsidianDataWeave Atomization Skill

You receive a parsed document (JSON) and produce a complete atom plan (JSON).
The atom plan is a list of atomic notes + one MOC, ready for vault writing.

## Input Format

The input JSON has this structure:
{
  "source_file": "Filename.docx",
  "heading_depth_offset": N,
  "sections": [
    {"heading": "Title" | null, "level": 1, "paragraphs": ["text..."]}
  ]
}

## Processing Steps

### Step 1: Title Enumeration Pass
For each section, decide:
- Single note? → propose one title
- Split? → propose multiple titles (apply rules/atomization.md criteria)
Titles must be noun phrases. Do not write note bodies yet.

### Step 2: Note Body Generation
For each proposed note title:
- Write the body in the source document's language
- 150-600 words
- Self-contained (reader needs no other note to understand it)
- Preserve the user's original formulations where possible
- Add context/connective tissue as needed

### Step 3: Wikilink Pass
Review all note bodies. Insert [[Title]] for:
- Explicit title mentions in text
- Semantically related concepts (even if not literally mentioned)
Target: 3-7 links per note. Links must reference titles from Step 1 ONLY.

### Step 4: Tag Assignment
For each note, select 2-5 tags from the provided tag list.
If no tag fits: use the closest available tag AND add proposed_new_tag entry.

### Step 5: MOC Generation
Generate one MOC using the source document's heading structure:
- Level 1 sections → top-level clusters
- Notes from that section → items under that cluster

### Step 6: Output
Produce the complete atom plan JSON. Output ONLY valid JSON.
```

### Tag Validation in atomize.py

```python
def validate_tags(plan: dict, valid_tags: set[str]) -> list[str]:
    """Identify tags in plan that are not in the canonical taxonomy."""
    errors = []
    for note in plan.get("notes", []):
        for tag in note.get("tags", []):
            if tag not in valid_tags:
                errors.append(f"Note '{note['title']}': non-canonical tag '{tag}'")
    return errors

# Usage: warn but don't fail — Claude may have moved it to proposed_new_tags correctly
issues = validate_tags(plan, set(load_tags()))
if issues:
    print(f"WARNING: {len(issues)} non-canonical tags found", file=sys.stderr)
    for issue in issues:
        print(f"  {issue}", file=sys.stderr)
```

---

## Data Grounding: Actual Document Measurements

Measured from the two reference .docx files with the working parser:

**"Архитектура Второго мозга" (Architecture doc):**
- 4 sections total: 1 pre-heading (59 words), 3 level-1 sections (234, 371, 66 words)
- Section [1] "Часть 1" — 234 words, 14 paragraphs → likely 1-2 atomic notes
- Section [2] "Часть 2" — 371 words, 29 paragraphs → likely 2-3 atomic notes (needs splitting)
- Section [3] "Как это будет работать" — 66 words, 1 paragraph → 1 note
- Expected atom plan: ~5-7 atomic notes + 1 MOC = 6-8 total entries

**"Smart Connections" doc:**
- 7 sections total: 1 pre-heading (18 words), 1 level-1 header with 0 content, 5 level-2 sections (69, 107, 71, 52, 101 words)
- All level-2 sections are well under 150 words → each needs Claude to add context
- Expected atom plan: ~5-6 atomic notes + 1 MOC = 6-7 total entries

**Implication for SKILL.md:** Claude must be told that short source sections (< 150 words) still produce full notes — it must ADD context and connective tissue to reach the 150-word minimum, not simply copy the section text.

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Single-shot atomization prompt | Iterative passes (title → body → links → MOC) | Eliminates title instability and broken wikilinks |
| Direct .md file generation | JSON atom plan intermediate | Enables Phase 3 validation, rollback, and batch-safe vault writes |
| Hardcoded tag list in prompt | Runtime injection from tags.yaml | SKILL.md stays version-stable as taxonomy evolves |
| Separate "Related" section for links | Inline wikilinks only | Matches user decision and Obsidian backlink graph expectations |

**Patterns from Phase 1 that carry forward unchanged:**
- Staging-first: atom plan JSON goes to /tmp/dw/staging/, not directly to vault
- Config-driven paths: staging_dir read from config.toml
- Cyrillic safety: json.dumps with ensure_ascii=False throughout

---

## Open Questions

1. **Claude CLI invocation pattern**
   - What we know: `claude --print` accepts stdin and prints response to stdout (this is the documented Claude Code CLI non-interactive mode)
   - What's unclear: Whether the claude CLI is available as `claude` in PATH on this system — not verified
   - Recommendation: atomize.py should try `claude --print` first; if not in PATH, fall back to prompting user to run manually and paste response. Add a `--dry-run` flag that prints the assembled prompt without calling Claude.

2. **Iterative vs single-shot for the reference documents**
   - What we know: Architecture doc has 371-word max section; Smart Connections has 107-word max. Both are well under truncation limits.
   - What's unclear: User's actual research documents (future, not reference docs) may be much larger.
   - Recommendation: Design for iterative (section-by-section) from the start; it works for small docs too and scales to large ones.

3. **JSON extraction from Claude's response**
   - What we know: Claude sometimes wraps JSON in markdown code fences (```json...```) even when instructed not to
   - What's unclear: Reliability of the "output ONLY JSON" instruction in practice
   - Recommendation: atomize.py must strip code fences defensively. The code example above handles this.

---

## Sources

### Primary (HIGH confidence)
- `/home/kosya/vibecoding/ObsidianDataWeave/rules/atomization.md` — verified Phase 1 artifact (557 words, working)
- `/home/kosya/vibecoding/ObsidianDataWeave/rules/taxonomy.md` — verified Phase 1 artifact (601 words, working)
- `/home/kosya/vibecoding/ObsidianDataWeave/scripts/parse_docx.py` — verified Phase 1 artifact; used to measure actual section sizes
- Hands-on parser execution against both reference .docx files — section sizes measured directly (59, 234, 371, 66, 18, 0, 69, 107, 71, 52, 101 words per section)
- `/home/kosya/.claude/skills/st-character-forge/SKILL.md` — existing SKILL.md pattern in this environment; confirms format and structure conventions
- `/home/kosya/.claude/skills/css-graphics/SKILL.md` — second SKILL.md reference confirming pattern consistency

### Secondary (MEDIUM confidence)
- Phase 1 RESEARCH.md, VERIFICATION.md, and three SUMMARY.md files — comprehensive record of what Phase 1 built and verified; all artifacts confirmed working
- CONTEXT.md for Phase 2 — user decisions; locked constraints confirmed

### Tertiary (LOW confidence, flagged for validation)
- `claude --print` stdin invocation pattern — assumed from Claude Code CLI documentation conventions; not tested on this system. Validate in plan 02-03 before writing atomize.py.
- Word expansion factor of 1.3 (source_words × 1.3 ≈ final note words) — heuristic estimate; not empirically measured on Russian text. Validate by running SKILL.md on reference docs.

---

## Metadata

**Confidence breakdown:**
- Atom plan JSON schema: HIGH — derived directly from locked requirements and Phase 1 verified artifacts
- SKILL.md structure: HIGH — matches existing SKILL.md pattern in this environment; rules files already exist
- Processing strategy (iterative passes): HIGH — two-pass wikilink requirement is architecturally sound; derived from LINK-01/LINK-02 requirements
- atomize.py skeleton: MEDIUM — Claude CLI invocation (claude --print) not yet verified on this system
- Pitfalls: HIGH — derived from concrete measurements (section sizes) and locked constraints

**Research date:** 2026-02-26
**Valid until:** 2026-03-26 (stable ecosystem; no external dependencies change frequently)

---

*Phase 2 AI Core research for ObsidianDataWeave*
*All schema designs and measurements grounded in Phase 1 verified artifacts and actual .docx parser output*
