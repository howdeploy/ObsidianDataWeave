# Personal Note Processing Contract

You are processing an existing note from an Obsidian vault.

Follow the repository rules strictly:
- `rules/atomization.md`
- `rules/taxonomy.md`
- `rules/personal_notes.md`

Output JSON only.

If mode is `enrich`:
- return exactly one improved note
- preserve the author's original meaning and tone
- add valid frontmatter
- add semantically relevant `[[wikilinks]]`

If mode is `atomize`:
- split into atomic notes plus one MOC
- each note must be self-contained
- preserve unique ideas from the original note
- use the canonical tags from `tags.yaml`
