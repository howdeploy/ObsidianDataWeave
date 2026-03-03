# Personal Notes Processing Rules

These rules extend `atomization.md` and `taxonomy.md` for processing personal Obsidian notes (written directly in the vault, not imported from .docx).

## Source Convention

- `source_doc` is always `"Личная заметка"` — not a filename, not a path.
- This distinguishes personal notes from imported .docx documents in the registry and frontmatter.

## Voice Preservation

Personal notes carry the author's voice. Processing must preserve it:

- **Do not rewrite** existing sentences. Add context around them, not instead of them.
- **Do not change tone.** If the author writes casually, keep it casual. If formally — keep it formal.
- **Expand, don't replace.** When adding context (enrich mode), insert introductory framing or connective tissue between existing paragraphs. Do not remove or rephrase the author's original text.
- **Preserve structure.** If the author used lists, keep them as lists. If they used paragraphs, keep paragraphs.

## Wikilink Priority

When inserting `[[wikilinks]]`, follow this priority order:

1. **Existing vault notes** — always prefer linking to notes that already exist in the vault. These are provided as `vault_titles` in the input JSON.
2. **New notes from current processing run** — only applicable in atomize mode. Link to titles generated in Step 1.
3. **Never invent links** to notes that don't exist in either category.

Vault titles take absolute priority. If a concept matches both a vault title and a potential new note title, link to the vault title.

## Enrich Mode Constraints

Enrich mode processes a single note without splitting:

- **Do not split** the note into multiple notes. One note in → one note out.
- **Minimum body length:** 150 words after enrichment. If the original is shorter, add enough context to reach 150 words.
- **Maximum body length:** 600 words. If the original exceeds 600 words and has a single idea, trim tangential content. If it has multiple ideas, switch to atomize mode.
- **Wikilinks:** 3–7 inline wikilinks to existing vault notes.
- **Tags:** 2–5 from `tags.yaml`.
- **Title:** If the original title is generic ("Без названия", "Untitled", "New Note") or empty, propose a noun-phrase title based on the content. Otherwise, keep the original title.

## Atomize Mode Constraints

Atomize mode splits a long/multi-topic note into atomic notes + MOC:

- All rules from `atomization.md` apply.
- **Title collision check:** New note titles must not collide with existing `vault_titles`. If a collision would occur, differentiate the title (e.g., add a qualifier).
- **MOC title:** `"{Original Note Title} — MOC"` (not the source document name, since there is no .docx).
- **Wikilinks:** May reference both existing vault notes AND new notes from the current run.

## Edge Cases

- **Empty notes** (< 20 words body): reject with an error. Do not process.
- **Already processed notes** (have frontmatter with `source_doc` and `note_type` fields): skip with a warning. Do not re-process unless explicitly forced.
- **Notes with existing wikilinks:** Preserve them. Add new wikilinks alongside existing ones, but do not duplicate.
- **Notes with existing tags in frontmatter:** Merge — keep existing tags, add new ones up to the 5-tag maximum.
