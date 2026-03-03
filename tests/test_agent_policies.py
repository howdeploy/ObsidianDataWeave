"""Tests for non-interactive agent policy branches."""

from datetime import date
from pathlib import Path

from scripts import dedup_vault
from scripts.dedup_vault import CandidateGroup, VaultNote, interactive_merge
from scripts.fix_similar_notes import (
    append_related_link,
    build_canonical_body,
    choose_canonical_title,
    deterministic_fix_pairs,
    PairCandidate,
)
from scripts.fix_atomic_notes import is_target_note, rank_related_candidates
from scripts.vault_writer import resolve_conflict


def make_group() -> CandidateGroup:
    note = VaultNote(
        path=Path("/tmp/example.md"),
        title="Example",
        body="Body text for testing.",
        tags=["ai/llm"],
        note_type="atomic",
        source_doc="source.docx",
        word_count=4,
    )
    return CandidateGroup(
        group_id=1,
        notes=[note],
        pairs=[],
        is_duplicate=True,
        confidence=0.9,
        canonical_title="Canonical Example",
        canonical_tags=["ai/llm"],
        canonical_body="Merged body",
    )


class TestResolveConflictPolicy:
    def test_non_interactive_skip(self):
        assert resolve_conflict(
            "Title",
            "source.docx",
            non_interactive=True,
            on_conflict="skip",
        ) == "skip"

    def test_non_interactive_overwrite(self):
        assert resolve_conflict(
            "Title",
            "source.docx",
            non_interactive=True,
            on_conflict="overwrite",
        ) == "overwrite"


class TestInteractiveMergePolicy:
    def test_non_interactive_keep_marks_reviewed(self):
        reviewed: list[dict] = []
        title_map = interactive_merge(
            [make_group()],
            config={},
            vault_path=Path("/tmp"),
            reviewed=reviewed,
            dry_run=False,
            non_interactive=True,
            decision="keep",
        )

        assert title_map == {}
        assert reviewed[0]["decision"] == "keep"
        assert reviewed[0]["titles"] == ["Example"]

    def test_non_interactive_merge_executes_merge(self, monkeypatch):
        reviewed: list[dict] = []
        merge_called = {"value": False}
        registry_called = {"value": False}

        def fake_execute_merge(group, config, vault_path):
            merge_called["value"] = True
            return {"Example": "Canonical Example"}

        def fake_update_registry_after_merge(group, canonical_title):
            registry_called["value"] = True

        monkeypatch.setattr(dedup_vault, "execute_merge", fake_execute_merge)
        monkeypatch.setattr(
            dedup_vault,
            "update_registry_after_merge",
            fake_update_registry_after_merge,
        )

        title_map = interactive_merge(
            [make_group()],
            config={},
            vault_path=Path("/tmp"),
            reviewed=reviewed,
            dry_run=False,
            non_interactive=True,
            decision="merge",
        )

        assert title_map == {"Example": "Canonical Example"}
        assert merge_called["value"] is True
        assert registry_called["value"] is True
        assert reviewed[0]["decision"] == "merge"


class TestAppendRelatedLink:
    def test_appends_related_section_when_missing(self):
        content = "Body text\n"
        updated = append_related_link(content, "Target Note")
        assert "## Related" in updated
        assert "[[Target Note]]" in updated

    def test_does_not_duplicate_existing_link(self):
        content = "Body text\n\n## Related\n- [[Target Note]]\n"
        updated = append_related_link(content, "Target Note")
        assert updated.count("[[Target Note]]") == 1

    def test_appends_into_existing_related_section(self):
        content = "Body text\n\n## Related\n- [[One]]\n"
        updated = append_related_link(content, "Two")
        assert "## Related" in updated
        assert "[[One]]" in updated
        assert "[[Two]]" in updated


