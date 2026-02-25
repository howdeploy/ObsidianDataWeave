# Atomization Rules

You are processing a research document into atomic notes for an Obsidian vault. Follow these rules exactly.

## Core Principle

One note = one idea that stands alone without reading any other note. A reader who has never seen the source document must be able to fully understand the note in isolation. If understanding the note requires reading another note first, it is not atomic.

Source: "Архитектура Второго мозга" Part 1 (atomicity rule); "Smart Connections" best practices (atomicity enables precise vector embeddings and semantic search accuracy).

## Constraints

Apply these constraints to every atomic note you produce:

- **Length:** 150-600 words per note. Below 150 = not enough substance. Above 600 = too broad, split it.
- **Title:** Noun phrase, not a sentence. Describes what the note is about, not what it claims.
  - Correct: "Векторные эмбеддинги в Smart Connections"
  - Wrong: "Как Smart Connections использует векторные эмбеддинги"
- **Focus:** One claim, one concept, or one technique per note. Not two.
- **Self-contained:** Write in complete sentences. Include enough context so the note makes sense without the source document.
- **Own words:** Rewrite source content in your own phrasing. Direct copy-paste reduces semantic search quality. Paraphrasing forces clarification of meaning.
- **Source reference:** Include the source document name in YAML frontmatter `source_doc` field, not in the note body.

## Splitting Heuristics

Split a section into multiple notes when any of these conditions are true:

### When to split
1. The section covers 2 or more distinct ideas (each can stand alone)
2. The section exceeds 600 words after removing headings and metadata
3. The section contains both a definition AND its application — split into one note defining the concept and one note showing how to apply it
4. The section heading is a list ("Principles of X" or "Rules for Y") — each list item may warrant its own note

Do not split on paragraph boundaries alone. Paragraphs within a section that develop one idea belong in one note.

## Few-Shot Examples

### Good atomic note (from "Smart Connections" reference doc)

**Title:** Векторные эмбеддинги в Smart Connections

**Content:**
Smart Connections использует математические векторные эмбеддинги для семантического поиска по базе заметок Obsidian. Каждая заметка преобразуется в числовой вектор, представляющий её смысловое содержание. Заметки с похожим смыслом получают векторы, которые находятся близко в многомерном пространстве.

При открытии заметки плагин автоматически вычисляет её вектор и находит в индексе ближайшие векторы — это и есть семантически родственные заметки, которые появляются в боковой панели без ручного поиска.

Важно: атомарность заметок напрямую влияет на точность эмбеддингов. Одна заметка с одной идеей создаёт более точный вектор, чем заметка с несколькими смешанными темами.

**Why good:** Single concept (vector embeddings), self-contained, ~130 words, noun-phrase title, no prerequisites.

---

### Bad: too broad (from "Smart Connections" reference doc)

**Title:** Smart Connections плагин

**Problem:** Would cover installation, vector embeddings, Smart Chat, pricing model, and best practices in one note — 5 distinct ideas, would exceed 600 words.

**Fix — split into separate notes:**
- "Установка и первичное индексирование Smart Connections" (installation + indexing process)
- "Векторные эмбеддинги в Smart Connections" (how vector search works)
- "Smart Chat: диалог с базой заметок" (chat interface feature)
- "Модель монетизации Smart Connections" (freemium pricing)
- "Атомарность заметок для точности семантического поиска" (best practice: why atomic notes improve results)

Each becomes a focused, self-contained note between 150-600 words.
