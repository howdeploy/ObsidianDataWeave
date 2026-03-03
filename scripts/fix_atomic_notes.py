"""fix_atomic_notes.py — Add related links to thin or isolated atomic notes."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

try:
    from scripts.audit_vault import NoteRecord, iter_notes, score_similarity
    from scripts.config import load_config
    from scripts.fix_similar_notes import append_related_link
except ModuleNotFoundError:
    from audit_vault import NoteRecord, iter_notes, score_similarity
    from config import load_config
    from fix_similar_notes import append_related_link

STOP_TOKENS = {
    "через",
    "между",
    "после",
    "вокруг",
    "вместо",
    "against",
    "using",
    "about",
}


def is_target_note(note: NoteRecord, *, min_words: int) -> bool:
    """Return True for atomic notes that are thin or have no wikilinks."""
    if note.note_type != "atomic":
        return False
    if note.words < min_words:
        return True
    if note.words >= min_words and not note.links:
        return True
    return False


def rank_related_candidates(
    note: NoteRecord,
    notes: list[NoteRecord],
    *,
    threshold: float,
    max_links: int,
) -> list[tuple[float, NoteRecord]]:
    """Find the strongest related-note candidates for one atomic note."""
    ranked: list[tuple[float, NoteRecord]] = []
    note_tokens = {
        token for token in re.findall(r"\w+", note.title.lower())
        if len(token) >= 4 and token not in STOP_TOKENS
    }

    for candidate in notes:
        if candidate.path == note.path:
            continue
        if candidate.title in note.links:
            continue
        if candidate.note_type == "moc":
            continue

        candidate_tokens = {
            token for token in re.findall(r"\w+", candidate.title.lower())
            if len(token) >= 4 and token not in STOP_TOKENS
        }
        shared_tokens = note_tokens & candidate_tokens
        same_source = bool(note.source_doc) and note.source_doc == candidate.source_doc
        if not shared_tokens and not same_source:
            continue

        score = score_similarity(note, candidate)
        if same_source:
            score += 0.08
        if shared_tokens:
            score += min(0.12, 0.04 * len(shared_tokens))
        if candidate.title in note.body:
            score += 0.05
        if score < threshold:
            continue
        ranked.append((score, candidate))

    ranked.sort(key=lambda item: (-item[0], item[1].title))
    return ranked[:max_links]


def apply_related_links(note: NoteRecord, related: list[NoteRecord]) -> bool:
    """Append related links to a note. Returns True if the file changed."""
    if not related:
        return False

    content = note.path.read_text(encoding="utf-8")
    updated = content
    for candidate in related:
        updated = append_related_link(updated, candidate.title)

    if updated == content:
        return False

    note.path.write_text(updated, encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add related-note links to thin or isolated atomic notes."
    )
    parser.add_argument(
        "--min-words",
        type=int,
        default=80,
        help="Minimum healthy word count for atomic notes (default: 80)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.34,
        help="Relatedness threshold for link suggestions (default: 0.34)",
    )
    parser.add_argument(
        "--max-links",
        type=int,
        default=3,
        help="Maximum related links to add per note (default: 3)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of target notes to process (default: 20)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show proposed link additions without modifying files",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply related-link fixes to the vault",
    )
    args = parser.parse_args()

    config = load_config(strict=True)
    vault_path = Path(config["vault"]["vault_path"])
    notes = iter_notes(vault_path)

    targets = [note for note in notes if is_target_note(note, min_words=args.min_words)]
    targets.sort(key=lambda note: (note.words, note.title))
    targets = targets[:args.limit]

    results: list[dict] = []
    modified = 0
    for note in targets:
        ranked = rank_related_candidates(
            note,
            notes,
            threshold=args.threshold,
            max_links=args.max_links,
        )
        related = [candidate for _, candidate in ranked]
        if args.apply and not args.dry_run:
            changed = apply_related_links(note, related)
            if changed:
                modified += 1

        results.append(
            {
                "title": note.title,
                "path": str(note.path),
                "words": note.words,
                "existing_links": len(note.links),
                "suggested_related": [
                    {"title": candidate.title, "score": round(score, 3)}
                    for score, candidate in ranked
                ],
            }
        )

    summary = {
        "target_notes": len(targets),
        "modified_notes": modified,
        "dry_run": args.dry_run or not args.apply,
    }
    print(json.dumps({"summary": summary, "notes": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
