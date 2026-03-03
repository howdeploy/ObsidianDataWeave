"""dedup_vault.py — Semantic deduplication of Obsidian vault notes.

5-phase pipeline:
    1. Deep Vault Scan — read all notes with content and frontmatter
    2. Local Candidate Detection — title/tag/token similarity
    3. Semantic Verification — batch semantic dedup check via local CLI
    4. Merge Decision — merge/keep/skip per group
    5. Wikilink Update — replace old titles across vault

Usage:
    python3 scripts/dedup_vault.py [--dry-run] [--auto] [--threshold 0.55]
                                   [--confidence 0.85] [--folder <subfolder>]
                                   [--skip-claude] [--non-interactive]
                                   [--decision merge|keep|skip]
"""

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

try:
    from scripts.config import PROJECT_ROOT, load_config as _load_config
    from scripts.atomize import extract_json, load_tags
    from scripts.rewrite_backend import call_rewriter
    from scripts.generate_notes import render_note_md, sanitize_filename
    from scripts.scan_vault import SKIP_DIRS
    from scripts.vault_writer import (
        get_vault_dest, load_registry, parse_frontmatter, save_registry,
    )
except ModuleNotFoundError:
    from config import PROJECT_ROOT, load_config as _load_config
    from atomize import extract_json, load_tags
    from rewrite_backend import call_rewriter
    from generate_notes import render_note_md, sanitize_filename
    from scan_vault import SKIP_DIRS
    from vault_writer import (
        get_vault_dest, load_registry, parse_frontmatter, save_registry,
    )

REVIEWED_PATH = PROJECT_ROOT / "dedup_reviewed.json"


# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class VaultNote:
    path: Path
    title: str          # file stem
    body: str           # content after frontmatter
    tags: list[str]
    note_type: str
    source_doc: str
    word_count: int


@dataclass
class CandidateGroup:
    group_id: int
    notes: list[VaultNote]
    pairs: list[tuple[str, str, float]]
    is_duplicate: bool | None = None
    confidence: float = 0.0
    canonical_title: str | None = None
    canonical_tags: list[str] | None = None
    canonical_body: str | None = None


# ── Phase 1: Deep Vault Scan ─────────────────────────────────────────────────


def deep_scan_vault(vault_path: Path, folder: str | None = None) -> list[VaultNote]:
    """Read all notes with content and frontmatter. MOC notes are filtered out."""
    notes: list[VaultNote] = []
    scan_root = vault_path / folder if folder else vault_path

    if not scan_root.exists():
        print(f"ERROR: Scan path does not exist: {scan_root}", file=sys.stderr)
        sys.exit(1)

    for md_file in scan_root.rglob("*.md"):
        # Skip excluded directories
        rel = md_file.relative_to(vault_path)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue

        try:
            content = md_file.read_text(encoding="utf-8")
        except OSError:
            continue

        fm = parse_frontmatter(content)
        note_type = fm.get("note_type", "")

        # Skip MOC notes — they are auto-generated, not merge targets
        if note_type == "moc" or md_file.stem.endswith(" \u2014 MOC"):
            continue

        # Extract body (after frontmatter)
        parts = content.split("---", 2)
        body = parts[2].strip() if len(parts) >= 3 else content.strip()

        tags = fm.get("tags", [])
        if not isinstance(tags, list):
            tags = []

        notes.append(VaultNote(
            path=md_file,
            title=md_file.stem,
            body=body,
            tags=tags,
            note_type=note_type,
            source_doc=fm.get("source_doc", ""),
            word_count=len(body.split()),
        ))

    return notes


# ── Phase 2: Local Candidate Detection ───────────────────────────────────────


def compute_similarity(a: VaultNote, b: VaultNote) -> float:
    """Three-signal composite similarity score.

    Signals:
        Title similarity (SequenceMatcher)  — weight 0.5
        Tag overlap (Jaccard)               — weight 0.3
        Title token overlap (Jaccard)       — weight 0.2
    """
    # Title similarity
    title_sim = SequenceMatcher(None, a.title.lower(), b.title.lower()).ratio()

    # Tag overlap (Jaccard)
    tags_a = set(a.tags)
    tags_b = set(b.tags)
    tag_union = tags_a | tags_b
    tag_jaccard = len(tags_a & tags_b) / len(tag_union) if tag_union else 0.0

    # Title token overlap (Jaccard on words)
    tokens_a = set(re.findall(r"\w+", a.title.lower()))
    tokens_b = set(re.findall(r"\w+", b.title.lower()))
    token_union = tokens_a | tokens_b
    token_jaccard = len(tokens_a & tokens_b) / len(token_union) if token_union else 0.0

    return 0.5 * title_sim + 0.3 * tag_jaccard + 0.2 * token_jaccard


