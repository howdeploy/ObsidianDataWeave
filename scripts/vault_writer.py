"""vault_writer.py — Copy staged .md files to the Obsidian vault with dedup and folder routing.

Usage:
    python3 scripts/vault_writer.py --staging <staging-dir> [--atom-plan <atom-plan.json>]

vault_writer.py is the ONLY script permitted to write to vault_path.

Routing by note_type (from frontmatter):
    atomic  -> vault_path/notes_folder
    moc     -> vault_path/moc_folder
    source  -> vault_path/source_folder
    <other> -> vault_path/notes_folder  (fallback)

Deduplication: (source_doc, title) pair tracked in processed.json registry.
MOC files are always overwritten (auto-generated, no manual edits expected).
MOC written last (sorted after all atomic notes).

All diagnostics go to stderr. Summary printed to both stdout and stderr.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

# Attempt tomllib import (stdlib since Python 3.11; fallback to tomli for 3.10)
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        tomllib = None  # type: ignore

PROJECT_ROOT = Path(__file__).parent.parent
REGISTRY_PATH = PROJECT_ROOT / "processed.json"


# ── Config ──────────────────────────────────────────────────────────────────────


def load_config() -> dict:
    """Read config.toml via tomllib.

    Unlike generate_notes.py, vault_writer.py has NO fallback — vault_path MUST
    be known before writing to the real Obsidian vault.  Missing or unparseable
    config is a hard error.
    """
    config_path = PROJECT_ROOT / "config.toml"

    if not config_path.exists():
        print(
            "ERROR: config.toml not found. vault_writer.py requires vault_path "
            "to be configured. Copy config.example.toml to config.toml and fill "
            "in your vault path.",
            file=sys.stderr,
        )
        sys.exit(1)

    if tomllib is None:
        print(
            "ERROR: tomllib/tomli not available. vault_writer.py cannot parse "
            "config.toml without it. Upgrade to Python 3.11+ or: pip install tomli",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(config_path, "rb") as f:
        return tomllib.load(f)


# ── Registry (processed.json) ───────────────────────────────────────────────────


def load_registry() -> dict:
    """Read processed.json from PROJECT_ROOT.

    Registry schema:
    {
        "SourceDoc.docx": {
            "source_doc": "SourceDoc.docx",
            "date": "2026-02-26",
            "note_count": 5,
            "note_titles": ["Title1", "Title2", ...]
        }
    }

    Returns {} on first run (file does not exist). Never crashes on missing file.
    """
    if not REGISTRY_PATH.exists():
        return {}
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(
            f"WARNING: Could not read processed.json: {exc}. Starting with empty registry.",
            file=sys.stderr,
        )
        return {}


def save_registry(registry: dict) -> None:
    """Write processed.json to PROJECT_ROOT atomically (all-at-once, after all copies)."""
    REGISTRY_PATH.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── Frontmatter parsing ─────────────────────────────────────────────────────────


def parse_frontmatter(content: str) -> dict:
    """Extract key/value pairs from YAML frontmatter block (between --- delimiters).

    Handles:
    - tags as a list (lines starting with '  - ')
    - double-quoted values (strips outer quotes)
    - Keys returned: tags, date, source_doc, note_type

    Returns an empty dict if no frontmatter found.
    """
    parts = content.split("---")
    if len(parts) < 3:
        return {}

    # The frontmatter block is between the first two '---'
    fm_block = parts[1]
    result: dict = {}
    current_key: str | None = None
    tag_list: list[str] = []
    in_tags = False

    for line in fm_block.splitlines():
        # Tag list item
        if line.startswith("  - ") and in_tags:
            tag_list.append(line[4:].strip())
            continue

        # Top-level key: value pair
        if ": " in line or (line.endswith(":") and not line.startswith(" ")):
            in_tags = False
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip()

                # Strip surrounding double-quotes from values like "Smart Connections: ..."
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1].replace('\\"', '"')

                if key == "tags":
                    in_tags = True
                    tag_list = []
                    current_key = "tags"
                else:
                    result[key] = value
                    current_key = key

    # Commit collected tag list
    if tag_list:
        result["tags"] = tag_list

    return result


# ── Conflict resolution ─────────────────────────────────────────────────────────


def resolve_conflict(title: str, source_doc: str) -> str:
    """Ask the user whether to skip or overwrite a duplicate note.

    Returns 'skip' or 'overwrite'.

    If stdin is not a TTY (non-interactive / pipe), auto-skips with a stderr message.
    """
    if not sys.stdin.isatty():
        print(
            f"  [auto-skip] Duplicate (non-interactive): '{title}' from '{source_doc}'",
            file=sys.stderr,
        )
        return "skip"

    while True:
        try:
            choice = input(
                f"  Duplicate found: '{title}' (from {source_doc})\n"
                "  [s]kip / [o]verwrite? [s]: "
            ).strip().lower()
        except EOFError:
            return "skip"

        if choice in ("", "s", "skip"):
            return "skip"
        if choice in ("o", "overwrite"):
            return "overwrite"
        print("  Please enter 's' to skip or 'o' to overwrite.", file=sys.stderr)


# ── Vault destination routing ───────────────────────────────────────────────────


def get_vault_dest(note_type: str, config: dict) -> Path:
    """Return the vault subfolder Path for a given note_type.

    Routing:
        atomic  -> vault_path/notes_folder
        moc     -> vault_path/moc_folder
        source  -> vault_path/source_folder
        <other> -> vault_path/notes_folder  (fallback)
    """
    vault_path = Path(config["vault"]["vault_path"])
    vault_cfg = config.get("vault", {})

    if note_type == "moc":
        folder = vault_cfg.get("moc_folder", "MOCs")
    elif note_type == "source":
        folder = vault_cfg.get("source_folder", "Sources")
    else:
        # "atomic" and any unknown type
        folder = vault_cfg.get("notes_folder", "Notes")

    return vault_path / folder


# ── Sort key: MOC last ──────────────────────────────────────────────────────────


def _moc_sort_key(md_file: Path) -> tuple[int, str]:
    """Sort key that places MOC files after all atomic notes.

    Detection: frontmatter note_type=='moc' OR stem ending with ' — MOC'.
    Fallback (cannot read file): treat as non-MOC (sort first).
    """
    try:
        content = md_file.read_text(encoding="utf-8")
        fm = parse_frontmatter(content)
        is_moc = fm.get("note_type", "") == "moc" or md_file.stem.endswith(" \u2014 MOC")
    except OSError:
        is_moc = False
    return (1 if is_moc else 0, md_file.name)


# ── Main ────────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Copy staged .md files to the Obsidian vault with deduplication and "
            "folder routing. vault_writer.py is the only script that writes to vault_path."
        )
    )
    parser.add_argument(
        "--staging",
        required=True,
        help="Path to staging directory containing .md files",
    )
    parser.add_argument(
        "--atom-plan",
        help=(
            "Optional path to atom plan JSON for additional note_type/source_doc "
            "context. Frontmatter remains the primary source."
        ),
    )
    args = parser.parse_args()

    staging_dir = Path(args.staging)
    if not staging_dir.exists():
        print(f"ERROR: Staging directory not found: {args.staging}", file=sys.stderr)
        sys.exit(1)

    # Load config (hard error if missing — vault_path must be known)
    config = load_config()
    if "vault" not in config or "vault_path" not in config.get("vault", {}):
        print(
            "ERROR: config.toml is missing [vault] section or vault_path key.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Load dedup registry
    registry = load_registry()

    # Optionally load atom plan for supplementary note_type/source_doc context
    atom_plan_titles: dict[str, str] = {}  # stem -> note_type
    atom_plan_source: dict[str, str] = {}  # title -> source_doc
    if args.atom_plan:
        try:
            plan_data = json.loads(Path(args.atom_plan).read_text(encoding="utf-8"))
            for note in plan_data.get("notes", []):
                t = note.get("title", "")
                atom_plan_titles[t] = note.get("note_type", "")
                atom_plan_source[t] = note.get("source_doc", "")
        except (OSError, json.JSONDecodeError) as exc:
            print(
                f"WARNING: Could not read atom plan JSON '{args.atom_plan}': {exc}. "
                "Falling back to frontmatter-only mode.",
                file=sys.stderr,
            )

    # Collect all .md files (skip non-note files like proposed-tags.md)
    md_files = [
        p for p in staging_dir.glob("*.md")
        if p.name != "proposed-tags.md"
    ]
    if not md_files:
        print("WARNING: No .md files found in staging directory.", file=sys.stderr)
        summary = "Created 0 notes + 0 MOC, skipped 0 duplicates"
        print(summary, file=sys.stderr)
        print(summary)
        return

    # Sort: atomic notes first, MOC files last
    md_files.sort(key=_moc_sort_key)

    # Track per-session results for registry update
    # Maps source_doc -> {date, note_titles set}
    session_writes: dict[str, dict] = {}

    created_atomic = 0
    created_moc = 0
    skipped = 0

    for md_file in md_files:
        try:
            content = md_file.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"WARNING: Cannot read {md_file.name}: {exc}", file=sys.stderr)
            continue

        fm = parse_frontmatter(content)
        title = md_file.stem  # Use filename stem as title fallback
        # Extract title from the H1 heading if possible
        for line in content.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break

        note_type = fm.get("note_type", "")
        source_doc = fm.get("source_doc", "")
        date_val = fm.get("date", "")

        # Supplement with atom plan data if frontmatter is sparse
        if not note_type and title in atom_plan_titles:
            note_type = atom_plan_titles[title]
        if not source_doc and title in atom_plan_source:
            source_doc = atom_plan_source[title]

        # Dedup check — MOC always overwrites, atomic notes check registry
        if note_type != "moc" and source_doc:
            existing = registry.get(source_doc, {})
            existing_titles: list[str] = existing.get("note_titles", [])
            if title in existing_titles:
                action = resolve_conflict(title, source_doc)
                if action == "skip":
                    skipped += 1
                    continue
                # action == "overwrite": fall through to copy

        # Determine vault destination folder
        dest_dir = get_vault_dest(note_type, config)
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest_path = dest_dir / md_file.name
        shutil.copy2(md_file, dest_path)

        # Track for registry update
        if source_doc:
            if source_doc not in session_writes:
                session_writes[source_doc] = {
                    "date": date_val,
                    "note_titles": [],
                }
            session_writes[source_doc]["note_titles"].append(title)

        if note_type == "moc":
            created_moc += 1
        else:
            created_atomic += 1

    # Update registry atomically after all vault writes complete
    for source_doc, info in session_writes.items():
        existing = registry.get(source_doc, {
            "source_doc": source_doc,
            "date": info["date"],
            "note_count": 0,
            "note_titles": [],
        })
        # Merge new titles (avoid duplication in overwrite scenarios)
        existing_titles_set = set(existing.get("note_titles", []))
        for t in info["note_titles"]:
            existing_titles_set.add(t)
        existing["note_titles"] = sorted(existing_titles_set)
        existing["note_count"] = len(existing["note_titles"])
        if info["date"] and not existing.get("date"):
            existing["date"] = info["date"]
        registry[source_doc] = existing

    if session_writes:
        save_registry(registry)
        print("Registry updated: processed.json", file=sys.stderr)

    summary = (
        f"Created {created_atomic} notes + {created_moc} MOC, "
        f"skipped {skipped} duplicates"
    )
    print(summary, file=sys.stderr)
    print(summary)


if __name__ == "__main__":
    main()
