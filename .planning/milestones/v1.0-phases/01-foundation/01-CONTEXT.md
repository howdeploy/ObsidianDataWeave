# Phase 1: Foundation - Context

**Gathered:** 2026-02-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Lock config schema, build .docx fetch + parse pipeline, distill methodology rules from two reference documents. No AI analysis, no vault writing — those are Phase 2 and 3.

</domain>

<decisions>
## Implementation Decisions

### JSON Parser Output
- Inline formatting preserved as markdown (**bold**, *italic*, [links](url))
- Images marked as `[image]` placeholders in text flow
- Tables and lists handling — Claude's discretion (markdown or structured JSON)
- Heading granularity for sections — Claude's discretion (optimize for atomization input)

### Tag Taxonomy
- Language: English tags only (`#tech/ai`, not `#тех/ии`) — universal for GitHub package
- Hierarchy: Nested tags using `/` separator (`#tech/ai`, `#tech/python`, `#productivity/pkm`)
- Broad spectrum: tech, productivity, science, personal, creative, business, health
- Auto-expansion: Claude can add new tags to tags.yaml when nothing fits — no strict lock
- Starter taxonomy: ~30-50 tags covering wide range of research topics

### Rules Distillation
- File structure — Claude's discretion (one file or modular by aspect)
- Must include few-shot examples of good atomic notes alongside rules
- Rules language: English (better for LLM instruction following)
- Examples can be bilingual (EN rules, RU examples from actual content)
- Source: two .docx files in project root, distilled into rules/*.md

### Claude's Discretion
- JSON output schema design (fields, nesting)
- Section granularity (H2 vs H3 as split boundary)
- Tables/lists representation format
- Rules file organization (single vs modular)

</decisions>

<specifics>
## Specific Ideas

- README needs language switcher (RU/EN) — noted for Phase 4
- Rules should be practical, not academic — Claude follows them as operating instructions
- Few-shot examples are critical — show what a good atomic note looks like

</specifics>

<deferred>
## Deferred Ideas

- README language switcher (RU/EN button) — Phase 4: Publish
- Bilingual README — Phase 4: Publish

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-02-25*
