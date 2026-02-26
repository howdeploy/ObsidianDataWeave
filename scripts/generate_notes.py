"""generate_notes.py — Render atom plan JSON into .md files in staging directory.

Usage:
    python3 scripts/generate_notes.py <atom-plan.json>

Prints staging directory path to stdout (for process.py chaining).
All diagnostics go to stderr.
"""

import argparse
import json
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

# Characters forbidden in Obsidian filenames
_OBSIDIAN_FORBIDDEN = r'\/:"*<>|?'


# ── Config ─────────────────────────────────────────────────────────────────────


def load_config() -> dict:
    """Read config.toml via tomllib; fall back to defaults if not found."""
    config_path = PROJECT_ROOT / "config.toml"
    if not config_path.exists():
        print(
            "WARNING: config.toml not found; using default staging_dir=/tmp/dw/staging",
            file=sys.stderr,
        )
        return {"rclone": {"staging_dir": "/tmp/dw/staging"}}

    if tomllib is None:
        print(
            "WARNING: tomllib/tomli not available; using default config. "
            "Upgrade to Python 3.11+ or: pip install tomli",
            file=sys.stderr,
        )
        return {"rclone": {"staging_dir": "/tmp/dw/staging"}}

    with open(config_path, "rb") as f:
        return tomllib.load(f)


# ── Filename sanitization ───────────────────────────────────────────────────────


def sanitize_filename(title: str, max_bytes: int = 200) -> str:
    """Sanitize a note title into a safe filename stem.

    - Replaces Obsidian-forbidden characters (\\/:\"*<>|?) with '-'
    - Removes NUL bytes
    - Truncates to max_bytes in UTF-8 (not chars) to stay within ext4's 255-byte
      limit (leaves room for '.md' + safety margin; Cyrillic = 2 bytes/char)
    - Strips leading/trailing whitespace
    """
    # Remove NUL bytes
    sanitized = title.replace("\x00", "")

    # Replace forbidden characters with '-'
    for ch in _OBSIDIAN_FORBIDDEN:
        sanitized = sanitized.replace(ch, "-")

    # Strip surrounding whitespace
    sanitized = sanitized.strip()

    # Truncate by UTF-8 byte count, not character count
    encoded = sanitized.encode("utf-8")
    if len(encoded) > max_bytes:
        truncated = encoded[:max_bytes].decode("utf-8", errors="ignore")
        sanitized = truncated.strip()

    return sanitized


# ── Markdown rendering ──────────────────────────────────────────────────────────


def render_note_md(note: dict) -> str:
    """Build .md file content with YAML frontmatter from a note dict.

    Frontmatter schema (v1, locked):
        tags:       YAML list (one '  - tag' per line)
        date:       ISO date string, as-is
        source_doc: always double-quoted to handle colons in titles
        note_type:  as-is

    Body: blank line, body text (no H1 — Obsidian uses filename as title).
    Uses string interpolation — NOT PyYAML — to keep exact formatting.
    """
    title = note.get("title", "")
    tags = note.get("tags", [])
    date_val = note.get("date", "")
    source_doc = note.get("source_doc", "")
    note_type = note.get("note_type", "")
    body = note.get("body", "")

    # Build tags YAML list lines
    tags_lines = "\n".join(f"  - {tag}" for tag in tags)

    # Double-quote source_doc; escape any embedded double-quotes
    source_doc_escaped = source_doc.replace('"', '\\"')
    source_doc_quoted = f'"{source_doc_escaped}"'

    content = (
        "---\n"
        f"tags:\n{tags_lines}\n"
        f"date: {date_val}\n"
        f"source_doc: {source_doc_quoted}\n"
        f"note_type: {note_type}\n"
        "---\n"
        "\n"
        f"{body}\n"
    )
    return content


# ── Main ────────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Render atom plan JSON into .md files in the staging directory."
        )
    )
    parser.add_argument("input", help="Path to atom plan JSON file from atomize.py")
    args = parser.parse_args()

    # Load atom plan JSON
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    plan = json.loads(input_path.read_text(encoding="utf-8"))

    if "notes" not in plan:
        print("ERROR: Atom plan JSON missing required 'notes' key", file=sys.stderr)
        sys.exit(1)

    # Load config and derive staging dir
    config = load_config()
    staging_dir = Path(config.get("rclone", {}).get("staging_dir", "/tmp/dw/staging"))
    staging_dir.mkdir(parents=True, exist_ok=True)

    notes = plan["notes"]
    atomic_count = 0
    moc_count = 0

    for note in notes:
        title = note.get("title", "untitled")
        filename = sanitize_filename(title) + ".md"
        content = render_note_md(note)
        dest = staging_dir / filename
        dest.write_text(content, encoding="utf-8")

        note_type = note.get("note_type", "")
        if note_type == "atomic":
            atomic_count += 1
        elif note_type == "moc":
            moc_count += 1

    total = len(notes)
    print(
        f"Generated {total} .md files in staging ({atomic_count} atomic + {moc_count} MOC)",
        file=sys.stderr,
    )

    # Print staging dir path to stdout for process.py chaining
    print(str(staging_dir))


if __name__ == "__main__":
    main()