def _find(parent: dict[str, str], x: str) -> str:
    """Union-Find: find with path compression."""
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def _union(parent: dict[str, str], rank: dict[str, int], a: str, b: str) -> None:
    """Union-Find: union by rank."""
    ra, rb = _find(parent, a), _find(parent, b)
    if ra == rb:
        return
    if rank[ra] < rank[rb]:
        ra, rb = rb, ra
    parent[rb] = ra
    if rank[ra] == rank[rb]:
        rank[ra] += 1


def load_reviewed() -> list[dict]:
    """Load previously reviewed pairs from dedup_reviewed.json."""
    if not REVIEWED_PATH.exists():
        return []
    try:
        data = json.loads(REVIEWED_PATH.read_text(encoding="utf-8"))
        return data.get("reviewed", [])
    except (json.JSONDecodeError, OSError):
        return []


def save_reviewed(reviewed: list[dict]) -> None:
    """Persist reviewed pairs to dedup_reviewed.json (atomic write)."""
    data = json.dumps({"reviewed": reviewed}, ensure_ascii=False, indent=2)
    fd, tmp_path = tempfile.mkstemp(
        dir=REVIEWED_PATH.parent, suffix=".tmp", prefix=REVIEWED_PATH.stem
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp_path, REVIEWED_PATH)
    except BaseException:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def _reviewed_set(reviewed: list[dict]) -> set[frozenset[str]]:
    """Convert reviewed list to a set of frozensets for fast lookup."""
    result: set[frozenset[str]] = set()
    for entry in reviewed:
        titles = entry.get("titles", [])
        if len(titles) >= 2:
            result.add(frozenset(titles))
    return result


def find_candidate_groups(
    notes: list[VaultNote],
    threshold: float,
    reviewed: list[dict],
) -> list[CandidateGroup]:
    """Find groups of similar notes using Union-Find on pairs above threshold.

    Filters out pairs already in reviewed list.
    Limits groups to max 4 notes (larger groups split into pairs).
    """
    reviewed_pairs = _reviewed_set(reviewed)

    # Compute all pairwise similarities above threshold
    pairs: list[tuple[str, str, float]] = []
    for i in range(len(notes)):
        for j in range(i + 1, len(notes)):
            sim = compute_similarity(notes[i], notes[j])
            if sim >= threshold:
                pair_key = frozenset([notes[i].title, notes[j].title])
                if pair_key not in reviewed_pairs:
                    pairs.append((notes[i].title, notes[j].title, sim))

    if not pairs:
        return []

    # Union-Find grouping
    all_titles = {p[0] for p in pairs} | {p[1] for p in pairs}
    parent = {t: t for t in all_titles}
    rank = {t: 0 for t in all_titles}

    for a, b, _ in pairs:
        _union(parent, rank, a, b)

    # Collect connected components
    components: dict[str, list[str]] = {}
    for t in all_titles:
        root = _find(parent, t)
        components.setdefault(root, []).append(t)

    # Build note lookup
    note_by_title = {n.title: n for n in notes}

    groups: list[CandidateGroup] = []
    group_id = 0

    for component_titles in components.values():
        component_notes = [note_by_title[t] for t in component_titles if t in note_by_title]
        component_pairs = [
            (a, b, s) for a, b, s in pairs
            if a in component_titles and b in component_titles
        ]

        if len(component_notes) <= 4:
            groups.append(CandidateGroup(
                group_id=group_id,
                notes=component_notes,
                pairs=component_pairs,
            ))
            group_id += 1
        else:
            # Split large groups into pairs
            for a, b, s in component_pairs:
                na = note_by_title.get(a)
                nb = note_by_title.get(b)
                if na and nb:
                    groups.append(CandidateGroup(
                        group_id=group_id,
                        notes=[na, nb],
                        pairs=[(a, b, s)],
                    ))
                    group_id += 1

    return groups


# ── Phase 3: Semantic Verification ───────────────────────────────────────────


