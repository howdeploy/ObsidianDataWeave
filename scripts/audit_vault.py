"""audit_vault.py — Audit vault quality issues: empty, thin, and unlinked similar notes."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(f"ERROR: Missing dependency: {exc}") from exc

try:
    from scripts.config import load_config
    from scripts.scan_vault import SKIP_DIRS
except ModuleNotFoundError:
    from config import load_config
    from scan_vault import SKIP_DIRS


WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def extract_wikilink_targets(text: str) -> set[str]:
    """Extract normalized wikilink targets, ignoring aliases and headings."""
    targets: set[str] = set()
    for raw in WIKILINK_RE.findall(text):
        target = raw.split("|", 1)[0].split("#", 1)[0].strip()
        if target:
            targets.add(target)
    return targets


@dataclass
class NoteRecord:
    path: Path
    title: str
    note_type: str
    source_doc: str
    frontmatter: dict
    body: str
    tags: set[str]
    links: set[str]

    @property
    def words(self) -> int:
        return len(self.body.split())


def parse_note(path: Path) -> NoteRecord | None:
    """Parse a vault note into a normalized record."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    frontmatter: dict = {}
    body = text.strip()
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                frontmatter = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError:
                frontmatter = {}
            body = parts[2].strip()

    title = path.stem
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break

    tags = frontmatter.get("tags", [])
    if not isinstance(tags, list):
        tags = []

    return NoteRecord(
        path=path,
        title=title,
        note_type=str(frontmatter.get("note_type", "")),
        source_doc=str(frontmatter.get("source_doc", "")),
        frontmatter=frontmatter,
        body=body,
        tags=set(tags),
        links=extract_wikilink_targets(body),
    )


def iter_notes(vault_path: Path) -> list[NoteRecord]:
    """Load notes from the vault, excluding known system directories."""
    records: list[NoteRecord] = []
    for md_file in vault_path.rglob("*.md"):
        rel = md_file.relative_to(vault_path)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        record = parse_note(md_file)
        if record is not None:
            records.append(record)
    return records


def score_similarity(a: NoteRecord, b: NoteRecord) -> float:
    """Weighted title/tag similarity for duplicate-linking candidates."""
    title_sim = SequenceMatcher(None, a.title.lower(), b.title.lower()).ratio()
    union = a.tags | b.tags
    tag_sim = len(a.tags & b.tags) / len(union) if union else 0.0
    return 0.7 * title_sim + 0.3 * tag_sim


def audit_notes(
    notes: list[NoteRecord],
    *,
    min_words: int = 80,
    similarity_threshold: float = 0.72,
) -> dict:
    """Build a structured audit report."""
    empty = [
        {
            "title": note.title,
            "path": str(note.path),
            "source_doc": note.source_doc,
            "note_type": note.note_type,
        }
        for note in notes
        if note.words == 0 and not note.frontmatter
    ]

    thin = [
        {
            "title": note.title,
            "path": str(note.path),
            "words": note.words,
            "links": len(note.links),
            "source_doc": note.source_doc,
            "note_type": note.note_type,
        }
        for note in notes
        if note.note_type == "atomic" and 0 < note.words < min_words
    ]

    no_links = [
        {
            "title": note.title,
            "path": str(note.path),
            "words": note.words,
            "source_doc": note.source_doc,
        }
        for note in notes
        if note.note_type == "atomic" and note.words >= min_words and not note.links
    ]

    similar_pairs: list[dict] = []
    atomic_notes = [note for note in notes if note.note_type != "moc"]
    for i in range(len(atomic_notes)):
        for j in range(i + 1, len(atomic_notes)):
            a = atomic_notes[i]
            b = atomic_notes[j]
            score = score_similarity(a, b)
            if score < similarity_threshold:
                continue
            linked = b.title in a.links or a.title in b.links
            if linked:
                continue
            similar_pairs.append(
                {
                    "score": round(score, 3),
                    "a": a.title,
                    "a_path": str(a.path),
                    "b": b.title,
                    "b_path": str(b.path),
                }
            )

    similar_pairs.sort(key=lambda item: (-item["score"], item["a"], item["b"]))

    return {
        "summary": {
            "total_notes": len(notes),
            "empty_notes": len(empty),
            "thin_atomic_notes": len(thin),
            "atomic_notes_without_links": len(no_links),
            "unlinked_similar_pairs": len(similar_pairs),
        },
        "empty_notes": empty,
        "thin_atomic_notes": thin,
        "atomic_notes_without_links": no_links,
        "unlinked_similar_pairs": similar_pairs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit vault quality issues: empty notes, thin atomic notes, and unlinked similar pairs."
    )
    parser.add_argument(
        "--min-words",
        type=int,
        default=80,
        help="Minimum healthy word count for atomic notes (default: 80)",
    )
    parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.72,
        help="Similarity threshold for unlinked pair detection (default: 0.72)",
    )
    parser.add_argument(
        "--output",
        help="Optional JSON file path for the full audit report",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Max items per section to print in stdout summary (default: 25)",
    )
    args = parser.parse_args()

    config = load_config(strict=True)
    vault_path = Path(config["vault"]["vault_path"])
    notes = iter_notes(vault_path)
    report = audit_notes(
        notes,
        min_words=args.min_words,
        similarity_threshold=args.similarity_threshold,
    )

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    limit = args.limit
    trimmed = {
        "summary": report["summary"],
        "empty_notes": report["empty_notes"][:limit],
        "thin_atomic_notes": report["thin_atomic_notes"][:limit],
        "atomic_notes_without_links": report["atomic_notes_without_links"][:limit],
        "unlinked_similar_pairs": report["unlinked_similar_pairs"][:limit],
    }
    print(json.dumps(trimmed, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
