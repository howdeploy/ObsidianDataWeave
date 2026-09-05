"""wiki_compile.py — Compile a wiki-space from raw inputs via the LLM backend.

Pipeline:
    1. Resolve project; require ``<wiki>/<slug>/SCHEMA.md`` to exist.
    2. Snapshot existing wiki-space (every page + each page's wikilink set).
    3. Select raw inputs (--since-last-compile or --raw-only <glob>).
    4. Assemble prompt: schema rules + compile rules + tag whitelist + snapshot
       JSON + raw JSON + hard preservation contract.
    5. Call rewrite backend (claude/codex via rewrite_backend.call_rewriter).
    6. Parse + semantically validate ChangeSet.
    7. Render pages + meta into a staging dir.
    8. Append a row to log.md and rebuild index.md against the post-compile
       page set (both into the same staging pass).
    9. Subprocess vault_writer.py with --on-conflict overwrite.

The ``--regenerate-index-only`` flag short-circuits steps 3-7 and rebuilds
index.md from the current on-disk page set without invoking the LLM.

Exit codes:
    0 — success (or --dry-run)
    1 — bad arguments / config
    2 — wiki-space not found              WIKI_PROJECT_NOT_FOUND
    3 — backend output failed validation  WIKI_VALIDATION_FAILED
    4 — raw selection too large           WIKI_RAW_LIMIT_EXCEEDED
    5 — wikilink preservation guard fired WIKI_LINKS_LOST
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml

try:
    from scripts.config import PROJECT_ROOT, load_config as _load_config
    from scripts.rewrite_backend import call_rewriter, write_debug_prompt
    from scripts.wiki_models import (
        ChangeSet,
        ChangeSetShapeError,
        CORE_PAGES,
        REQUIRED_FRONTMATTER,
        WIKI_NOTE_TYPE,
        WIKI_PAGE_TYPES,
        WIKI_STATUSES,
        is_valid_slug,
        is_valid_wiki_source_doc,
        parse_changeset,
    )
except ModuleNotFoundError:
    from config import PROJECT_ROOT, load_config as _load_config
    from rewrite_backend import call_rewriter, write_debug_prompt
    from wiki_models import (
        ChangeSet,
        ChangeSetShapeError,
        CORE_PAGES,
        REQUIRED_FRONTMATTER,
        WIKI_NOTE_TYPE,
        WIKI_PAGE_TYPES,
        WIKI_STATUSES,
        is_valid_slug,
        is_valid_wiki_source_doc,
        parse_changeset,
    )


SCRIPTS_DIR = Path(__file__).parent
RULES_DIR = PROJECT_ROOT / "rules"
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
FENCED_CODE_RE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
DEBUG_RESPONSE_PATH = Path("/tmp/dw/debug-response.json")


_OUTER_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```\s*\Z")


def _strip_outer_code_fence(text: str) -> str:
    """Strip a wrapping ```json fence from an LLM response, preserving inner ``` blocks.

    A naive non-greedy fence regex like ``` … ``` matches the FIRST closing ``` it
    finds — which breaks the moment the LLM's JSON body strings contain code
    examples with their own ``` fences. Anchoring the match to end-of-text with
    \\Z forces the closing fence to be the LAST one.
    """
    text = text.strip()
    fence = _OUTER_FENCE_RE.match(text)
    return fence.group(1).strip() if fence else text


def _strip_code(text: str) -> str:
    """Drop fenced/inline code spans before extracting wikilinks.

    Without this, `[[wikilinks]]` inside backticked documentation prose
    would be counted as real links and pollute the preservation guard.
    """
    text = FENCED_CODE_RE.sub("", text)
    text = INLINE_CODE_RE.sub("", text)
    return text


# ── Snapshot ─────────────────────────────────────────────────────────────────


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        fm = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        fm = {}
    if not isinstance(fm, dict):
        fm = {}
    return fm, parts[2].lstrip("\n")


def _extract_wikilink_targets(text: str) -> set[str]:
    out: set[str] = set()
    for raw in WIKILINK_RE.findall(_strip_code(text)):
        target = raw.split("|", 1)[0].split("#", 1)[0].strip()
        if target:
            out.add(target)
    return out


def snapshot_wiki_space(root: Path) -> dict[str, Any]:
    """Build an in-memory snapshot of a wiki-space. Pure; no writes."""
    if not root.exists():
        return {"slug": root.name, "exists": False, "pages": {}, "existing_links": {}}

    pages: dict[str, dict[str, Any]] = {}
    existing_links: dict[str, list[str]] = {}
    for md in root.rglob("*.md"):
        rel = str(md.relative_to(root))
        try:
            text = md.read_text(encoding="utf-8")
        except OSError:
            continue
        fm, body = _split_frontmatter(text)
        pages[rel] = {"frontmatter": fm, "body": body}
        existing_links[rel] = sorted(_extract_wikilink_targets(body))

    schema_fm = pages.get("SCHEMA.md", {}).get("frontmatter", {})
    log_text = pages.get("log.md", {}).get("body", "")
    log_tail = "\n".join(log_text.splitlines()[-20:])

    return {
        "slug": root.name,
        "exists": True,
        "mode": schema_fm.get("wiki_mode", "unknown"),
        "schema_frontmatter": schema_fm,
        "log_tail": log_tail,
        "pages": pages,
        "existing_links": existing_links,
        "all_titles": sorted({Path(rel).stem for rel in pages}),
    }


# ── Raw selection ────────────────────────────────────────────────────────────


def _is_ingested(fm: dict[str, Any]) -> bool:
    return fm.get("wiki_status") == "ingested"


def select_raw_inputs(
    snapshot: dict[str, Any],
    *,
    since_last_compile: bool,
    raw_only_glob: str | None,
) -> list[dict[str, Any]]:
    """Return raw notes to feed into this compile pass."""
    if raw_only_glob:
        matched = [
            rel for rel in snapshot["pages"]
            if rel.startswith("raw/") and Path(rel).match(raw_only_glob)
        ]
    else:
        matched = [rel for rel in snapshot["pages"] if rel.startswith("raw/")]
        if since_last_compile:
            matched = [
                rel for rel in matched
                if _is_ingested(snapshot["pages"][rel]["frontmatter"])
            ]

    out = []
    for rel in sorted(matched):
        page = snapshot["pages"][rel]
        out.append(
            {
                "rel_path": rel,
                "kind": Path(rel).parts[1] if len(Path(rel).parts) > 2 else "docs",
                "frontmatter": page["frontmatter"],
                "body": page["body"],
            }
        )
    return out


# ── Prompt assembly ──────────────────────────────────────────────────────────


def _read_rule(name: str) -> str:
    path = RULES_DIR / name
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _read_tag_whitelist() -> list[str]:
    path = PROJECT_ROOT / "wiki_tags.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: list[str] = []
    for top, subs in (data.get("tags") or {}).items():
        for sub in subs or []:
            out.append(f"{top}/{sub}")
    return sorted(out)


def assemble_prompt(
    *,
    snapshot: dict[str, Any],
    raw_batch: list[dict[str, Any]],
    mode: str,
    update_only: bool,
) -> str:
    schema_md = _read_rule("wiki_schema.md")
    compile_md = _read_rule("wiki_compile.md")
    update_md = _read_rule("wiki_update.md") if update_only else ""
    tags = _read_tag_whitelist()
    today = date.today().isoformat()
    compile_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Strip frontmatter dicts down to the keys the LLM actually needs to see;
    # full frontmatter explodes the prompt for big wikis.
    snapshot_pages = {
        rel: {
            "frontmatter": {
                k: page["frontmatter"].get(k)
                for k in ("note_type", "wiki_project", "wiki_page_type", "wiki_status",
                          "date", "source_doc", "confidence", "sources", "related")
                if k in page["frontmatter"]
            },
            "body": page["body"],
        }
        for rel, page in snapshot["pages"].items()
    }

    # default=str — YAML loads bare `date:` as datetime.date, which json
    # can't serialize natively. Coerce all non-JSON-friendly values to str.
    snapshot_json = json.dumps(
        {
            "slug": snapshot["slug"],
            "mode": snapshot.get("mode", mode),
            "log_tail": snapshot.get("log_tail", ""),
            "pages": snapshot_pages,
            "existing_links": snapshot.get("existing_links", {}),
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    )

    raw_json = json.dumps(raw_batch, ensure_ascii=False, indent=2, default=str)

    sections = [
        "# Wiki Schema (rules)",
        schema_md,
        "",
        "# Compile Contract",
        compile_md,
    ]
    if update_md:
        sections.extend(["", "# Update Contract (incremental mode)", update_md])
    sections.extend(
        [
            "",
            "# Allowed Tags (whitelist)",
            "\n".join(f"- {t}" for t in tags) or "(empty)",
            "",
            "# Snapshot of existing wiki-space (JSON)",
            "```json",
            snapshot_json,
            "```",
            "",
            "# Raw inputs to merge in this pass (JSON)",
            "```json",
            raw_json,
            "```",
            "",
            "# Compile metadata",
            f"- compile_id: {compile_id}",
            f"- date: {today}",
            f"- mode: {mode}",
            "",
            "# Hard requirement",
            "Output ONLY a single JSON object that parses as a ChangeSet "
            "(see Compile Contract). For every entry in `updates[]`, the new "
            "`body` MUST contain [[<target>]] for every target in "
            "`existing_links[<rel_path>]`. Losing any existing wikilink fails "
            "the run with WIKI_LINKS_LOST.",
        ]
    )
    return "\n".join(sections)


# ── Validation (semantic — shape is parse_changeset's job) ───────────────────


class ValidationError(ValueError):
    """Raised when a parsed ChangeSet violates semantic rules."""

    def __init__(self, message: str, *, exit_code: int = 3, marker: str = "WIKI_VALIDATION_FAILED"):
        super().__init__(message)
        self.exit_code = exit_code
        self.marker = marker


def _check_frontmatter(rel: str, fm: dict[str, Any], slug: str, errors: list[str]) -> None:
    for key in REQUIRED_FRONTMATTER:
        if key not in fm or fm[key] in (None, ""):
            errors.append(f"{rel}: frontmatter missing '{key}'")
    if fm.get("note_type") and fm["note_type"] != WIKI_NOTE_TYPE:
        errors.append(f"{rel}: note_type='{fm['note_type']}', expected '{WIKI_NOTE_TYPE}'")
    if fm.get("wiki_page_type") and fm["wiki_page_type"] not in WIKI_PAGE_TYPES:
        errors.append(f"{rel}: wiki_page_type='{fm['wiki_page_type']}' invalid")
    if fm.get("wiki_status") and fm["wiki_status"] not in WIKI_STATUSES:
        errors.append(f"{rel}: wiki_status='{fm['wiki_status']}' invalid")
    if fm.get("wiki_project") and fm["wiki_project"] != slug:
        errors.append(f"{rel}: wiki_project='{fm['wiki_project']}' != '{slug}'")
    sd = fm.get("source_doc")
    if sd and fm.get("wiki_page_type") != "raw" and not is_valid_wiki_source_doc(sd):
        errors.append(f"{rel}: source_doc='{sd}' must match wiki:<slug>:<page_type>:<stem>")


def validate_changeset(cs: ChangeSet, snapshot: dict[str, Any]) -> None:
    """Semantic validation — load-bearing checks live here.

    Raises ValidationError (exit 3) for general violations.
    Raises ValidationError(exit_code=5, marker='WIKI_LINKS_LOST') for the
    wikilink-preservation guard — this is the load-bearing safety property.
    """
    if cs.project != snapshot["slug"]:
        raise ValidationError(
            f"ChangeSet.project='{cs.project}' does not match snapshot slug='{snapshot['slug']}'"
        )

    errors: list[str] = []

    # 1. Frontmatter shape on every create / update
    for page in cs.creates:
        _check_frontmatter(page.rel_path, page.frontmatter, cs.project, errors)
    for upd in cs.updates:
        _check_frontmatter(upd.rel_path, upd.frontmatter, cs.project, errors)

    # 2. Updates must target pages that actually exist in the snapshot
    for upd in cs.updates:
        if upd.rel_path not in snapshot["pages"]:
            errors.append(
                f"updates[{upd.rel_path}]: page does not exist in snapshot — "
                "use creates[] for new pages"
            )

    # 3. Wikilink resolution: every [[link]] resolves to existing snapshot
    #    page, a page in creates[], or the explicit [[?slug]] open-question.
    known_stems = {Path(rel).stem for rel in snapshot["pages"]}
    known_titles = set()
    for page in snapshot["pages"].values():
        body = page["body"]
        for line in body.splitlines():
            if line.startswith("# "):
                known_titles.add(line[2:].strip())
                break
    for c in cs.creates:
        known_stems.add(Path(c.rel_path).stem)

    for page in list(cs.creates) + list(cs.updates):
        for target in _extract_wikilink_targets(page.body):
            if target.startswith("?"):
                continue
            if target in known_stems or target in known_titles:
                continue
            errors.append(
                f"{page.rel_path}: wikilink [[{target}]] does not resolve in this wiki-space"
            )

    # 4. Duplicate entity titles (case-insensitive)
    seen: dict[str, str] = {}
    for c in cs.creates:
        if not c.rel_path.startswith("entities/"):
            continue
        title = ""
        for line in c.body.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        key = (title or Path(c.rel_path).stem).lower()
        if key in seen:
            errors.append(
                f"creates: entity '{c.rel_path}' duplicates '{seen[key]}' (title='{title}')"
            )
        else:
            seen[key] = c.rel_path

    # 5. Low-confidence pages must open with a > [!warning] callout
    for page in list(cs.creates) + list(cs.updates):
        if page.frontmatter.get("confidence") == "low":
            head = "\n".join(page.body.splitlines()[:5])
            if "[!warning]" not in head:
                errors.append(
                    f"{page.rel_path}: confidence=low requires a `> [!warning]` "
                    "callout in the first lines of body"
                )

    if errors:
        raise ValidationError("ChangeSet failed validation:\n  - " + "\n  - ".join(errors))

    # 6. Wikilink preservation guard — separate exit code (5) so callers can
    #    treat it as a distinct failure mode from generic validation.
    lost_report: list[str] = []
    for upd in cs.updates:
        # The model's echoed list may omit or invent links. The pre-merge
        # snapshot is the source of truth for what must survive the update.
        expected = set(snapshot["existing_links"][upd.rel_path])
        actual = _extract_wikilink_targets(upd.body)
        missing = sorted(expected - actual)
        if missing:
            sample = missing[:10]
            extra = f" (+{len(missing) - 10} more)" if len(missing) > 10 else ""
            lost_report.append(f"  {upd.rel_path}: lost {sample}{extra}")
    if lost_report:
        raise ValidationError(
            "Wikilink preservation guard tripped:\n" + "\n".join(lost_report),
            exit_code=5,
            marker="WIKI_LINKS_LOST",
        )


# ── Render ChangeSet to staging ──────────────────────────────────────────────


def _render_page(frontmatter: dict[str, Any], body: str) -> str:
    fm_yaml = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{fm_yaml}\n---\n\n{body}\n"


def materialize_to_staging(cs: ChangeSet, staging_dir: Path) -> None:
    """Write each page in the ChangeSet into staging at its rel_path."""
    for page in cs.creates:
        dest = staging_dir / page.rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(_render_page(page.frontmatter, page.body), encoding="utf-8")
    for upd in cs.updates:
        dest = staging_dir / upd.rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(_render_page(upd.frontmatter, upd.body), encoding="utf-8")


# ── Index regeneration ──────────────────────────────────────────────────────


_INDEX_LOCALES: dict[str, dict[str, Any]] = {
    "en": {
        "title_prefix": "Index — ",
        "intro": (
            "Auto-regenerated by `wiki_compile.py` on every successful run. "
            "Do not edit by hand — manual changes are overwritten on next "
            "compile."
        ),
        "section_titles": {
            "core": "Core pages",
            "entities": "Entities",
            "concepts": "Concepts",
            "comparisons": "Comparisons",
            "queries": "Queries",
            "readouts": "Readouts",
        },
        "empty": "_(empty)_",
        "empty_core_corpus": "_(corpus mode — no fixed core pages)_",
    },
    "ru": {
        "title_prefix": "Индекс — ",
        "intro": (
            "Авто-перегенерируется `wiki_compile.py` при каждом успешном "
            "проходе. Не редактируй вручную — ручные правки будут "
            "перезаписаны на следующей компиляции."
        ),
        "section_titles": {
            "core": "Core-страницы",
            "entities": "Entities",
            "concepts": "Concepts",
            "comparisons": "Comparisons",
            "queries": "Queries",
            "readouts": "Readouts",
        },
        "empty": "_(пусто)_",
        "empty_core_corpus": "_(режим corpus — фиксированных core-страниц нет)_",
    },
}

_INDEX_SECTION_DIRS: tuple[tuple[str, str], ...] = (
    ("entities", "entities/"),
    ("concepts", "concepts/"),
    ("comparisons", "comparisons/"),
    ("queries", "queries/"),
    ("readouts", "readouts/"),
)


def _detect_index_lang_and_title(existing_index_body: str, slug: str) -> tuple[str, str]:
    """Recover (lang, title) from the existing index.md.

    Falls back to ``("en", slug)`` when no index exists or no known locale
    prefix matches. Preserves whatever human title ``wiki_init.py`` wrote
    on first creation so successive compiles do not silently relabel the
    space.
    """
    if not existing_index_body:
        return "en", slug
    for line in existing_index_body.splitlines():
        stripped = line.strip()
        if not stripped.startswith("# "):
            continue
        h1 = stripped[2:].strip()
        for lang, locale in _INDEX_LOCALES.items():
            prefix = locale["title_prefix"]
            if h1.startswith(prefix):
                return lang, h1[len(prefix):].strip() or slug
        return "en", h1 or slug
    return "en", slug


def _compute_post_compile_pages(
    snapshot: dict[str, Any], cs: ChangeSet | None
) -> dict[str, dict[str, Any]]:
    """Return the on-disk page set as it will look after applying ``cs``.

    Renames drop the old path; creates and updates land at their declared
    rel_path. ``cs`` may be None for the regenerate-index-only path, in
    which case the snapshot is returned unchanged.
    """
    pages = dict(snapshot.get("pages", {}))
    if cs is None:
        return pages
    for rename in cs.renames:
        old = rename.get("from") or rename.get("from_path")
        if old and old in pages:
            pages.pop(old)
    for c in cs.creates:
        pages[c.rel_path] = {"frontmatter": c.frontmatter, "body": c.body}
    for u in cs.updates:
        pages[u.rel_path] = {"frontmatter": u.frontmatter, "body": u.body}
    return pages


def _render_index_markdown(
    *,
    final_pages: dict[str, dict[str, Any]],
    slug: str,
    mode: str,
    lang: str,
    title: str,
    today: str,
) -> str:
    """Render index.md from the post-compile page set."""
    locale = _INDEX_LOCALES.get(lang) or _INDEX_LOCALES["en"]
    section_titles = locale["section_titles"]

    fm = {
        "tags": ["wiki/meta"],
        "date": today,
        "source_doc": f"wiki:{slug}:meta:index",
        "note_type": WIKI_NOTE_TYPE,
        "wiki_project": slug,
        "wiki_page_type": "meta",
        "wiki_status": "stable",
    }

    lines: list[str] = [f"# {locale['title_prefix']}{title}", "", locale["intro"], ""]

    lines.append(f"## {section_titles['core']}")
    lines.append("")
    if mode == "project":
        core_stems = sorted(
            Path(rel).stem
            for rel in final_pages
            if rel.startswith("pages/") and rel.endswith(".md")
        )
        if core_stems:
            lines.extend(f"- [[{stem}]]" for stem in core_stems)
        else:
            lines.append(locale["empty"])
    else:
        lines.append(locale["empty_core_corpus"])
    lines.append("")

    for section_key, prefix in _INDEX_SECTION_DIRS:
        lines.append(f"## {section_titles[section_key]}")
        lines.append("")
        stems = sorted(
            Path(rel).stem
            for rel in final_pages
            if rel.startswith(prefix) and rel.endswith(".md")
        )
        if stems:
            lines.extend(f"- [[{stem}]]" for stem in stems)
        else:
            lines.append(locale["empty"])
        lines.append("")

    body = "\n".join(lines).rstrip() + "\n"
    return _render_page(fm, body)


def regenerate_index_to_staging(
    staging_dir: Path,
    slug: str,
    snapshot: dict[str, Any],
    cs: ChangeSet | None,
    mode: str,
) -> None:
    """Materialize a fresh index.md into ``staging_dir/index.md``.

    The schema contract promises that index.md is auto-regenerated on every
    successful compile; this is the implementation of that promise. Caller
    is responsible for the subsequent vault_writer pass.
    """
    final_pages = _compute_post_compile_pages(snapshot, cs)
    existing_index_body = snapshot.get("pages", {}).get("index.md", {}).get("body", "")
    lang, title = _detect_index_lang_and_title(existing_index_body, slug)
    today = date.today().isoformat()
    rendered = _render_index_markdown(
        final_pages=final_pages,
        slug=slug,
        mode=mode,
        lang=lang,
        title=title,
        today=today,
    )
    dest = staging_dir / "index.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(rendered, encoding="utf-8")


def _append_log_to_staging(
    staging_dir: Path,
    slug: str,
    snapshot: dict[str, Any],
    cs: ChangeSet,
    backend: str,
    duration_s: float,
) -> None:
    """Re-emit log.md for staging with one new appended row."""
    today = date.today().isoformat()
    summary = (
        cs.log_entry.summary
        or f"compile: {len(cs.creates)} create, {len(cs.updates)} update"
    )
    new_row = f"| {today} | compile | {summary} (backend={backend}, {duration_s:.1f}s) |"

    existing = snapshot["pages"].get("log.md")
    if existing:
        body = existing["body"].rstrip() + "\n" + new_row + "\n"
        fm = existing["frontmatter"] or {}
    else:
        body = (
            "# Log — " + slug + "\n\n"
            "| Date | Event | Summary |\n"
            "|------|-------|---------|\n"
            f"{new_row}\n"
        )
        fm = {
            "tags": ["wiki/meta"],
            "date": today,
            "source_doc": f"wiki:{slug}:meta:log",
            "note_type": WIKI_NOTE_TYPE,
            "wiki_project": slug,
            "wiki_page_type": "meta",
            "wiki_status": "stable",
        }
    fm["date"] = today
    dest = staging_dir / "log.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(_render_page(fm, body), encoding="utf-8")


# ── vault_writer subprocess ──────────────────────────────────────────────────


def write_to_vault(staging_dir: Path, on_conflict: str = "overwrite") -> int:
    """Invoke vault_writer.py on the staging dir; return its exit code."""
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "vault_writer.py"),
        "--staging",
        str(staging_dir),
        "--non-interactive",
        "--on-conflict",
        on_conflict,
    ]
    print(f"INFO: invoking {' '.join(cmd)}", file=sys.stderr)
    proc = subprocess.run(cmd, check=False)
    return proc.returncode


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compile a wiki-space from raw inputs via the LLM backend."
    )
    parser.add_argument("slug", help="wiki-space slug to compile")
    parser.add_argument(
        "--since-last-compile",
        action="store_true",
        help="select raw notes whose wiki_status is still 'ingested' (default if no other selector)",
    )
    parser.add_argument(
        "--raw-only", default=None, help="glob (relative to wiki root) selecting a raw subset"
    )
    parser.add_argument(
        "--update-only",
        action="store_true",
        help="load wiki_update.md as the contract (incremental mode)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the assembled prompt to stdout and exit 0 (no LLM call, no writes)",
    )
    parser.add_argument(
        "--on-conflict", default="overwrite", choices=["skip", "overwrite", "rename", "ask"],
        help="conflict policy passed to vault_writer.py (default: overwrite)",
    )
    parser.add_argument("--backend", default="auto", choices=["auto", "claude", "codex"])
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument(
        "--regenerate-index-only",
        action="store_true",
        help=(
            "skip the LLM call and only rebuild index.md from the current "
            "on-disk page set (maintenance action; no log row added)"
        ),
    )
    args = parser.parse_args()

    if not is_valid_slug(args.slug):
        print(f"ERROR: slug '{args.slug}' is not valid kebab-case", file=sys.stderr)
        return 1

    config = _load_config(strict=True)
    vault_path = Path(config["vault"]["vault_path"]).expanduser()
    wiki_cfg = config.get("wiki", {})
    wiki_folder = wiki_cfg.get("wiki_folder", "LLM Wiki")
    max_raw = int(wiki_cfg.get("max_raw_per_compile", 30))
    wiki_root = vault_path / wiki_folder / args.slug

    if not (wiki_root / "SCHEMA.md").exists():
        print(
            f"WIKI_PROJECT_NOT_FOUND: no SCHEMA.md at {wiki_root}; run "
            f"`wiki_init.py {args.slug}` first",
            file=sys.stderr,
        )
        return 2

    snapshot = snapshot_wiki_space(wiki_root)
    mode = snapshot.get("mode", "project")

    if args.regenerate_index_only:
        staging_root = Path(config.get("rclone", {}).get("staging_dir", "/tmp/dw/staging"))
        staging_root.mkdir(parents=True, exist_ok=True)
        staging_dir = Path(tempfile.mkdtemp(prefix=f"wiki-{args.slug}-idx-", dir=staging_root))
        regenerate_index_to_staging(staging_dir, args.slug, snapshot, cs=None, mode=mode)
        rc = write_to_vault(staging_dir, on_conflict=args.on_conflict)
        if rc != 0:
            print(f"ERROR: vault_writer exited with {rc}", file=sys.stderr)
            return rc
        print(f"OK: regenerated index.md for {wiki_root}")
        return 0

    raw_batch = select_raw_inputs(
        snapshot,
        since_last_compile=args.since_last_compile or args.raw_only is None,
        raw_only_glob=args.raw_only,
    )
    if len(raw_batch) > max_raw:
        print(
            f"WIKI_RAW_LIMIT_EXCEEDED: {len(raw_batch)} raw inputs selected, "
            f"max_raw_per_compile={max_raw}. Compile in batches via --raw-only.",
            file=sys.stderr,
        )
        return 4

    print(
        f"INFO: snapshot has {len(snapshot['pages'])} pages; "
        f"selected {len(raw_batch)} raw inputs (mode={mode})",
        file=sys.stderr,
    )

    # Project-mode reminder: surface missing core pages early.
    if mode == "project":
        for core in CORE_PAGES:
            if f"pages/{core}.md" not in snapshot["pages"]:
                print(f"WARNING: project-mode core page missing: pages/{core}.md", file=sys.stderr)

    prompt = assemble_prompt(
        snapshot=snapshot, raw_batch=raw_batch, mode=mode, update_only=args.update_only
    )

    if args.dry_run:
        print(prompt)
        return 0

    if not raw_batch:
        print(
            "INFO: no raw inputs selected; nothing to compile. "
            "Use --raw-only or ingest first via wiki_ingest.py.",
            file=sys.stderr,
        )
        return 0

    debug_path = write_debug_prompt(prompt, prefix=f"wiki_compile-{args.slug}")
    print(f"INFO: prompt persisted to {debug_path}", file=sys.stderr)

    started = datetime.now(timezone.utc)
    backend, response = call_rewriter(
        prompt,
        backend=args.backend,
        timeout_seconds=args.timeout_seconds,
        project_root=PROJECT_ROOT,
    )
    duration_s = (datetime.now(timezone.utc) - started).total_seconds()
    print(f"INFO: backend={backend} returned in {duration_s:.1f}s", file=sys.stderr)

    text = _strip_outer_code_fence(response)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        DEBUG_RESPONSE_PATH.parent.mkdir(parents=True, exist_ok=True)
        DEBUG_RESPONSE_PATH.write_text(response, encoding="utf-8")
        print(
            f"WIKI_VALIDATION_FAILED: backend response is not valid JSON: {exc}\n"
            f"Raw response saved to {DEBUG_RESPONSE_PATH}",
            file=sys.stderr,
        )
        return 3

    try:
        cs = parse_changeset(data)
    except ChangeSetShapeError as exc:
        DEBUG_RESPONSE_PATH.write_text(response, encoding="utf-8")
        print(f"WIKI_VALIDATION_FAILED: ChangeSet shape error: {exc}", file=sys.stderr)
        return 3

    try:
        validate_changeset(cs, snapshot)
    except ValidationError as exc:
        DEBUG_RESPONSE_PATH.write_text(response, encoding="utf-8")
        print(f"{exc.marker}: {exc}\nRaw response saved to {DEBUG_RESPONSE_PATH}", file=sys.stderr)
        return exc.exit_code

    # Build staging dir and materialize.
    staging_root = Path(config.get("rclone", {}).get("staging_dir", "/tmp/dw/staging"))
    staging_root.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(prefix=f"wiki-{args.slug}-", dir=staging_root))

    # Persist the changeset alongside the rendered files for audit.
    (staging_dir / "changeset.json").write_text(
        json.dumps(cs.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    materialize_to_staging(cs, staging_dir)
    _append_log_to_staging(staging_dir, args.slug, snapshot, cs, backend, duration_s)
    regenerate_index_to_staging(staging_dir, args.slug, snapshot, cs, mode)

    rc = write_to_vault(staging_dir, on_conflict=args.on_conflict)
    if rc != 0:
        print(f"ERROR: vault_writer exited with {rc}", file=sys.stderr)
        return rc

    print(
        f"OK: compiled {len(cs.creates)} new page(s), "
        f"{len(cs.updates)} update(s) into {wiki_root}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
