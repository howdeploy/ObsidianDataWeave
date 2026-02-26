# ObsidianDataWeave Atomization Skill

You receive a parsed document (JSON) and produce a complete atom plan (JSON).

Context is injected at runtime by `atomize.py`: canonical tag list from `tags.yaml` and rule files from `rules/`.

---

## Input Format

Parsed JSON from `parse_docx.py`:

```
{
  "source_file": "Filename.docx",
  "heading_depth_offset": 0,
  "sections": [
    {"heading": null, "level": 0, "paragraphs": ["..."]},
    {"heading": "Section Title", "level": 2, "paragraphs": ["...", "..."]}
  ]
}
```

- `sections[0]` may have `heading: null` (pre-heading content — treat as intro material)
- `paragraphs` is a list of strings; tables appear as `"[TABLE: col1 | col2 | ...]"` entries

---

## Processing Steps

### Step 1: Title Enumeration Pass

For each section in the parsed JSON:

- Estimate final note length: `source_words × 1.3` (expansion factor for context-adding)
- If estimated > 600 words OR section contains 2+ distinct ideas: split into multiple notes with separate titles
- If estimated < 150 words: note will need substantial context — plan to add introductory framing
- Output: complete list of all proposed note titles in noun-phrase style (see `rules/atomization.md`)
- **Do NOT write note bodies yet**

### Step 2: Note Body Generation

For each title from Step 1:

- Write body in the source document's language (Russian doc → Russian notes, English doc → English notes)
- Target: 150–600 words per note
- Hybrid approach: preserve original phrases and formulations, but add introductory context and connective tissue so each note is fully self-contained
- **Do NOT insert wikilinks yet** — write plain text bodies only

### Step 3: Wikilink Insertion Pass

Review all note bodies against the confirmed title list from Step 1:

- Insert `[[Title]]` for explicit title mentions in text
- Insert `[[Title]]` for semantically related concepts (even if not literally mentioned)
- Place wikilinks inline in text only — **no separate "Related notes" section at bottom**
- Target: 3–7 wikilinks per note
- **Use EXACTLY the titles from Step 1 — do not rephrase or paraphrase in link targets**

### Step 4: Tag Assignment

For each note, select 2–5 tags from the injected tag list:

- Prefer specific over generic (`tech/llm` over `tech/ai` when discussing language models)
- Match tags to the note's primary concept, not the source document topic
- If NO tag fits: use closest available AND add entry to `proposed_new_tags`: `{"tag": "domain/subtag", "reason": "why needed"}`
- Determine `note_type`: `"atomic"` (default), `"moc"` (one per document, Step 5), `"source"` (when note describes a product/book/tool)

### Step 5: MOC Generation

Generate exactly one MOC note — **always last, after all atomic note titles are finalized**:

- Title: cleaned source document name (remove file extension, strip colons, truncate at 60 chars) + `" — MOC"`
- Body: starts directly with content (NO `# Title` H1 heading — Obsidian uses filename as title). Two-level hierarchy mirroring source document headings — Level 1 sections become `##` headers; notes from each section listed as `[[wikilinks]]` under their parent heading
- `note_type: "moc"`, tags: document's primary domain tags
- MOC is navigational only — no analysis, no new content

### Step 6: JSON Output

Output the complete atom plan as a single JSON object. **Output ONLY valid JSON — no prose, no markdown code fences.**

---

## Output Schema

```
{
  "schema_version": "1",
  "source_file": "Filename.docx",
  "processed_date": "YYYY-MM-DD",
  "notes": [
    {
      "id": "note-001",
      "title": "Exact Note Title",
      "note_type": "atomic",
      "tags": ["domain/subtag", "domain/subtag"],
      "source_doc": "Filename.docx",
      "date": "YYYY-MM-DD",
      "body": "Note body in markdown with [[wikilinks]] inline.",
      "proposed_new_tags": []
    }
  ],
  "proposed_tags": [{"tag": "domain/subtag", "reason": "..."}]
}
```

Field definitions:

- `id`: `"note-001"` through `"note-NNN"`; use `"moc-001"` for the MOC note
- `title`: exact note filename without `.md`; MUST match `[[wikilink]]` targets exactly
- `note_type`: `"atomic"` | `"moc"` | `"source"`
- `tags`: 2–5 strings from `tags.yaml` in `domain/subtag` format
- `source_doc`: verbatim `.docx` filename
- `date`: ISO 8601 processing date
- `body`: complete note body in markdown with `[[wikilinks]]` inline; no YAML frontmatter
- `proposed_new_tags`: list of `{"tag", "reason"}` for tags not in `tags.yaml`
- `proposed_tags` (top-level): aggregated list of all `proposed_new_tags` across notes

---

## Critical Constraints

- Tags MUST come from the provided tag list ONLY. If none fit, use closest match AND add `proposed_new_tag`.
- Wikilink targets MUST match titles from Step 1 exactly. Do not rephrase or paraphrase titles in links.
- Every note MUST be self-contained — a reader unfamiliar with the source document must understand it fully.
- MOC is generated LAST, after all atomic note titles are finalized.
- Do NOT add YAML frontmatter in the `body` field — frontmatter fields are separate JSON fields.
- Do NOT embed `tags.yaml` content or rules file content directly — these are injected at runtime.

---

## Few-Shot Example

### Input (parsed JSON section)

```json
{
  "heading": "Семантический поиск в Smart Connections",
  "level": 2,
  "paragraphs": [
    "Smart Connections использует векторные эмбеддинги для поиска по базе заметок. Каждая заметка преобразуется в числовой вектор.",
    "Атомарность заметок напрямую влияет на точность эмбеддингов: одна идея — один точный вектор."
  ]
}
```

### Output (atom plan entry)

```json
{
  "id": "note-001",
  "title": "Векторные эмбеддинги в Smart Connections",
  "note_type": "atomic",
  "tags": ["tech/ai", "productivity/obsidian"],
  "source_doc": "Smart Connections: Интеллектуальный мозг вашей базы Obsidian.docx",
  "date": "2026-02-26",
  "body": "Smart Connections использует векторные эмбеддинги для семантического поиска по базе заметок Obsidian. Каждая заметка преобразуется в числовой вектор; заметки со схожим смыслом получают близкие векторы.\n\n[[Атомарность заметок Zettelkasten]] напрямую влияет на точность эмбеддингов: одна заметка — одна идея — один точный вектор. Это делает [[Принцип одной идеи в PKM]] техническим требованием, а не только методологическим советом.",
  "proposed_new_tags": []
}
```
