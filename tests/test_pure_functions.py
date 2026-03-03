"""Tests for pure functions across ObsidianDataWeave scripts."""

import json
from pathlib import Path

import pytest

from scripts.generate_notes import sanitize_filename, render_note_md
from scripts.vault_writer import parse_frontmatter
from scripts.atomize import extract_json, validate_atom_plan
from scripts.audit_vault import NoteRecord, audit_notes, extract_wikilink_targets
from scripts.enrich_thin_notes import (
    ENRICH_HEADER,
    append_enrichment,
    build_enrichment_paragraphs,
    is_thin_atomic,
)
from scripts.archive_empty_notes import archive_destination


# ── sanitize_filename ─────────────────────────────────────────────────────────


class TestSanitizeFilename:
    def test_basic(self):
        assert sanitize_filename("Hello World") == "Hello World"

    def test_removes_forbidden_chars(self):
        result = sanitize_filename('File: "Test" <1>')
        assert ":" not in result
        assert '"' not in result
        assert "<" not in result
        assert ">" not in result

    def test_strips_whitespace(self):
        assert sanitize_filename("  spaces  ") == "spaces"

    def test_truncation(self):
        long_title = "A" * 300
        result = sanitize_filename(long_title, max_bytes=200)
        assert len(result.encode("utf-8")) <= 200

    def test_unicode_preserved(self):
        result = sanitize_filename("Привет мир")
        assert result == "Привет мир"

    def test_unicode_truncation(self):
        # Cyrillic chars are 2 bytes each in UTF-8
        title = "Б" * 150  # 300 bytes
        result = sanitize_filename(title, max_bytes=200)
        assert len(result.encode("utf-8")) <= 200


# ── parse_frontmatter ─────────────────────────────────────────────────────────


class TestParseFrontmatter:
    def test_no_frontmatter(self):
        assert parse_frontmatter("Just text") == {}

    def test_basic_frontmatter(self):
        content = "---\ntags:\n  - ai/llm\ndate: 2026-01-01\nnote_type: atomic\n---\nBody text"
        result = parse_frontmatter(content)
        assert result["tags"] == ["ai/llm"]
        # PyYAML parses bare dates as datetime.date objects
        from datetime import date
        assert result["date"] == date(2026, 1, 1)
        assert result["note_type"] == "atomic"

    def test_multiple_tags(self):
        content = "---\ntags:\n  - dev/python\n  - ai/llm\n  - tools/cli\n---\n"
        result = parse_frontmatter(content)
        assert len(result["tags"]) == 3
        assert "dev/python" in result["tags"]

    def test_source_doc_with_colon(self):
        content = '---\nsource_doc: "Research: AI"\nnote_type: atomic\n---\n'
        result = parse_frontmatter(content)
        assert result["source_doc"] == "Research: AI"

    def test_empty_frontmatter(self):
        content = "---\n---\nBody"
        result = parse_frontmatter(content)
        # yaml.safe_load returns None for empty string
        assert result == {}

    def test_invalid_yaml(self):
        content = "---\n: : invalid\n\t\tbad: yaml\n---\n"
        result = parse_frontmatter(content)
        assert isinstance(result, dict)


# ── extract_json ──────────────────────────────────────────────────────────────


