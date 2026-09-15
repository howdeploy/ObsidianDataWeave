"""wiki_ingest.py — Normalize raw inputs into a wiki-space's raw/ folder.

Accepts a single file, a directory, or a URL and writes one .md file per
input under ``<wiki-space>/raw/<kind>/<YYYY-MM-DD>-<slug>.md`` with a
minimal wiki frontmatter. **No LLM call.** This is pure normalization;
the compile pass that follows is what does the merge into wiki pages.

Usage:
    python3 scripts/wiki_ingest.py <slug> <path>          # file or dir
    python3 scripts/wiki_ingest.py <slug> <url> --kind articles
    python3 scripts/wiki_ingest.py <slug> <path> --label customer-survey

Flags:
    --kind {articles,docs,transcripts,assets}  (default: docs)
    --label <slug>                              (override slug part of filename)
    --no-compile                                (skip the chained compile call)
    --backend {auto,claude,codex}               (passed through to wiki_compile)

Exit codes:
    0 — at least one raw file written
    1 — bad arguments / config
    2 — wiki-space not found            (WIKI_PROJECT_NOT_FOUND on stderr)
    3 — input expanded to zero files    (WIKI_INGEST_EMPTY on stderr)
    4 — input read failed               (per-file errors logged to stderr)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

try:
    from scripts.config import PROJECT_ROOT, load_config as _load_config
    from scripts.wiki_models import WIKI_RAW_KINDS, is_valid_slug
except ModuleNotFoundError:
    from config import PROJECT_ROOT, load_config as _load_config
    from wiki_models import WIKI_RAW_KINDS, is_valid_slug


_SLUG_STRIP = re.compile(r"[^a-z0-9-]+")
_SLUG_DASHES = re.compile(r"-{2,}")


def _slugify(text: str) -> str:
    """Coerce arbitrary text into kebab-case ASCII slug."""
    lower = text.strip().lower()
    lower = lower.replace(" ", "-").replace("_", "-")
    lower = _SLUG_STRIP.sub("", lower)
    lower = _SLUG_DASHES.sub("-", lower).strip("-")
    return lower or "input"


def _is_url(token: str) -> bool:
    parsed = urlparse(token)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _slug_from_url(url: str) -> str:
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    base = parts[-1] if parts else parsed.netloc
    base = base.rsplit(".", 1)[0]
    return _slugify(base) or _slugify(parsed.netloc)


def expand_inputs(token: str) -> list[Path]:
    """Resolve a CLI input token to a list of input files.

    URLs are not expanded here (caller fetches them); we return an empty
    list for URLs and let the caller branch.
    """
    if _is_url(token):
        return []
    p = Path(token)
    if not p.exists():
        raise FileNotFoundError(token)
    if p.is_file():
        return [p]
    return sorted(f for f in p.rglob("*") if f.is_file())


def _build_raw_frontmatter(slug: str, label: str, source: str, today: str) -> str:
    return (
        "---\n"
        f"tags:\n  - wiki/raw\n  - wiki/ingested\n"
        f"date: {today}\n"
        f"source_doc: \"wiki:{slug}:raw:{label}\"\n"
        "note_type: wiki\n"
        f"wiki_project: {slug}\n"
        "wiki_page_type: raw\n"
        "wiki_status: ingested\n"
        f"raw_source: {json.dumps(str(source))}\n"
        "---\n"
        "\n"
    )


def _read_text_file(path: Path) -> str:
    """Read a text file, falling back to a one-line marker for binaries."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"_(binary file copied as-is from {path.name})_\n"