def assemble_dedup_prompt(groups: list[CandidateGroup], tags: list[str]) -> str:
    """Build a batch semantic dedup verification prompt."""
    lines: list[str] = [
        "You are verifying potential duplicate notes in an Obsidian vault.",
        "For each group of candidate duplicates, determine if they are truly about "
        "the same concept/topic (semantic duplicates) or legitimately different notes.",
        "",
        "For EACH group, respond with:",
        '- "is_duplicate": true/false',
        '- "confidence": 0.0-1.0 (how confident you are)',
        '- If is_duplicate is true, also provide:',
        '  - "canonical_title": best title for the merged note (concise noun phrase)',
        f'  - "canonical_tags": 2-5 tags from this list: {json.dumps(tags[:50])}...',
        '  - "canonical_body": merged body text, 150-600 words, preserving all unique '
        'information from both notes. Use [[wikilinks]] where appropriate.',
        "",
        "Output a JSON object: { \"groups\": [ { \"group_id\": N, ... }, ... ] }",
        "Output ONLY JSON, no prose.",
        "",
        "---",
        "",
    ]

    for group in groups:
        lines.append(f"## Group {group.group_id}")
        lines.append(f"Similarity pairs: {[(a, b, round(s, 3)) for a, b, s in group.pairs]}")
        lines.append("")

        for note in group.notes:
            # First 300 words of body
            words = note.body.split()
            truncated = " ".join(words[:300])
            if len(words) > 300:
                truncated += " [...]"

            lines.append(f"### {note.title}")
            lines.append(f"Tags: {note.tags}")
            lines.append(f"Source: {note.source_doc}")
            lines.append(f"Word count: {note.word_count}")
            lines.append("")
            lines.append(truncated)
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def verify_with_claude(
    groups: list[CandidateGroup],
    tags: list[str],
    *,
    backend: str = "auto",
    timeout_seconds: int = 300,
) -> list[CandidateGroup]:
    """Send candidate groups to the active semantic verification backend.

    Processes in batches of up to 5 groups.
    """
    verified: list[CandidateGroup] = []

    for batch_start in range(0, len(groups), 5):
        batch = groups[batch_start:batch_start + 5]
        prompt = assemble_dedup_prompt(batch, tags)

        print(
            f"  Verifying batch {batch_start // 5 + 1} "
            f"({len(batch)} groups)...",
            file=sys.stderr,
        )

        _, raw = call_rewriter(
            prompt,
            backend=backend,
            timeout_seconds=timeout_seconds,
            project_root=PROJECT_ROOT,
        )
        try:
            result = extract_json(raw)
        except ValueError as e:
            print(f"WARNING: Failed to parse Claude response: {e}", file=sys.stderr)
            continue

        for g_result in result.get("groups", []):
            gid = g_result.get("group_id")
            # Find matching group
            matching = [g for g in batch if g.group_id == gid]
            if not matching:
                continue
            group = matching[0]

            group.is_duplicate = g_result.get("is_duplicate", False)
            group.confidence = g_result.get("confidence", 0.0)
            group.canonical_title = g_result.get("canonical_title")
            group.canonical_tags = g_result.get("canonical_tags")
            group.canonical_body = g_result.get("canonical_body")
            verified.append(group)

    return verified


# ── Phase 4: Interactive Merge ────────────────────────────────────────────────


def execute_merge(
    group: CandidateGroup,
    config: dict,
    vault_path: Path,
) -> dict[str, str]:
    """Write canonical note and archive duplicates.

    Returns mapping of old_title -> canonical_title for wikilink updates.
    """
    title = group.canonical_title
    tags = group.canonical_tags or []
    body = group.canonical_body or ""

    # Determine source_doc from first note
    source_doc = group.notes[0].source_doc if group.notes else ""

    note_dict = {
        "title": title,
        "tags": tags,
        "date": date.today().isoformat(),
        "source_doc": source_doc,
        "note_type": "atomic",
        "body": body,
    }

    content = render_note_md(note_dict)
    filename = sanitize_filename(title) + ".md"
    dest_dir = get_vault_dest("atomic", config)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / filename

    # Archive duplicates first so canonical paths that reuse an existing title
    # do not immediately archive the newly written canonical note.
    archive_dir = vault_path / ".archive"
    archive_dir.mkdir(exist_ok=True)
    today = date.today().isoformat()
    title_map: dict[str, str] = {}

    for note in group.notes:
        if note.path.exists():
            archive_name = f"{today}_dedup_{note.path.name}"
            archive_dest = archive_dir / archive_name
            # Handle collision
            counter = 1
            while archive_dest.exists():
                stem = note.path.stem
                archive_name = f"{today}_dedup_{stem}_{counter}.md"
                archive_dest = archive_dir / archive_name
                counter += 1
            shutil.move(str(note.path), str(archive_dest))
            print(f"    Archived: {note.path.name} -> .archive/{archive_name}", file=sys.stderr)

        title_map[note.title] = title

    # Write canonical note after duplicates have been archived.
    dest_path.write_text(content, encoding="utf-8")
    print(f"    Created: {filename}", file=sys.stderr)

    return title_map


