# Phase 2: AI Core - Context

**Gathered:** 2026-02-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the Claude skill (SKILL.md) that reads parsed JSON + rules and produces a complete atom plan — atomic notes with titles, bodies, tags, wikilinks, and MOC. No vault writing — that's Phase 3.

</domain>

<decisions>
## Implementation Decisions

### Atomization Strategy
- Text handling: Hybrid — preserve original phrases and formulations (user's research, user's words), but Claude adds introductory context and connective tissue so each note is self-contained
- Splitting: Claude decides based on rules/atomization.md (one idea = one note, 150-600 words). No hard word-count threshold — Claude evaluates semantic boundaries
- Language: Notes written in the language of the source document (Russian doc → Russian notes, English doc → English notes)
- Title style: Claude's discretion — picks appropriate style (noun phrase, claim, etc.) based on content

### Tag & Type Inference
- Tag selection: 2-5 tags per note from tags.yaml taxonomy
- New tags: When no existing tag fits, Claude uses the new tag BUT logs it in proposed-tags.md for user review later. Does NOT modify tags.yaml directly.
- note_type: Claude analyzes content to determine type (atomic, moc, source). MOC is always one per document. Source type used when note describes a product/book/tool.

### Wikilink Generation
- Strategy: Explicit mentions + semantic links — Claude inserts [[wikilinks]] both where titles are mentioned and where ideas are semantically related
- Placement: Inline within text only (no separate "Related notes" section at bottom)
- Scope: v1 links only to notes created in the same processing run (same document). No vault scanning.
- Limit: Claude's discretion on quantity per note (guided by rules/taxonomy.md)

### Atom Plan Output & SKILL.md Structure
- Output format: Claude's discretion (JSON file in staging vs direct .md files vs hybrid)
- SKILL.md structure: Claude's discretion (single-shot vs iterative per section vs adaptive by document size)

### Claude's Discretion
- Output format (JSON intermediate vs direct .md)
- SKILL.md processing strategy (single-shot vs iterative)
- Title style per note (noun phrase, claim, descriptive)
- Wikilink quantity per note
- When to split sections vs keep whole

</decisions>

<specifics>
## Specific Ideas

- Rules from Phase 1 (rules/atomization.md, rules/taxonomy.md) are loaded into Claude context as operating instructions
- Tags.yaml is the canonical taxonomy — Claude reads it at the start of processing
- proposed-tags.md is created/appended when Claude uses tags not in taxonomy
- Smart Connections will find cross-document links later, so v1 intra-document linking is sufficient

</specifics>

<deferred>
## Deferred Ideas

- Cross-document wikilinks (LINK-V2-02) — v2, requires vault scanning
- Dry-run mode (DOCX-V2-01) — v2
- Zettelkasten timestamp IDs (DOCX-V2-03) — v2

</deferred>

---

*Phase: 02-ai-core*
*Context gathered: 2026-02-25*