def write_raw_note(
    wiki_root: Path,
    slug: str,
    kind: str,
    label: str,
    source_id: str,
    body: str,
    today: str,
) -> Path:
    """Write a single raw note. Returns the destination path."""
    if kind not in WIKI_RAW_KINDS:
        raise ValueError(f"raw kind '{kind}' not in {list(WIKI_RAW_KINDS)}")
    raw_dir = wiki_root / "raw" / kind
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / f"{today}-{label}.md"
    counter = 2
    while dest.exists():
        dest = raw_dir / f"{today}-{label}-{counter}.md"
        counter += 1
    fm = _build_raw_frontmatter(slug, dest.stem, source_id, today)
    dest.write_text(fm + body, encoding="utf-8")
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize one or more raw inputs into a wiki-space's raw/ folder."
    )
    parser.add_argument("slug", help="target wiki-space slug")
    parser.add_argument("path", help="file, directory, or http(s) URL to ingest")
    parser.add_argument(
        "--kind",
        default="docs",
        choices=list(WIKI_RAW_KINDS),
        help="raw kind subfolder (default: docs)",
    )
    parser.add_argument("--label", default=None, help="override slug part of filename")
    parser.add_argument(
        "--no-compile", action="store_true", help="skip chained wiki_compile.py call"
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "claude", "codex"],
        default="auto",
        help="passed through to wiki_compile.py if --no-compile is not set",
    )
    args = parser.parse_args()

    if not is_valid_slug(args.slug):
        print(f"ERROR: slug '{args.slug}' is not valid kebab-case", file=sys.stderr)
        return 1

    config = _load_config(strict=True)
    vault_path = Path(config["vault"]["vault_path"]).expanduser()
    wiki_folder = config.get("wiki", {}).get("wiki_folder", "LLM Wiki")
    wiki_root = vault_path / wiki_folder / args.slug

    if not (wiki_root / "SCHEMA.md").exists():
        print(
            f"WIKI_PROJECT_NOT_FOUND: no SCHEMA.md at {wiki_root}; run "
            f"`wiki_init.py {args.slug}` first",
            file=sys.stderr,
        )
        return 2

    today = date.today().isoformat()
    written: list[Path] = []

    if _is_url(args.path):
        # We do not auto-fetch URLs (would invite scope creep + secrets).
        # Instead, write a stub that records the URL — user can paste content
        # in later, or run a separate fetch step.
        label = args.label or _slug_from_url(args.path)
        body = (
            f"# {label}\n\n"
            f"_(stub — paste fetched content below or rerun with a downloaded file)_\n\n"
            f"Source URL: {args.path}\n"
        )
        try:
            dest = write_raw_note(
                wiki_root, args.slug, args.kind, label, args.path, body, today
            )
        except (OSError, ValueError) as exc:
            print(f"ERROR: failed to write raw note: {exc}", file=sys.stderr)
            return 4
        written.append(dest)
    else:
        try:
            inputs = expand_inputs(args.path)
        except FileNotFoundError:
            print(f"ERROR: input not found: {args.path}", file=sys.stderr)
            return 1

        if not inputs:
            print(
                f"WIKI_INGEST_EMPTY: '{args.path}' expanded to zero files",
                file=sys.stderr,
            )
            return 3

        for src in inputs:
            base_label = args.label or _slugify(src.stem)
            # If we got many inputs from a directory, append the original stem
            # to the label so each is unique even with --label.
            if len(inputs) > 1 and args.label:
                base_label = f"{args.label}-{_slugify(src.stem)}"
            try:
                if src.suffix.lower() == ".md":
                    body = _read_text_file(src)
                else:
                    body = (
                        f"# {src.name}\n\n"
                        f"_(non-markdown source copied as-is from `{src}`)_\n\n"
                        f"```\n{_read_text_file(src)}\n```\n"
                    )
                dest = write_raw_note(
                    wiki_root,
                    args.slug,
                    args.kind,
                    base_label,
                    str(src),
                    body,
                    today,
                )
            except (OSError, ValueError) as exc:
                print(f"ERROR: failed to ingest {src}: {exc}", file=sys.stderr)
                continue
            written.append(dest)

    if not written:
        print(f"WIKI_INGEST_EMPTY: nothing was written from '{args.path}'", file=sys.stderr)
        return 3

    rel_root = wiki_root.relative_to(vault_path)
    for dest in written:
        rel = dest.relative_to(wiki_root)
        print(f"OK: {rel_root}/{rel}")

    if args.no_compile:
        return 0

    compile_script = PROJECT_ROOT / "scripts" / "wiki_compile.py"
    if not compile_script.exists():
        print(
            "INFO: wiki_compile.py not yet available; skipping chained compile",
            file=sys.stderr,
        )
        return 0

    cmd = [
        sys.executable,
        str(compile_script),
        args.slug,
        "--since-last-compile",
        "--backend",
        args.backend,
    ]
    print(f"INFO: chaining: {' '.join(cmd)}", file=sys.stderr)
    proc = subprocess.run(cmd, check=False)
    return proc.returncode


__all__ = ["expand_inputs", "write_raw_note", "main"]


if __name__ == "__main__":
    sys.exit(main())