def update_registry_after_merge(
    group: CandidateGroup,
    canonical_title: str,
) -> None:
    """Update processed.json: replace old titles with canonical title."""
    registry = load_registry()
    changed = False

    for note in group.notes:
        source = note.source_doc
        if source and source in registry:
            old_titles = registry[source].get("note_titles", [])
            if note.title in old_titles:
                old_titles.remove(note.title)
                changed = True

    # Add canonical title to first source_doc entry
    if group.notes:
        source = group.notes[0].source_doc
        if source and source in registry:
            titles = registry[source].get("note_titles", [])
            if canonical_title not in titles:
                titles.append(canonical_title)
                titles.sort()
            registry[source]["note_count"] = len(titles)
            changed = True

    if changed:
        save_registry(registry)


def interactive_merge(
    groups: list[CandidateGroup],
    config: dict,
    vault_path: Path,
    reviewed: list[dict],
    *,
    auto_threshold: float | None = None,
    dry_run: bool = False,
    non_interactive: bool = False,
    decision: str = "skip",
) -> dict[str, str]:
    """Merge decision loop. Returns full title_map for wikilink updates."""
    all_title_maps: dict[str, str] = {}

    for group in groups:
        if not group.is_duplicate:
            continue

        titles = [n.title for n in group.notes]
        print(f"\n  Group {group.group_id}: {titles}", file=sys.stderr)
        print(f"    Confidence: {group.confidence:.2f}", file=sys.stderr)
        print(f"    Canonical title: {group.canonical_title}", file=sys.stderr)
        print(f"    Canonical tags: {group.canonical_tags}", file=sys.stderr)

        if dry_run:
            print("    [dry-run] Would merge", file=sys.stderr)
            continue

        # Auto-merge if confidence is above threshold
        if auto_threshold and group.confidence >= auto_threshold:
            print(f"    [auto] Merging (confidence >= {auto_threshold})", file=sys.stderr)
            title_map = execute_merge(group, config, vault_path)
            update_registry_after_merge(group, group.canonical_title)
            all_title_maps.update(title_map)
            reviewed.append({
                "titles": titles,
                "decision": "merge",
                "date": date.today().isoformat(),
            })
            continue

        # Non-interactive policy
        if non_interactive or not sys.stdin.isatty():
            print(f"    [non-interactive] Decision -> {decision}", file=sys.stderr)
            if decision == "keep":
                reviewed.append({
                    "titles": titles,
                    "decision": "keep",
                    "date": date.today().isoformat(),
                })
                continue
            if decision == "merge":
                title_map = execute_merge(group, config, vault_path)
                update_registry_after_merge(group, group.canonical_title)
                all_title_maps.update(title_map)
                reviewed.append({
                    "titles": titles,
                    "decision": "merge",
                    "date": date.today().isoformat(),
                })
                continue
            print("    [non-interactive] Skipping", file=sys.stderr)
            continue

        while True:
            try:
                choice = input(
                    "    [m]erge / [k]eep both / [s]kip? [s]: "
                ).strip().lower()
            except EOFError:
                choice = "s"

            if choice in ("", "s", "skip"):
                # Will reappear next run
                break
            elif choice in ("k", "keep"):
                reviewed.append({
                    "titles": titles,
                    "decision": "keep",
                    "date": date.today().isoformat(),
                })
                print("    Marked as reviewed (keep both)", file=sys.stderr)
                break
            elif choice in ("m", "merge"):
                title_map = execute_merge(group, config, vault_path)
                update_registry_after_merge(group, group.canonical_title)
                all_title_maps.update(title_map)
                reviewed.append({
                    "titles": titles,
                    "decision": "merge",
                    "date": date.today().isoformat(),
                })
                print("    Merged successfully", file=sys.stderr)
                break
            else:
                print("    Please enter 'm', 'k', or 's'.", file=sys.stderr)

    return all_title_maps


# ── Phase 5: Wikilink Update ─────────────────────────────────────────────────


