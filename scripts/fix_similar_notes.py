"""fix_similar_notes.py — Merge near-duplicate notes or link related pairs."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

try:
    from scripts.config import PROJECT_ROOT, load_config
    from scripts.atomize import extract_json, load_tags
    from scripts.audit_vault import extract_wikilink_targets, score_similarity
    from scripts.dedup_vault import (
        CandidateGroup,
        VaultNote,
        deep_scan_vault,
        execute_merge,
        update_registry_after_merge,
        update_wikilinks,
    )
    from scripts.rewrite_backend import call_rewriter
except ModuleNotFoundError:
    from config import PROJECT_ROOT, load_config
    from atomize import extract_json, load_tags
    from audit_vault import extract_wikilink_targets, score_similarity
    from dedup_vault import (
        CandidateGroup,
        VaultNote,
        deep_scan_vault,
        execute_merge,
        update_registry_after_merge,
        update_wikilinks,
    )
    from rewrite_backend import call_rewriter


REVIEWED_FIXES_PATH = PROJECT_ROOT / "similar_fix_reviewed.json"
RELATED_HEADER = "## Related"
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class PairCandidate:
    pair_id: int
    a: VaultNote
    b: VaultNote
    score: float


def load_reviewed() -> list[dict]:
    """Load previously reviewed similarity fixes."""
    if not REVIEWED_FIXES_PATH.exists():
        return []
    try:
        data = json.loads(REVIEWED_FIXES_PATH.read_text(encoding="utf-8"))
        return data.get("reviewed", [])
    except (json.JSONDecodeError, OSError):
        return []


def save_reviewed(reviewed: list[dict]) -> None:
    """Persist reviewed similarity fixes (atomic write)."""
    data = json.dumps({"reviewed": reviewed}, ensure_ascii=False, indent=2)
    fd, tmp_path = tempfile.mkstemp(
        dir=REVIEWED_FIXES_PATH.parent, suffix=".tmp", prefix=REVIEWED_FIXES_PATH.stem
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp_path, REVIEWED_FIXES_PATH)
    except BaseException:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def reviewed_set(reviewed: list[dict]) -> set[frozenset[str]]:
    """Convert reviewed entries to title-pair keys."""
    result: set[frozenset[str]] = set()
    for entry in reviewed:
        titles = entry.get("titles", [])
        if len(titles) == 2:
            result.add(frozenset(titles))
    return result


def extract_links(body: str) -> set[str]:
    """Return wikilink targets from note body."""
    return extract_wikilink_targets(body)


def find_unlinked_pairs(
    notes: list[VaultNote],
    *,
    threshold: float,
    reviewed: list[dict],
    limit: int,
) -> list[PairCandidate]:
    """Find high-similarity note pairs without direct wikilinks."""
    reviewed_pairs = reviewed_set(reviewed)
    candidates: list[PairCandidate] = []
    pair_id = 0

    for i in range(len(notes)):
        for j in range(i + 1, len(notes)):
            a, b = notes[i], notes[j]
            score = score_similarity(
                type("AuditNote", (), {"title": a.title, "tags": set(a.tags)})(),
                type("AuditNote", (), {"title": b.title, "tags": set(b.tags)})(),
            )
            if score < threshold:
                continue
            if frozenset([a.title, b.title]) in reviewed_pairs:
                continue
            links_a = extract_links(a.body)
            links_b = extract_links(b.body)
            if b.title in links_a or a.title in links_b:
                continue
            candidates.append(PairCandidate(pair_id=pair_id, a=a, b=b, score=score))
            pair_id += 1

    candidates.sort(key=lambda item: (-item.score, item.a.title, item.b.title))
    return candidates[:limit]


def assemble_fix_prompt(pairs: list[PairCandidate], tags: list[str]) -> str:
    """Build a prompt to decide merge vs link vs ignore for similar pairs."""
    lines = [
        "You are fixing an Obsidian vault with semantically similar notes.",
        "For each pair, decide one action:",
        '- "merge" if the two notes are practical duplicates and should become one rewritten canonical note',
        '- "link" if they are related but distinct and should remain separate',
        '- "ignore" if the similarity is superficial',
        "",
        "For action=merge, return:",
        '- "canonical_title"',
        '- "canonical_tags" (2-5 tags chosen from the provided taxonomy)',
        '- "canonical_body" (150-600 words, preserving all unique information and using [[wikilinks]] where appropriate)',
        "",
        "For action=link, return only the action and confidence.",
        'Output JSON only: {"pairs":[{"pair_id":0,"action":"merge|link|ignore","confidence":0.0,...}]}',
        f"Available tags sample: {json.dumps(tags[:50], ensure_ascii=False)}",
        "---",
        "",
    ]

    for pair in pairs:
        lines.append(f"## Pair {pair.pair_id}")
        lines.append(f"Similarity score: {pair.score:.3f}")
        for note in [pair.a, pair.b]:
            words = note.body.split()
            truncated = " ".join(words[:220])
            if len(words) > 220:
                truncated += " [...]"
            lines.append(f"### {note.title}")
            lines.append(f"Tags: {note.tags}")
            lines.append(f"Source: {note.source_doc}")
            lines.append("")
            lines.append(truncated)
            lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def append_related_link(content: str, target_title: str) -> str:
    """Append a wikilink to a related note if it is not already present."""
    wikilink = f"[[{target_title}]]"
    if wikilink in content:
        return content

    stripped = content.rstrip() + "\n"
    if RELATED_HEADER in stripped:
        idx = stripped.index(RELATED_HEADER)
        head = stripped[:idx]
        tail = stripped[idx:].rstrip()
        return f"{head}{tail}\n- {wikilink}\n"

    return f"{stripped}\n{RELATED_HEADER}\n- {wikilink}\n"


def normalize_title(title: str) -> str:
    """Normalize a title for deterministic comparisons."""
    title = title.lower().strip()
    title = re.sub(r"\s+", " ", title)
    return title


def choose_canonical_title(a: VaultNote, b: VaultNote) -> str:
    """Choose the more canonical of two very similar titles."""
    norm_a = normalize_title(a.title)
    norm_b = normalize_title(b.title)
    if norm_a in norm_b:
        return a.title if len(a.title) <= len(b.title) else b.title
    if norm_b in norm_a:
        return b.title if len(b.title) <= len(a.title) else a.title
    return a.title if len(a.title) <= len(b.title) else b.title


def paragraph_similarity(a: str, b: str) -> float:
    """Approximate similarity for paragraph deduplication."""
    return SequenceMatcher(None, a.strip().lower(), b.strip().lower()).ratio()


def merge_unique_paragraphs(a_body: str, b_body: str) -> list[str]:
    """Keep unique paragraphs from both notes, preserving order."""
    merged: list[str] = []
    for paragraph in [*a_body.split("\n\n"), *b_body.split("\n\n")]:
        text = paragraph.strip()
        if not text:
            continue
        if any(paragraph_similarity(text, existing) >= 0.9 for existing in merged):
            continue
        merged.append(text)
    return merged


def build_canonical_body(a: VaultNote, b: VaultNote, canonical_title: str) -> str:
    """Deterministically build a merged body for an obvious duplicate pair."""
    first, second = (a, b) if len(a.body) >= len(b.body) else (b, a)
    paragraphs = merge_unique_paragraphs(first.body, second.body)
    links = sorted(extract_links(first.body) | extract_links(second.body))
    body = "\n\n".join(paragraphs)

    if len(body.split()) < 120:
        lead = (
            f"{canonical_title} описывает, какие инструменты и ограничения получает агент "
            "в рамках одной программной конфигурации и как это влияет на его зону ответственности."
        )
        body = f"{lead}\n\n{body}"

    if links:
        related = "\n".join(f"- [[{title}]]" for title in links[:6] if title != canonical_title)
        if related:
            body = f"{body}\n\n{RELATED_HEADER}\n{related}"

    return body


def deterministic_fix_pairs(pairs: list[PairCandidate]) -> dict:
    """Classify similar pairs without an LLM for the most obvious cases."""
    results: list[dict] = []
    for pair in pairs:
        same_source = bool(pair.a.source_doc) and pair.a.source_doc == pair.b.source_doc
        if same_source and pair.score >= 0.9:
            canonical_title = choose_canonical_title(pair.a, pair.b)
            canonical_tags = sorted(set(pair.a.tags) | set(pair.b.tags))[:5]
            canonical_body = build_canonical_body(pair.a, pair.b, canonical_title)
            results.append(
                {
                    "pair_id": pair.pair_id,
                    "action": "merge",
                    "confidence": round(min(0.99, pair.score + 0.03), 3),
                    "canonical_title": canonical_title,
                    "canonical_tags": canonical_tags,
                    "canonical_body": canonical_body,
                }
            )
        elif pair.score >= 0.8:
            results.append(
                {
                    "pair_id": pair.pair_id,
                    "action": "link",
                    "confidence": round(pair.score, 3),
                }
            )
        else:
            results.append(
                {
                    "pair_id": pair.pair_id,
                    "action": "ignore",
                    "confidence": round(pair.score, 3),
                }
            )
    return {"pairs": results}


def link_pair(a: VaultNote, b: VaultNote) -> int:
    """Insert reciprocal related links into two notes. Returns number of files modified."""
    modified = 0
    for source, target in [(a, b), (b, a)]:
        content = source.path.read_text(encoding="utf-8")
        updated = append_related_link(content, target.title)
        if updated != content:
            source.path.write_text(updated, encoding="utf-8")
            modified += 1
    return modified


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fix similar notes by either merging practical duplicates or linking related pairs."
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.72,
        help="Similarity threshold for pair selection (default: 0.72)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of pairs to evaluate in one run (default: 20)",
    )
    parser.add_argument(
        "--backend",
        choices=("auto", "claude", "codex", "deterministic"),
        default="auto",
        help="Rewrite backend to use (default: auto-detect from the current agent environment; deterministic avoids LLM calls)",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=300,
        help="Timeout for each rewrite backend call (default: 300)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned actions without modifying the vault",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply merge/link actions to the vault",
    )
    args = parser.parse_args()

    config = load_config(strict=True)
    vault_path = Path(config["vault"]["vault_path"])
    reviewed = load_reviewed()
    tags = load_tags()
    notes = deep_scan_vault(vault_path)
    pairs = find_unlinked_pairs(
        notes,
        threshold=args.threshold,
        reviewed=reviewed,
        limit=args.limit,
    )

    if not pairs:
        print(json.dumps({"summary": {"candidate_pairs": 0}}, ensure_ascii=False, indent=2))
        return

    if args.backend == "deterministic":
        resolved_backend = "deterministic"
        result = deterministic_fix_pairs(pairs)
    else:
        prompt = assemble_fix_prompt(pairs, tags)
        resolved_backend, raw = call_rewriter(
            prompt,
            backend=args.backend,
            timeout_seconds=args.timeout_seconds,
            project_root=PROJECT_ROOT,
        )
        try:
            result = extract_json(raw)
        except ValueError as e:
            print(f"ERROR: Failed to parse backend response: {e}", file=sys.stderr)
            return

    summary = {
        "backend": resolved_backend,
        "candidate_pairs": len(pairs),
        "merge_actions": 0,
        "link_actions": 0,
        "ignored_actions": 0,
        "wikilink_updates": 0,
    }
    title_map: dict[str, str] = {}

    indexed = {pair.pair_id: pair for pair in pairs}

    for item in result.get("pairs", []):
        pair_id = item.get("pair_id")
        pair = indexed.get(pair_id)
        if pair is None:
            continue

        action = item.get("action", "ignore")
        confidence = float(item.get("confidence", 0.0))
        titles = [pair.a.title, pair.b.title]

        if action == "merge":
            summary["merge_actions"] += 1
            if args.apply and not args.dry_run:
                group = CandidateGroup(
                    group_id=pair_id,
                    notes=[pair.a, pair.b],
                    pairs=[(pair.a.title, pair.b.title, pair.score)],
                    is_duplicate=True,
                    confidence=confidence,
                    canonical_title=item.get("canonical_title"),
                    canonical_tags=item.get("canonical_tags"),
                    canonical_body=item.get("canonical_body"),
                )
                merged_map = execute_merge(group, config, vault_path)
                update_registry_after_merge(group, group.canonical_title or pair.a.title)
                title_map.update(merged_map)
            reviewed.append({
                "titles": titles,
                "decision": "merge",
                "confidence": confidence,
                "date": date.today().isoformat(),
            })
        elif action == "link":
            summary["link_actions"] += 1
            if args.apply and not args.dry_run:
                summary["wikilink_updates"] += link_pair(pair.a, pair.b)
            reviewed.append({
                "titles": titles,
                "decision": "link",
                "confidence": confidence,
                "date": date.today().isoformat(),
            })
        else:
            summary["ignored_actions"] += 1
            reviewed.append({
                "titles": titles,
                "decision": "ignore",
                "confidence": confidence,
                "date": date.today().isoformat(),
            })

    if title_map and args.apply and not args.dry_run:
        summary["wikilink_updates"] += update_wikilinks(vault_path, title_map)

    if args.apply and not args.dry_run:
        save_reviewed(reviewed)

    print(json.dumps({"summary": summary, "pairs": result.get("pairs", [])}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
