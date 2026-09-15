"""Tests for scripts/wiki_ingest.py — frontmatter must survive any source path.

Why this file exists: `wiki_ingest` shipped without tests, and that is exactly where a
silent data-destroying bug lived. On Windows the source path was interpolated straight
into a double-quoted YAML scalar:

    raw_source: "C:\\Users\\...\\scratchpad\\file.md"

PyYAML reads `\\U` as the start of a unicode escape, aborts the scan, and the loader
returns nothing — so the WHOLE frontmatter block is lost, `wiki_status: ingested`
included. `wiki_compile.py --since-last-compile` selects on that key, so every freshly
ingested note became invisible and compile produced an empty ChangeSet while exiting 0.

The red fixtures below are that precedent verbatim, not invented inputs.
"""

from pathlib import Path

import pytest
import yaml

from scripts.wiki_ingest import _build_raw_frontmatter, write_raw_note

TODAY = "2026-09-15"

# The exact shape that broke: a Windows path whose segments start with U, T, n, x …
WINDOWS_PATH = r"C:\Users\RaphaelBos\AppData\Local\Temp\claude\scratchpad\strategy__governance.md"


def parse_frontmatter(text: str) -> dict:
    """Split and parse the YAML block the way the snapshot loader does."""
    assert text.startswith("---\n"), "frontmatter must open the note"
    _, block, _ = text.split("---", 2)
    return yaml.safe_load(block) or {}


class TestSourcePathSurvivesYaml:
    """Red side — each of these aborted the YAML scanner before the fix."""

    @pytest.mark.parametrize(
        "source",
        [
            WINDOWS_PATH,
            r"C:\Users\x\notes.md",            # \U in \Users
            r"D:\temp\file.md",                # \t is a tab escape
            r"E:\new\note.md",                 # \n is a newline escape
            r"F:\xray\doc.md",                 # \x starts a hex escape
        ],
        ids=["full-windows-path", "backslash-U", "backslash-t", "backslash-n", "backslash-x"],
    )
    def test_windows_path_keeps_frontmatter_parseable(self, source: str) -> None:
        fm = parse_frontmatter(_build_raw_frontmatter("yorxen", "note", source, TODAY))
        assert fm, "frontmatter was dropped — the YAML scanner aborted on the path"
        assert fm["raw_source"] == source, "the path did not round-trip intact"

    def test_wiki_status_survives_a_windows_path(self) -> None:
        """The key that actually mattered: --since-last-compile selects on it.

        A parseable block is not enough. If `wiki_status` is missing, the note is
        invisible to compile and the run reports success over an empty ChangeSet.
        """
        fm = parse_frontmatter(_build_raw_frontmatter("yorxen", "note", WINDOWS_PATH, TODAY))
        assert fm.get("wiki_status") == "ingested"

    @pytest.mark.parametrize(
        "source",
        [
            'C:\\dir\\file "quoted".md',       # a double quote closes the scalar early
            r"C:\Юникод\заметка.md",           # non-ASCII segments
            "https://example.test/a?b=1&c=2",  # URL input, documented in --help
            r"C:\trailing\backslash\\",        # path ending in a backslash
        ],
        ids=["double-quote", "non-ascii", "url", "trailing-backslash"],
    )
    def test_awkward_sources_keep_frontmatter_parseable(self, source: str) -> None:
        fm = parse_frontmatter(_build_raw_frontmatter("yorxen", "note", source, TODAY))
        assert fm, f"frontmatter dropped for {source!r}"
        assert fm["raw_source"] == source


class TestFrontmatterContract:
    """Green side — the keys the rest of the pipeline reads must all be present."""

    def test_posix_path_still_works(self) -> None:
        fm = parse_frontmatter(
            _build_raw_frontmatter("yorxen", "note", "/home/user/vault/note.md", TODAY)
        )
        assert fm["raw_source"] == "/home/user/vault/note.md"

    def test_required_keys_are_present(self) -> None:
        fm = parse_frontmatter(_build_raw_frontmatter("yorxen", "my-note", WINDOWS_PATH, TODAY))
        assert fm["note_type"] == "wiki"
        assert fm["wiki_page_type"] == "raw"
        assert fm["wiki_project"] == "yorxen"
        assert fm["wiki_status"] == "ingested"
        assert fm["source_doc"] == "wiki:yorxen:raw:my-note"
        assert "wiki/raw" in fm["tags"] and "wiki/ingested" in fm["tags"]


class TestWriteRawNoteEndToEnd:
    """The file on disk — not just the string — must come back parseable."""

    def test_written_note_parses_and_keeps_status(self, tmp_path: Path) -> None:
        dest = write_raw_note(
            tmp_path, "yorxen", "docs", "governance", WINDOWS_PATH, "# Заголовок\n\nтело\n", TODAY
        )
        fm = parse_frontmatter(dest.read_text(encoding="utf-8"))
        assert fm.get("wiki_status") == "ingested"
        assert fm["raw_source"] == WINDOWS_PATH

    def test_body_with_non_ascii_round_trips(self, tmp_path: Path) -> None:
        body = "# Белая линия\n\nМы не выдаём деньги и не советуем.\n"
        dest = write_raw_note(
            tmp_path, "yorxen", "docs", "white-line", WINDOWS_PATH, body, TODAY
        )
        assert body in dest.read_text(encoding="utf-8")

    def test_second_ingest_of_same_label_does_not_overwrite(self, tmp_path: Path) -> None:
        """Observed 15.09: re-ingesting one file produced `-2`, it did not replace."""
        first = write_raw_note(tmp_path, "yorxen", "docs", "note", WINDOWS_PATH, "a\n", TODAY)
        second = write_raw_note(tmp_path, "yorxen", "docs", "note", WINDOWS_PATH, "b\n", TODAY)
        assert first != second
        assert second.name == f"{TODAY}-note-2.md"
        assert first.read_text(encoding="utf-8").endswith("a\n")

    def test_unknown_raw_kind_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            write_raw_note(tmp_path, "yorxen", "nonsense", "n", WINDOWS_PATH, "x", TODAY)