def update_wikilinks(
    vault_path: Path,
    title_map: dict[str, str],
) -> int:
    """Replace [[old title]] -> [[canonical title]] across entire vault.

    Excludes .archive/ and other SKIP_DIRS.
    Returns count of files modified.
    """
    if not title_map:
        return 0

    # Build regex: match any old title inside [[ ]]
    escaped = [re.escape(old) for old in title_map]
    pattern = re.compile(r"\[\[(" + "|".join(escaped) + r")\]\]")

    modified = 0
    for md_file in vault_path.rglob("*.md"):
        rel = md_file.relative_to(vault_path)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue

        try:
            content = md_file.read_text(encoding="utf-8")
        except OSError:
            continue

        new_content = pattern.sub(
            lambda m: f"[[{title_map[m.group(1)]}]]",
            content,
        )

        if new_content != content:
            md_file.write_text(new_content, encoding="utf-8")
            modified += 1

    return modified


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Semantic deduplication of Obsidian vault notes."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show candidates and semantic verification results without making changes",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-merge when verification confidence >= --confidence threshold",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.55,
        help="Composite similarity threshold for candidate detection (default: 0.55)",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.85,
        help="Verification confidence threshold for auto-merge (default: 0.85)",
    )
    parser.add_argument(
        "--folder",
        help="Scan only this subfolder of the vault",
    )
    parser.add_argument(
        "--skip-claude",
        action="store_true",
        help="Only show local candidates (skip semantic verification)",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Disable prompts and use the policy from --decision",
    )
    parser.add_argument(
        "--decision",
        choices=("merge", "keep", "skip"),
        default="skip",
        help="Decision policy in non-interactive mode (default: skip)",
    )
    parser.add_argument(
        "--backend",
        choices=("auto", "claude", "codex"),
        default="auto",
        help="Semantic verification backend to use (default: auto-detect from the current agent environment)",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=300,
        help="Timeout for each semantic verification backend call (default: 300)",
    )
    args = parser.parse_args()

    # Load config
    config = _load_config(strict=True)
    vault_path = Path(config["vault"]["vault_path"])

    if not vault_path.exists():
        print(f"ERROR: Vault path does not exist: {vault_path}", file=sys.stderr)
        sys.exit(1)

    # ── Phase 1: Deep Vault Scan ──
    print(">> Phase 1: Deep vault scan...", file=sys.stderr)
    notes = deep_scan_vault(vault_path, folder=args.folder)
    print(f"  Scanned {len(notes)} notes (MOC filtered out)", file=sys.stderr)

    if len(notes) < 2:
        print("Not enough notes for deduplication.", file=sys.stderr)
        sys.exit(0)

    # ── Phase 2: Local Candidate Detection ──
    print(f">> Phase 2: Finding candidates (threshold={args.threshold})...", file=sys.stderr)
    reviewed = load_reviewed()
    groups = find_candidate_groups(notes, args.threshold, reviewed)
    print(f"  Found {len(groups)} candidate groups", file=sys.stderr)

    if not groups:
        print("No duplicate candidates found.", file=sys.stderr)
        sys.exit(0)

    # Print candidates
    for group in groups:
        titles = [n.title for n in group.notes]
        best_sim = max(s for _, _, s in group.pairs) if group.pairs else 0
        print(f"  Group {group.group_id}: {titles} (max sim: {best_sim:.3f})", file=sys.stderr)

    if args.skip_claude:
        print("\n--skip-claude: Stopping after local detection.", file=sys.stderr)
        sys.exit(0)

    # ── Phase 3: Semantic Verification ──
    print(">> Phase 3: Semantic verification...", file=sys.stderr)
    tags = load_tags()
    verified = verify_with_claude(
        groups,
        tags,
        backend=args.backend,
        timeout_seconds=args.timeout_seconds,
    )

    confirmed = [g for g in verified if g.is_duplicate]
    print(
        f"  Semantic verification confirmed {len(confirmed)}/{len(verified)} as duplicates",
        file=sys.stderr,
    )

    if not confirmed:
        print("No duplicates confirmed by semantic verification.", file=sys.stderr)
        sys.exit(0)

    # ── Phase 4: Merge Decision ──
    print(">> Phase 4: Merge decisions...", file=sys.stderr)
    auto_threshold = args.confidence if args.auto else None
    title_map = interactive_merge(
        verified, config, vault_path, reviewed,
        auto_threshold=auto_threshold,
        dry_run=args.dry_run,
        non_interactive=args.non_interactive,
        decision=args.decision,
    )
    save_reviewed(reviewed)

    if args.dry_run:
        print("\n--dry-run: No changes made.", file=sys.stderr)
        sys.exit(0)

    # ── Phase 5: Wikilink Update ──
    if title_map:
        print(">> Phase 5: Updating wikilinks...", file=sys.stderr)
        modified = update_wikilinks(vault_path, title_map)
        print(f"  Updated wikilinks in {modified} files", file=sys.stderr)

    print("\nDone.", file=sys.stderr)


if __name__ == "__main__":
    main()
