"""Tests for scripts/wiki_compile.py — pure functions only (no backend call)."""

from pathlib import Path

import pytest

from scripts.wiki_compile import (
    ValidationError,
    _compute_post_compile_pages,
    _detect_index_lang_and_title,
    _extract_wikilink_targets,
    _render_index_markdown,
    _split_frontmatter,
    _strip_outer_code_fence,
    materialize_to_staging,
    regenerate_index_to_staging,
    select_raw_inputs,
    snapshot_wiki_space,
    validate_changeset,
)
from scripts.wiki_models import ChangeSet, WikiPage, WikiPageUpdate


# ── Helpers ──────────────────────────────────────────────────────────────────


def _good_fm(slug: str, page_type: str, stem: str, status: str = "draft") -> dict:
    return {
        "note_type": "wiki",
        "wiki_project": slug,
        "wiki_page_type": page_type,
        "wiki_status": status,
        "date": "2026-05-15",
        "source_doc": f"wiki:{slug}:{page_type}:{stem}",
    }


def _seed_space(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    schema = (
        "---\n"
        "note_type: wiki\nwiki_project: demo\nwiki_page_type: meta\n"
        "wiki_status: stable\ndate: 2026-05-15\nwiki_mode: project\n"
        "source_doc: \"wiki:demo:meta:SCHEMA\"\n---\n\n# SCHEMA\n"
    )
    (root / "SCHEMA.md").write_text(schema, encoding="utf-8")
    arch = (
        "---\n"
        "note_type: wiki\nwiki_project: demo\nwiki_page_type: core\n"
        "wiki_status: draft\ndate: 2026-05-15\n"
        "source_doc: \"wiki:demo:core:architecture\"\n---\n\n"
        "# Architecture\n\nLinks to [[postgres]] and [[redis]].\n"
    )
    (root / "pages" / "architecture.md").parent.mkdir(parents=True, exist_ok=True)
    (root / "pages" / "architecture.md").write_text(arch, encoding="utf-8")
    pg = (
        "---\nnote_type: wiki\nwiki_project: demo\nwiki_page_type: entity\n"
        "wiki_status: draft\ndate: 2026-05-15\n"
        "source_doc: \"wiki:demo:entity:postgres\"\n---\n\n# Postgres\n"
    )
    (root / "entities" / "postgres.md").parent.mkdir(parents=True, exist_ok=True)
    (root / "entities" / "postgres.md").write_text(pg, encoding="utf-8")
    rd = pg.replace("postgres", "redis").replace("Postgres", "Redis")
    (root / "entities" / "redis.md").write_text(rd, encoding="utf-8")
    raw = (
        "---\nnote_type: wiki\nwiki_project: demo\nwiki_page_type: raw\n"
        "wiki_status: ingested\ndate: 2026-05-15\n"
        "source_doc: \"wiki:demo:raw:notes\"\n---\n\n# notes\n"
    )
    (root / "raw" / "docs" / "notes.md").parent.mkdir(parents=True, exist_ok=True)
    (root / "raw" / "docs" / "notes.md").write_text(raw, encoding="utf-8")


# ── Pure helpers ─────────────────────────────────────────────────────────────


class TestExtractWikilinks:
    def test_basic(self):
        assert _extract_wikilink_targets("hello [[foo]] world") == {"foo"}

    def test_strips_aliases_and_headings(self):
        assert _extract_wikilink_targets("[[foo|alias]] [[bar#heading]]") == {"foo", "bar"}

    def test_empty(self):
        assert _extract_wikilink_targets("no links here") == set()

    def test_ignores_inline_code(self):
        assert _extract_wikilink_targets("real [[foo]] vs prose `[[bar]]`") == {"foo"}

    def test_ignores_fenced_code(self):
        text = "real [[foo]]\n\n```markdown\n[[bar]]\n```\n"
        assert _extract_wikilink_targets(text) == {"foo"}


class TestStripOuterCodeFence:
    def test_plain_json_passes_through(self):
        assert _strip_outer_code_fence('{"a": 1}') == '{"a": 1}'

    def test_strips_json_fence(self):
        text = '```json\n{"a": 1}\n```'
        assert _strip_outer_code_fence(text) == '{"a": 1}'

    def test_strips_plain_fence(self):
        text = '```\n{"a": 1}\n```'
        assert _strip_outer_code_fence(text) == '{"a": 1}'

    def test_preserves_inner_fences(self):
        """Body strings often contain ``` examples that must survive."""
        inner = '{"body": "see ```\\nexample\\n``` here"}'
        wrapped = f"```json\n{inner}\n```"
        assert _strip_outer_code_fence(wrapped) == inner

    def test_no_fence_returns_stripped(self):
        assert _strip_outer_code_fence("  hello  ") == "hello"


class TestSplitFrontmatter:
    def test_round_trip(self):
        text = "---\nfoo: 1\n---\n\nbody"
        fm, body = _split_frontmatter(text)
        assert fm == {"foo": 1}
        assert body == "body"

    def test_no_frontmatter(self):
        fm, body = _split_frontmatter("just body")
        assert fm == {}
        assert body == "just body"


# ── Snapshot ─────────────────────────────────────────────────────────────────


class TestSnapshot:
    def test_snapshot_collects_pages_and_links(self, tmp_path: Path):
        root = tmp_path / "demo"
        _seed_space(root)
        snap = snapshot_wiki_space(root)
        assert snap["exists"] is True
        assert snap["mode"] == "project"
        assert "pages/architecture.md" in snap["pages"]
        assert set(snap["existing_links"]["pages/architecture.md"]) == {"postgres", "redis"}

    def test_snapshot_missing_root(self, tmp_path: Path):
        snap = snapshot_wiki_space(tmp_path / "nope")
        assert snap["exists"] is False
        assert snap["pages"] == {}


# ── Raw selection ────────────────────────────────────────────────────────────


class TestSelectRaw:
    def test_since_last_compile_picks_ingested(self, tmp_path: Path):
        root = tmp_path / "demo"
        _seed_space(root)
        snap = snapshot_wiki_space(root)
        chosen = select_raw_inputs(snap, since_last_compile=True, raw_only_glob=None)
        assert len(chosen) == 1
        assert chosen[0]["rel_path"] == "raw/docs/notes.md"

    def test_raw_only_glob(self, tmp_path: Path):
        root = tmp_path / "demo"
        _seed_space(root)
        snap = snapshot_wiki_space(root)
        chosen = select_raw_inputs(snap, since_last_compile=False, raw_only_glob="raw/docs/*.md")
        assert len(chosen) == 1


# ── validate_changeset ───────────────────────────────────────────────────────


def _snap(tmp_path: Path) -> dict:
    root = tmp_path / "demo"
    _seed_space(root)
    return snapshot_wiki_space(root)


class TestValidateChangeset:
    def test_valid_changeset_passes(self, tmp_path: Path):
        snap = _snap(tmp_path)
        cs = ChangeSet(
            project="demo",
            compile_id="x",
            updates=[
                WikiPageUpdate(
                    rel_path="pages/architecture.md",
                    expected_existing_links=["postgres", "redis"],
                    frontmatter=_good_fm("demo", "core", "architecture"),
                    body="# Architecture\n\n[[postgres]] and [[redis]] still here.",
                )
            ],
        )
        validate_changeset(cs, snap)  # should not raise

    def test_wrong_project_slug(self, tmp_path: Path):
        snap = _snap(tmp_path)
        cs = ChangeSet(project="other", compile_id="x")
        with pytest.raises(ValidationError, match="does not match snapshot slug"):
            validate_changeset(cs, snap)

    def test_update_to_unknown_page(self, tmp_path: Path):
        snap = _snap(tmp_path)
        cs = ChangeSet(
            project="demo",
            compile_id="x",
            updates=[
                WikiPageUpdate(
                    rel_path="pages/ghost.md",
                    expected_existing_links=[],
                    frontmatter=_good_fm("demo", "core", "ghost"),
                    body="# Ghost\n",
                )
            ],
        )
        with pytest.raises(ValidationError, match="does not exist in snapshot"):
            validate_changeset(cs, snap)

    def test_unresolved_wikilink_fails(self, tmp_path: Path):
        snap = _snap(tmp_path)
        cs = ChangeSet(
            project="demo",
            compile_id="x",
            creates=[
                WikiPage(
                    rel_path="entities/kafka.md",
                    frontmatter=_good_fm("demo", "entity", "kafka"),
                    body="# Kafka\n\nSee [[mystery-page]] for details.",
                )
            ],
        )
        with pytest.raises(ValidationError, match="\\[\\[mystery-page\\]\\]"):
            validate_changeset(cs, snap)

    def test_open_question_marker_resolves(self, tmp_path: Path):
        snap = _snap(tmp_path)
        cs = ChangeSet(
            project="demo",
            compile_id="x",
            creates=[
                WikiPage(
                    rel_path="entities/kafka.md",
                    frontmatter=_good_fm("demo", "entity", "kafka"),
                    body="# Kafka\n\nSee [[?future-page]] when it exists.",
                )
            ],
        )
        validate_changeset(cs, snap)

    def test_duplicate_entity_fails(self, tmp_path: Path):
        snap = _snap(tmp_path)
        cs = ChangeSet(
            project="demo",
            compile_id="x",
            creates=[
                WikiPage(
                    rel_path="entities/kafka.md",
                    frontmatter=_good_fm("demo", "entity", "kafka"),
                    body="# Kafka\n",
                ),
                WikiPage(
                    rel_path="entities/kafka-broker.md",
                    frontmatter=_good_fm("demo", "entity", "kafka-broker"),
                    body="# kafka\n",  # case-insensitive duplicate of "Kafka"
                ),
            ],
        )
        with pytest.raises(ValidationError, match="duplicates"):
            validate_changeset(cs, snap)

    def test_low_confidence_requires_warning(self, tmp_path: Path):
        snap = _snap(tmp_path)
        fm = _good_fm("demo", "entity", "kafka")
        fm["confidence"] = "low"
        cs = ChangeSet(
            project="demo",
            compile_id="x",
            creates=[
                WikiPage(
                    rel_path="entities/kafka.md",
                    frontmatter=fm,
                    body="# Kafka\n\nNo warning here.",
                )
            ],
        )
        with pytest.raises(ValidationError, match="\\[!warning\\]"):
            validate_changeset(cs, snap)

    def test_low_confidence_with_warning_passes(self, tmp_path: Path):
        snap = _snap(tmp_path)
        fm = _good_fm("demo", "entity", "kafka")
        fm["confidence"] = "low"
        cs = ChangeSet(
            project="demo",
            compile_id="x",
            creates=[
                WikiPage(
                    rel_path="entities/kafka.md",
                    frontmatter=fm,
                    body="> [!warning]\n> Sparse data.\n\n# Kafka\n",
                )
            ],
        )
        validate_changeset(cs, snap)

    def test_wikilink_preservation_guard_fires(self, tmp_path: Path):
        """The load-bearing safety property: lost wikilinks → exit 5."""
        snap = _snap(tmp_path)
        cs = ChangeSet(
            project="demo",
            compile_id="x",
            updates=[
                WikiPageUpdate(
                    rel_path="pages/architecture.md",
                    expected_existing_links=["postgres", "redis"],
                    frontmatter=_good_fm("demo", "core", "architecture"),
                    body="# Architecture\n\nMentions only [[postgres]] now.",
                )
            ],
        )
        with pytest.raises(ValidationError) as exc_info:
            validate_changeset(cs, snap)
        assert exc_info.value.exit_code == 5
        assert exc_info.value.marker == "WIKI_LINKS_LOST"
        assert "redis" in str(exc_info.value)

    @pytest.mark.parametrize("expected_links", [[], ["postgres"]])
    def test_guard_uses_snapshot_when_model_omits_expected_links(
        self, tmp_path: Path, expected_links: list[str]
    ):
        snap = _snap(tmp_path)
        cs = ChangeSet(
            project="demo",
            compile_id="x",
            updates=[
                WikiPageUpdate(
                    rel_path="pages/architecture.md",
                    expected_existing_links=expected_links,
                    frontmatter=_good_fm("demo", "core", "architecture"),
                    body="# Architecture\n\nOnly [[postgres]] survived.",
                )
            ],
        )
        with pytest.raises(ValidationError) as exc_info:
            validate_changeset(cs, snap)
        assert exc_info.value.exit_code == 5
        assert exc_info.value.marker == "WIKI_LINKS_LOST"
        assert "redis" in str(exc_info.value)

    @pytest.mark.parametrize(
        "expected_links", [[], ["postgres"], ["postgres", "redis", "fabricated"]]
    )
    def test_preserved_snapshot_links_pass_despite_inaccurate_model_list(
        self, tmp_path: Path, expected_links: list[str]
    ):
        snap = _snap(tmp_path)
        cs = ChangeSet(
            project="demo",
            compile_id="x",
            updates=[
                WikiPageUpdate(
                    rel_path="pages/architecture.md",
                    expected_existing_links=expected_links,
                    frontmatter=_good_fm("demo", "core", "architecture"),
                    body="# Architecture\n\n[[postgres|Database]] and [[redis#Caching]].",
                )
            ],
        )
        validate_changeset(cs, snap)


# ── materialize_to_staging ───────────────────────────────────────────────────


class TestMaterialize:
    def test_writes_creates_and_updates(self, tmp_path: Path):
        cs = ChangeSet(
            project="demo",
            compile_id="x",
            creates=[
                WikiPage(
                    rel_path="entities/kafka.md",
                    frontmatter=_good_fm("demo", "entity", "kafka"),
                    body="# Kafka\n\nLinks to [[postgres]].",
                )
            ],
            updates=[
                WikiPageUpdate(
                    rel_path="pages/architecture.md",
                    expected_existing_links=["postgres"],
                    frontmatter=_good_fm("demo", "core", "architecture"),
                    body="# Architecture\n\n[[postgres]] still here.",
                )
            ],
        )
        materialize_to_staging(cs, tmp_path)
        assert (tmp_path / "entities" / "kafka.md").exists()
        assert (tmp_path / "pages" / "architecture.md").exists()
        text = (tmp_path / "entities" / "kafka.md").read_text(encoding="utf-8")
        assert text.startswith("---\n")
        assert "wiki_project: demo" in text
        assert "[[postgres]]" in text


# ── Index regeneration ──────────────────────────────────────────────────────


class TestDetectIndexLangAndTitle:
    def test_detects_ru_locale_and_title(self):
        body = "# Индекс — Acme Project\n\nblah\n"
        assert _detect_index_lang_and_title(body, "acme") == ("ru", "Acme Project")

    def test_detects_en_locale_and_title(self):
        body = "# Index — Acme Project\n"
        assert _detect_index_lang_and_title(body, "acme") == ("en", "Acme Project")

    def test_missing_index_falls_back_to_slug(self):
        assert _detect_index_lang_and_title("", "acme") == ("en", "acme")

    def test_unknown_prefix_keeps_h1_but_defaults_lang(self):
        lang, title = _detect_index_lang_and_title("# Something Else\n", "acme")
        assert lang == "en"
        assert title == "Something Else"


class TestComputePostCompilePages:
    def test_creates_added_updates_overwrite_renames_drop_old(self):
        snapshot = {
            "pages": {
                "entities/old.md": {"frontmatter": {}, "body": "old"},
                "concepts/foo.md": {"frontmatter": {}, "body": "v1"},
            }
        }
        cs = ChangeSet(
            project="demo",
            compile_id="x",
            creates=[
                WikiPage(
                    rel_path="entities/new.md",
                    frontmatter=_good_fm("demo", "entity", "new"),
                    body="# New",
                )
            ],
            updates=[
                WikiPageUpdate(
                    rel_path="concepts/foo.md",
                    expected_existing_links=[],
                    frontmatter=_good_fm("demo", "concept", "foo"),
                    body="# Foo v2",
                )
            ],
            renames=[{"from": "entities/old.md", "to": "entities/renamed.md"}],
        )
        out = _compute_post_compile_pages(snapshot, cs)
        assert "entities/old.md" not in out
        assert "entities/new.md" in out
        assert out["concepts/foo.md"]["body"] == "# Foo v2"

    def test_none_changeset_returns_snapshot_pages(self):
        snapshot = {"pages": {"entities/x.md": {"frontmatter": {}, "body": "b"}}}
        out = _compute_post_compile_pages(snapshot, None)
        assert out == snapshot["pages"]


class TestRenderIndexMarkdown:
    def _final(self):
        return {
            "SCHEMA.md": {"frontmatter": {}, "body": ""},
            "log.md": {"frontmatter": {}, "body": ""},
            "index.md": {"frontmatter": {}, "body": ""},
            "pages/overview.md": {"frontmatter": {}, "body": ""},
            "pages/architecture.md": {"frontmatter": {}, "body": ""},
            "entities/kafka.md": {"frontmatter": {}, "body": ""},
            "entities/postgres.md": {"frontmatter": {}, "body": ""},
            "concepts/idempotency.md": {"frontmatter": {}, "body": ""},
            "comparisons/a-vs-b.md": {"frontmatter": {}, "body": ""},
            "raw/docs/note.md": {"frontmatter": {}, "body": ""},
        }

    def test_project_mode_lists_core_and_buckets_in_en(self):
        text = _render_index_markdown(
            final_pages=self._final(),
            slug="demo",
            mode="project",
            lang="en",
            title="Demo",
            today="2026-05-16",
        )
        assert "# Index — Demo" in text
        assert "## Core pages" in text
        assert "- [[architecture]]" in text
        assert "- [[overview]]" in text
        assert "## Entities" in text
        assert "- [[kafka]]" in text
        assert "- [[postgres]]" in text
        assert "- [[idempotency]]" in text
        assert "- [[a-vs-b]]" in text
        # Queries section exists even when empty.
        assert "## Queries" in text
        assert "_(empty)_" in text
        # Meta + raw pages never appear in index.
        assert "[[SCHEMA]]" not in text
        assert "[[log]]" not in text
        assert "[[note]]" not in text

    def test_corpus_mode_renders_corpus_placeholder_for_core(self):
        text = _render_index_markdown(
            final_pages={"entities/k.md": {"frontmatter": {}, "body": ""}},
            slug="demo",
            mode="corpus",
            lang="en",
            title="Demo",
            today="2026-05-16",
        )
        assert "corpus mode" in text
        assert "- [[k]]" in text

    def test_ru_locale_uses_russian_headers(self):
        text = _render_index_markdown(
            final_pages={"entities/k.md": {"frontmatter": {}, "body": ""}},
            slug="demo",
            mode="project",
            lang="ru",
            title="Демо",
            today="2026-05-16",
        )
        assert "# Индекс — Демо" in text
        assert "## Core-страницы" in text
        # Bucket headers stay language-neutral.
        assert "## Entities" in text


class TestRegenerateIndexToStaging:
    def test_writes_index_md_into_staging(self, tmp_path: Path):
        snapshot = {
            "pages": {
                "index.md": {
                    "frontmatter": {},
                    "body": "# Index — Demo\n\nold body",
                },
                "entities/kafka.md": {"frontmatter": {}, "body": "# Kafka"},
            }
        }
        regenerate_index_to_staging(
            tmp_path, slug="demo", snapshot=snapshot, cs=None, mode="project"
        )
        out = (tmp_path / "index.md").read_text(encoding="utf-8")
        assert out.startswith("---\n")
        assert "wiki_project: demo" in out
        assert "# Index — Demo" in out
        assert "- [[kafka]]" in out

    def test_includes_changeset_creates_in_listing(self, tmp_path: Path):
        snapshot = {
            "pages": {
                "index.md": {
                    "frontmatter": {},
                    "body": "# Index — Demo",
                }
            }
        }
        cs = ChangeSet(
            project="demo",
            compile_id="x",
            creates=[
                WikiPage(
                    rel_path="entities/new.md",
                    frontmatter=_good_fm("demo", "entity", "new"),
                    body="# New",
                )
            ],
        )
        regenerate_index_to_staging(
            tmp_path, slug="demo", snapshot=snapshot, cs=cs, mode="corpus"
        )
        out = (tmp_path / "index.md").read_text(encoding="utf-8")
        assert "- [[new]]" in out
        assert "corpus mode" in out
