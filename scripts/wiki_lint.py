"""wiki_lint.py — Read-only integrity checker for LLM Wiki spaces.

Walks one or all wiki-spaces under ``<vault>/<wiki_folder>/`` and reports
structural issues without writing anything. Used as the verification step
after ``wiki_compile.py`` and as a smoke check from ``doctor.py``.

Checks:
  - SCHEMA.md / index.md / log.md exist at the wiki-space root
  - Project-mode spaces have all CORE_PAGES under ``pages/``
  - Each page has required frontmatter fields (note_type, wiki_project,
    wiki_page_type, wiki_status, date)
  - ``wiki_page_type`` is one of WIKI_PAGE_TYPES; status is one of
    WIKI_STATUSES; confidence (if present) is one of WIKI_CONFIDENCES
  - ``wiki_project`` matches the enclosing folder slug
  - ``source_doc`` matches the synthetic ``wiki:<slug>:<page_type>:<stem>``
    pattern (raw notes are exempt — they may carry the original filename)
  - Every wikilink target resolves to a known page in the same wiki-space
    (or carries the explicit ``[[?slug]]`` open-question marker)
  - No duplicate entity titles (case-insensitive) in entities/
  - index.md is not stale: lists every existing page

Exit codes:
  0 — all spaces clean
  1 — issues found (always emits ``WIKI_LINT_FAILED`` to stderr)

Usage:
    python3 scripts/wiki_lint.py [<slug>] [--json] [--strict]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(f"ERROR: Missing dependency: {exc}") from exc

try:
    from scripts.config import load_config as _load_config
    from scripts.wiki_models import (
        CORE_PAGES,
        META_PAGES,
        REQUIRED_FRONTMATTER,
        WIKI_CONFIDENCES,
        WIKI_NOTE_TYPE,
        WIKI_PAGE_TYPES,
        WIKI_RAW_KINDS,
        WIKI_STATUSES,
        is_valid_slug,
        is_valid_wiki_source_doc,
    )
except ModuleNotFoundError:
    from config import load_config as _load_config
    from wiki_models import (
        CORE_PAGES,
        META_PAGES,
        REQUIRED_FRONTMATTER,
        WIKI_CONFIDENCES,
        WIKI_NOTE_TYPE,
        WIKI_PAGE_TYPES,
        WIKI_RAW_KINDS,
        WIKI_STATUSES,
        is_valid_slug,
        is_valid_wiki_source_doc,
    )


WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
OPEN_QUESTION_LINK_RE = re.compile(r"^\?[a-z0-9-]+$")
FENCED_CODE_RE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")


def _strip_code(text: str) -> str:
    """Remove fenced code blocks and inline code spans before link extraction.

    Wikilink syntax inside backticks (e.g. documentation prose like
    `[[wikilinks]]`) must not be treated as a real link.
    """
    text = FENCED_CODE_RE.sub("", text)
    text = INLINE_CODE_RE.sub("", text)
    return text


@dataclass
class LintIssue:
    space: str
    path: str
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "space": self.space,
            "path": self.path,
            "code": self.code,
            "message": self.message,
        }


@dataclass
class WikiSpaceSnapshot:
    slug: str
    root: Path
    mode: str  # "project" | "corpus" | "unknown"
    pages: dict[str, dict[str, Any]] = field(default_factory=dict)  # rel_path -> {fm, body, title}

    def page_titles(self) -> set[str]:
        return {p["title"] for p in self.pages.values()}

    def page_stems(self) -> set[str]:
        return {Path(rel).stem for rel in self.pages}


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
    targets: set[str] = set()
    for raw in WIKILINK_RE.findall(_strip_code(text)):
        target = raw.split("|", 1)[0].split("#", 1)[0].strip()
        if target:
            targets.add(target)
    return targets


def _detect_mode(root: Path) -> str:
    schema = root / "SCHEMA.md"
    if not schema.exists():
        return "unknown"
    fm, _ = _split_frontmatter(schema.read_text(encoding="utf-8"))
    mode = fm.get("wiki_mode")
    return mode if mode in ("project", "corpus") else "unknown"


def _load_space(root: Path) -> WikiSpaceSnapshot:
    snapshot = WikiSpaceSnapshot(slug=root.name, root=root, mode=_detect_mode(root))
    for md_file in root.rglob("*.md"):
        rel = md_file.relative_to(root).as_posix()
        try:
            text = md_file.read_text(encoding="utf-8")
        except OSError:
            continue
        fm, body = _split_frontmatter(text)
        title = md_file.stem
        for line in body.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        snapshot.pages[rel] = {"fm": fm, "body": body, "title": title}
    return snapshot


def _check_meta_pages(snapshot: WikiSpaceSnapshot, issues: list[LintIssue]) -> None:
    for meta in META_PAGES:
        rel = f"{meta}.md"
        if rel not in snapshot.pages:
            issues.append(
                LintIssue(
                    space=snapshot.slug,
                    path=rel,
                    code="META_MISSING",
                    message=f"required meta page '{rel}' not found at wiki-space root",
                )
            )


def _check_core_pages(snapshot: WikiSpaceSnapshot, issues: list[LintIssue]) -> None:
    if snapshot.mode != "project":
        return
    for core in CORE_PAGES:
        rel = f"pages/{core}.md"
        if rel not in snapshot.pages:
            issues.append(
                LintIssue(
                    space=snapshot.slug,
                    path=rel,
                    code="CORE_PAGE_MISSING",
                    message=f"project mode requires core page '{rel}'",
                )
            )


def _check_frontmatter(snapshot: WikiSpaceSnapshot, issues: list[LintIssue]) -> None:
    for rel, page in snapshot.pages.items():
        fm = page["fm"]

        for key in REQUIRED_FRONTMATTER:
            if key not in fm or fm[key] in (None, ""):
                issues.append(
                    LintIssue(
                        space=snapshot.slug,
                        path=rel,
                        code="FRONTMATTER_MISSING",
                        message=f"required field '{key}' missing or empty",
                    )
                )

        note_type = fm.get("note_type")
        if note_type and note_type != WIKI_NOTE_TYPE:
            issues.append(
                LintIssue(
                    space=snapshot.slug,
                    path=rel,
                    code="WRONG_NOTE_TYPE",
                    message=f"note_type='{note_type}', expected '{WIKI_NOTE_TYPE}'",
                )
            )

        page_type = fm.get("wiki_page_type")
        if page_type and page_type not in WIKI_PAGE_TYPES:
            issues.append(
                LintIssue(
                    space=snapshot.slug,
                    path=rel,
                    code="INVALID_PAGE_TYPE",
                    message=f"wiki_page_type='{page_type}' not in {list(WIKI_PAGE_TYPES)}",
                )
            )

        status = fm.get("wiki_status")
        if status and status not in WIKI_STATUSES:
            issues.append(
                LintIssue(
                    space=snapshot.slug,
                    path=rel,
                    code="INVALID_STATUS",
                    message=f"wiki_status='{status}' not in {list(WIKI_STATUSES)}",
                )
            )

        confidence = fm.get("confidence")
        if confidence and confidence not in WIKI_CONFIDENCES:
            issues.append(
                LintIssue(
                    space=snapshot.slug,
                    path=rel,
                    code="INVALID_CONFIDENCE",
                    message=f"confidence='{confidence}' not in {list(WIKI_CONFIDENCES)}",
                )
            )

        wiki_project = fm.get("wiki_project")
        if wiki_project and wiki_project != snapshot.slug:
            issues.append(
                LintIssue(
                    space=snapshot.slug,
                    path=rel,
                    code="WRONG_PROJECT_SLUG",
                    message=(
                        f"wiki_project='{wiki_project}' does not match enclosing "
                        f"folder slug '{snapshot.slug}'"
                    ),
                )
            )

        source_doc = fm.get("source_doc")
        if source_doc and page_type and page_type != "raw":
            if not is_valid_wiki_source_doc(source_doc):
                issues.append(
                    LintIssue(
                        space=snapshot.slug,
                        path=rel,
                        code="INVALID_SOURCE_DOC",
                        message=(
                            f"source_doc='{source_doc}' does not match "
                            f"wiki:<slug>:<page_type>:<stem>"
                        ),
                    )
                )


def _check_wikilinks(snapshot: WikiSpaceSnapshot, issues: list[LintIssue]) -> None:
    known_titles = snapshot.page_titles()
    known_stems = snapshot.page_stems()
    for rel, page in snapshot.pages.items():
        targets = _extract_wikilink_targets(page["body"])
        for target in targets:
            if OPEN_QUESTION_LINK_RE.match(target):
                continue
            if target in known_titles or target in known_stems:
                continue
            issues.append(
                LintIssue(
                    space=snapshot.slug,
                    path=rel,
                    code="UNRESOLVED_WIKILINK",
                    message=f"[[{target}]] does not resolve inside wiki-space",
                )
            )


def _check_entity_dupes(snapshot: WikiSpaceSnapshot, issues: list[LintIssue]) -> None:
    seen: dict[str, str] = {}
    for rel, page in snapshot.pages.items():
        if not rel.startswith("entities/"):
            continue
        key = page["title"].strip().lower()
        if key in seen:
            issues.append(
                LintIssue(
                    space=snapshot.slug,
                    path=rel,
                    code="DUPLICATE_ENTITY",
                    message=f"entity title duplicates '{seen[key]}' (case-insensitive)",
                )
            )
        else:
            seen[key] = rel


def _check_index_currency(snapshot: WikiSpaceSnapshot, issues: list[LintIssue]) -> None:
    index_page = snapshot.pages.get("index.md")
    if not index_page:
        return
    listed = _extract_wikilink_targets(index_page["body"])
    listed_stems = {Path(t).stem for t in listed}
    for rel in snapshot.pages:
        if rel in {f"{m}.md" for m in META_PAGES}:
            continue
        if rel.startswith("raw/"):
            continue
        stem = Path(rel).stem
        if stem not in listed_stems and stem not in listed:
            issues.append(
                LintIssue(
                    space=snapshot.slug,
                    path="index.md",
                    code="INDEX_STALE",
                    message=f"page '{rel}' not referenced in index.md",
                )
            )


def _check_raw_layout(snapshot: WikiSpaceSnapshot, issues: list[LintIssue]) -> None:
    for rel, page in snapshot.pages.items():
        if not rel.startswith("raw/"):
            continue
        # Files prefixed with "_" under raw/ are documentation, not raw notes
        # (e.g. raw/_README.md created by wiki_init.py).
        if Path(rel).name.startswith("_"):
            continue
        parts = Path(rel).parts
        if len(parts) < 3:
            issues.append(
                LintIssue(
                    space=snapshot.slug,
                    path=rel,
                    code="RAW_KIND_MISSING",
                    message="raw notes must live under raw/<kind>/<file>.md",
                )
            )
            continue
        kind = parts[1]
        if kind not in WIKI_RAW_KINDS:
            issues.append(
                LintIssue(
                    space=snapshot.slug,
                    path=rel,
                    code="INVALID_RAW_KIND",
                    message=f"raw kind '{kind}' not in {list(WIKI_RAW_KINDS)}",
                )
            )
            continue
        # frontmatter raw_kind, if present, must agree with the on-disk folder
        fm_kind = page["fm"].get("raw_kind")
        if fm_kind and fm_kind != kind:
            issues.append(
                LintIssue(
                    space=snapshot.slug,
                    path=rel,
                    code="RAW_KIND_MISMATCH",
                    message=f"frontmatter raw_kind='{fm_kind}' but file is under raw/{kind}/",
                )
            )


def lint_space(root: Path) -> list[LintIssue]:
    """Run all checks against a single wiki-space root."""
    if not root.exists() or not root.is_dir():
        return [
            LintIssue(
                space=root.name,
                path=".",
                code="SPACE_NOT_FOUND",
                message=f"wiki-space root '{root}' does not exist",
            )
        ]
    if not is_valid_slug(root.name):
        return [
            LintIssue(
                space=root.name,
                path=".",
                code="INVALID_SLUG",
                message=f"folder name '{root.name}' is not a valid slug",
            )
        ]

    snapshot = _load_space(root)
    issues: list[LintIssue] = []
    _check_meta_pages(snapshot, issues)
    _check_core_pages(snapshot, issues)
    _check_frontmatter(snapshot, issues)
    _check_wikilinks(snapshot, issues)
    _check_entity_dupes(snapshot, issues)
    _check_index_currency(snapshot, issues)
    _check_raw_layout(snapshot, issues)
    return issues


def discover_spaces(wiki_root: Path) -> list[Path]:
    if not wiki_root.exists():
        return []
    return sorted(p for p in wiki_root.iterdir() if p.is_dir() and is_valid_slug(p.name))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lint LLM Wiki spaces inside the configured vault."
    )
    parser.add_argument("slug", nargs="?", help="single wiki-space slug to check")
    parser.add_argument("--json", action="store_true", help="emit issues as JSON to stdout")
    parser.add_argument(
        "--strict", action="store_true", help="fail on any issue (default; reserved for parity)"
    )
    args = parser.parse_args()

    config = _load_config(strict=True)
    vault_path = Path(config["vault"]["vault_path"]).expanduser()
    wiki_folder = config.get("wiki", {}).get("wiki_folder", "LLM Wiki")
    wiki_root = vault_path / wiki_folder

    if args.slug:
        targets = [wiki_root / args.slug]
    else:
        targets = discover_spaces(wiki_root)
        if not targets:
            print(f"no wiki-spaces under {wiki_root}", file=sys.stderr)
            return 0

    all_issues: list[LintIssue] = []
    for root in targets:
        all_issues.extend(lint_space(root))

    if args.json:
        json.dump([i.to_dict() for i in all_issues], sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        if not all_issues:
            print("OK: no issues found")
        else:
            for issue in all_issues:
                print(f"[{issue.code}] {issue.space}/{issue.path}: {issue.message}")

    if all_issues:
        print("WIKI_LINT_FAILED", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
