---
tags:
  - productivity/zettelkasten
  - productivity/pkm
date: 2026-02-26
source_doc: "Example Document.docx"
note_type: atomic
---

# The Atomic Note Principle: One Idea Per Note

An atomic note captures exactly one idea — no more, no less. This constraint seems limiting at first, but it is the foundation of a knowledge system that actually scales. When each note contains a single, self-contained idea, the note becomes reusable across many different contexts without dragging along unrelated material.

The practical implication is clarity of scope: if you find yourself writing "and also..." in a note, that is a signal to split. The goal is a note that could be read in isolation by someone with no prior context and still convey a complete thought. [[Semantic Search with Smart Connections]] works best when each unit of text represents a coherent concept — mixed-topic notes dilute the embedding vector and produce weaker similarity matches.

## Why Atomicity Matters for Linking

When ideas are separated into individual notes, every idea becomes linkable. A dense paragraph buried in a ten-page document is effectively invisible to a knowledge graph. Once extracted as an atomic note, that same idea can appear as a node in multiple [[MOC as Navigation Hub]] files, showing up wherever it is conceptually relevant.

This is not just aesthetics. The link between two atomic notes is a claim — you are asserting that these two ideas are connected in a meaningful way. Over time, the pattern of connections reveals your actual mental model of a domain, which is more valuable than any individual note.

## Practical Guidelines

- Write the note title as a complete thought (not "PKM" but "Why atomic notes scale better than hierarchical folders")
- Keep body length between 150-400 words
- Add 1-3 wikilinks to related concepts you have already captured
- Tag with the domain taxonomy from `tags.yaml` (e.g., `productivity/zettelkasten`)

This note was generated from `Example Document.docx` as a demonstration of the v1 frontmatter schema used by ObsidianDataWeave.