class TestExtractJson:
    def test_plain_json(self):
        result = extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_json_in_code_fence(self):
        result = extract_json('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_json_in_plain_fence(self):
        result = extract_json('```\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_json_with_surrounding_text(self):
        text = 'Here is the result:\n```json\n{"notes": []}\n```\nDone.'
        result = extract_json(text)
        assert result == {"notes": []}

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="Failed to parse JSON"):
            extract_json("not json at all")


# ── validate_atom_plan ────────────────────────────────────────────────────────


class TestValidateAtomPlan:
    def test_missing_notes_key(self):
        errors = validate_atom_plan({})
        assert any("missing" in e.lower() and "notes" in e.lower() for e in errors)

    def test_valid_plan(self):
        plan = {
            "notes": [
                {
                    "id": "note-001",
                    "title": "Test Note",
                    "note_type": "atomic",
                    "tags": ["ai/llm", "dev/python"],
                    "source_doc": "test.docx",
                    "date": "2026-01-01",
                    "body": "Some text",
                    "proposed_new_tags": [],
                },
                {
                    "id": "moc-001",
                    "title": "Test MOC",
                    "note_type": "moc",
                    "tags": ["ai/llm", "dev/python"],
                    "source_doc": "test.docx",
                    "date": "2026-01-01",
                    "body": "MOC body",
                    "proposed_new_tags": [],
                },
            ]
        }
        errors = validate_atom_plan(plan)
        assert errors == []

    def test_missing_fields(self):
        plan = {"notes": [{"id": "note-001", "title": "Test"}]}
        errors = validate_atom_plan(plan)
        assert len(errors) > 0


# ── render_note_md ────────────────────────────────────────────────────────────


class TestRenderNoteMd:
    def test_basic_render(self):
        note = {
            "title": "Test",
            "tags": ["ai/llm"],
            "date": "2026-01-01",
            "source_doc": "doc.docx",
            "note_type": "atomic",
            "body": "Hello world",
        }
        md = render_note_md(note)
        assert md.startswith("---\n")
        assert "ai/llm" in md
        assert "Hello world" in md
        assert "atomic" in md

    def test_source_doc_quoted(self):
        note = {
            "title": "T",
            "tags": [],
            "date": "2026-01-01",
            "source_doc": "My Doc: Special",
            "note_type": "atomic",
            "body": "Text",
        }
        md = render_note_md(note)
        assert '"My Doc: Special"' in md


class TestAuditVault:
    def make_note(self, title: str, body: str, *, frontmatter=None, note_type="atomic"):
        if frontmatter is None:
            frontmatter = {}
        return NoteRecord(
            path=Path(f"/tmp/{title}.md"),
            title=title,
            note_type=note_type,
            source_doc=str(frontmatter.get("source_doc", "")),
            frontmatter=frontmatter,
            body=body,
            tags=set(frontmatter.get("tags", [])),
            links=set(),
        )

    def test_frontmatter_only_note_is_not_counted_as_empty(self):
        report = audit_notes(
            [
                self.make_note(
                    "Dashboard",
                    "",
                    frontmatter={"cssclasses": ["dashboard"], "banner": "[[banner.png]]"},
                    note_type="",
                )
            ]
        )
        assert report["summary"]["empty_notes"] == 0

    def test_extract_wikilink_targets_normalizes_alias_and_heading(self):
        links = extract_wikilink_targets(
            "Body [[Target Note|custom text]] and [[Second Note#Section]] and [[Plain Note]]."
        )
        assert links == {"Target Note", "Second Note", "Plain Note"}


class TestThinNoteEnricher:
    def make_note(self, title: str, body: str):
        return NoteRecord(
            path=Path(f"/tmp/{title}.md"),
            title=title,
            note_type="atomic",
            source_doc="source.docx",
            frontmatter={"source_doc": "source.docx", "note_type": "atomic"},
            body=body,
            tags={"tech/automation"},
            links={"One"},
        )

    def test_is_thin_atomic(self):
        assert is_thin_atomic(self.make_note("Thin", "word " * 10), min_words=80) is True

    def test_build_enrichment_for_subprocess_note_mentions_worker(self):
        paragraphs = build_enrichment_paragraphs(
            self.make_note("Вызов Codex CLI через subprocess в Python", "Body"),
            ["CLI-автоматизация Claude Code через subprocess", "Система сборки Flipper Zero на Python"],
        )
        assert "subprocess.run" in paragraphs[0]
        assert "[[CLI-автоматизация Claude Code через subprocess]]" in paragraphs[1]

    def test_append_enrichment_is_idempotent(self):
        content = "Body text\n\n## Related\n- [[One]]\n"
        updated = append_enrichment(content, ["Paragraph one.", "Paragraph two."])
        assert ENRICH_HEADER in updated
        assert updated.count(ENRICH_HEADER) == 1
        assert append_enrichment(updated, ["Paragraph one."]) == updated


class TestArchiveEmptyNotes:
    def test_archive_destination_preserves_relative_path(self):
        vault = Path("/vault")
        note = vault / "Area" / "Empty.md"
        destination = archive_destination(vault, note, stamp="2026-03-03")
        assert destination == vault / ".archive" / "empty-notes" / "2026-03-03" / "Area" / "Empty.md"
