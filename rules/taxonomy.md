# Taxonomy Rules

You are tagging, linking, and structuring atomic notes for an Obsidian vault. Follow these rules exactly.

## Tag Rules

Read canonical tags from `tags.yaml` before assigning any tags. Tags use the `domain/subtag` format (e.g., `tech/ai`, `productivity/pkm`, `productivity/zettelkasten`).

### Selection
- Assign 2-5 tags per note. Not fewer, not more.
- Prefer specific over generic: use `tech/llm` over `tech/ai` when the note discusses language models specifically.
- Match the tag to the note's primary concept, not the source document's topic.
- If no existing tag fits, propose a new one using the same `domain/subtag` format and log it to `proposed-tags.md` in the vault root. Do not invent a tag silently.

Source: "Smart Connections" contextual indexing — precise tags improve semantic clustering.

## Wikilink Rules

### Usage
- Link using Obsidian `[[Note Title]]` syntax — double brackets, exact note title, no file extension.
- Create 3-7 wikilinks per atomic note. Fewer links = missed connections; more = noise.
- Link only to note titles produced within the same processing run. Never link to titles that do not exist yet.
- Base links on semantic relationship, not keyword coincidence. Ask: "Does the linked note meaningfully extend or contrast with this note's idea?"
- Place wikilinks inline in the text where the concept appears, not only in a trailing "Related" block.

Source: "Архитектура Второго мозга" interlinking rules — backlinks build the knowledge graph; links must be meaningful, not decorative.

## MOC Rules

Create one MOC (Map of Content) per processed document.

### Structure
- MOC title: cleaned source document name (remove colons, truncate at 60 characters if needed).
- MOC mirrors the source document's heading hierarchy: H1/H2 become the two-level structure.
- MOC links to every atomic note generated from that document using `[[Note Title]]` syntax.
- Add `note_type: moc` in frontmatter. Tag with the document's domain tags.
- MOC is navigational only — no analysis, no new content.

Source: "Архитектура Второго мозга" Part 1, MOC usage rules — MOC hubs are the entry points for topic discovery.

## YAML Frontmatter Schema

Every note (atomic and MOC) begins with a YAML block. These fields are locked for v1 — do not add fields:

```yaml
---
tags: [domain/subtag, domain/subtag]
date: YYYY-MM-DD
source_doc: "Filename.docx"
note_type: atomic
---
```

- `tags`: list of `domain/subtag` strings from tags.yaml
- `date`: ISO 8601 date of processing (not original document date)
- `source_doc`: original .docx filename, verbatim, quoted if it contains colons or Cyrillic
- `note_type`: one of `atomic`, `moc`, or `source` — no other values

Treat any addition to this schema as a breaking change requiring a version bump.

## Few-Shot Example

Complete atomic note showing frontmatter, body, wikilinks, and tags working together:

```markdown
---
tags: [productivity/pkm, productivity/obsidian, tech/ai]
date: 2026-02-25
source_doc: "Архитектура Второго мозга: Синхронизация Obsidian и Claude MCP.docx"
note_type: atomic
---

# MOC как навигационный хаб в Obsidian

Карта контента (MOC) — это заметка-оглавление, которая объединяет атомарные заметки
по одной теме. MOC не содержит собственного анализа, только ссылки и структуру.

Каждый MOC помечается тегом `#productivity/moc` и служит точкой входа при работе
с конкретной темой. Плагин [[Smart Connections]] использует MOC-хабы как узловые
точки графа: заметка, связанная с MOC, косвенно связана со всеми другими заметками,
ссылающимися на тот же хаб.

MOC создаётся один раз при первичной обработке документа и обновляется при добавлении
новых атомарных заметок из того же источника.

### Связанные идеи
- [[Атомарность заметок Zettelkasten]] — принцип, на котором строится MOC-структура
- [[Векторные эмбеддинги в Smart Connections]] — как MOC влияет на семантический поиск
```

Note: The body is ~120 words, noun-phrase title, 2 inline wikilinks + 2 in Related, 3 tags, all frontmatter fields present.