class TestDeterministicFixer:
    def make_note(self, title: str, body: str, *, source_doc: str = "source.docx"):
        return VaultNote(
            path=Path(f"/tmp/{title}.md"),
            title=title,
            body=body,
            tags=["tech/ai", "tech/tools"],
            note_type="atomic",
            source_doc=source_doc,
            word_count=len(body.split()),
        )

    def test_choose_canonical_title_prefers_shorter_variant(self):
        a = self.make_note("Система инструментов агента в Claude Agent SDK", "Body one")
        b = self.make_note("Система инструментов Claude Agent SDK", "Body two")
        assert choose_canonical_title(a, b) == "Система инструментов Claude Agent SDK"

    def test_build_canonical_body_keeps_unique_paragraphs(self):
        a = self.make_note("A", "Para one.\n\nShared.\n\n[[Link A]]")
        b = self.make_note("B", "Shared.\n\nPara two.\n\n[[Link B]]")
        body = build_canonical_body(a, b, "Canonical")
        assert "Para one." in body
        assert "Para two." in body
        assert body.count("Shared.") == 1
        assert "[[Link A]]" in body
        assert "[[Link B]]" in body

    def test_deterministic_fix_pairs_merges_high_similarity_same_source(self):
        a = self.make_note("Alpha Agent SDK", "Sentence one. Shared paragraph.")
        b = self.make_note("Alpha SDK", "Shared paragraph. Sentence two.")
        pair = PairCandidate(pair_id=1, a=a, b=b, score=0.93)
        result = deterministic_fix_pairs([pair])
        item = result["pairs"][0]
        assert item["action"] == "merge"
        assert item["canonical_title"] in {"Alpha Agent SDK", "Alpha SDK"}

    def test_deterministic_fix_pairs_links_mid_similarity(self):
        a = self.make_note("One", "Body a", source_doc="a.docx")
        b = self.make_note("Two", "Body b", source_doc="b.docx")
        pair = PairCandidate(pair_id=2, a=a, b=b, score=0.82)
        result = deterministic_fix_pairs([pair])
        assert result["pairs"][0]["action"] == "link"


class TestAtomicLinkFixer:
    def make_atomic(self, title: str, body: str, *, tags=None, source_doc="doc.docx", links=None):
        if tags is None:
            tags = {"tech/ai", "tech/tools"}
        if links is None:
            links = set()
        note = type("AuditNote", (), {})()
        note.path = Path(f"/tmp/{title}.md")
        note.title = title
        note.note_type = "atomic"
        note.source_doc = source_doc
        note.body = body
        note.tags = set(tags)
        note.links = set(links)
        note.words = len(body.split())
        return note

    def test_is_target_note_for_thin_atomic(self):
        note = self.make_atomic("Thin", "few words only")
        assert is_target_note(note, min_words=80) is True

    def test_is_target_note_for_isolated_atomic(self):
        note = self.make_atomic("Long", "word " * 100, links=set())
        assert is_target_note(note, min_words=80) is True

    def test_rank_related_candidates_prefers_same_source(self):
        note = self.make_atomic("Alpha SDK", "word " * 20, tags={"tech/ai"}, source_doc="same.docx")
        same = self.make_atomic("Alpha Agent SDK", "word " * 20, tags={"tech/ai"}, source_doc="same.docx")
        other = self.make_atomic("Completely Different", "word " * 20, tags={"business/strategy"}, source_doc="other.docx")
        ranked = rank_related_candidates(note, [note, same, other], threshold=0.34, max_links=3)
        assert ranked
        assert ranked[0][1].title == "Alpha Agent SDK"


class TestExecuteMerge:
    def test_execute_merge_preserves_canonical_when_title_matches_duplicate(self, tmp_path, monkeypatch):
        vault = tmp_path / "vault"
        vault.mkdir()
        note_path = vault / "Canonical.md"
        note_path.write_text("---\nnote_type: atomic\n---\nOld body\n", encoding="utf-8")
        other_path = vault / "Variant.md"
        other_path.write_text("---\nnote_type: atomic\n---\nOther body\n", encoding="utf-8")

        group = CandidateGroup(
            group_id=1,
            notes=[
                VaultNote(
                    path=note_path,
                    title="Canonical",
                    body="Old body",
                    tags=["tech/tools"],
                    note_type="atomic",
                    source_doc="source.docx",
                    word_count=2,
                ),
                VaultNote(
                    path=other_path,
                    title="Variant",
                    body="Other body",
                    tags=["tech/tools"],
                    note_type="atomic",
                    source_doc="source.docx",
                    word_count=2,
                ),
            ],
            pairs=[("Canonical", "Variant", 0.95)],
            is_duplicate=True,
            confidence=0.95,
            canonical_title="Canonical",
            canonical_tags=["tech/tools"],
            canonical_body="Merged body",
        )

        monkeypatch.setattr(dedup_vault, "get_vault_dest", lambda note_type, config: vault)
        monkeypatch.setattr(dedup_vault, "date", type("FakeDate", (), {"today": staticmethod(lambda: date(2026, 3, 3))}))

        title_map = dedup_vault.execute_merge(group, config={}, vault_path=vault)

        assert title_map == {"Canonical": "Canonical", "Variant": "Canonical"}
        assert (vault / "Canonical.md").exists()
        assert "Merged body" in (vault / "Canonical.md").read_text(encoding="utf-8")
        assert (vault / ".archive" / "2026-03-03_dedup_Canonical.md").exists()
        assert (vault / ".archive" / "2026-03-03_dedup_Variant.md").exists()
