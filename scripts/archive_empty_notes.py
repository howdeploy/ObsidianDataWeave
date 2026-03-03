"""archive_empty_notes.py — Move truly empty vault notes into .archive."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

try:
    from scripts.audit_vault import parse_note
    from scripts.config import load_config
    from scripts.scan_vault import SKIP_DIRS
except ModuleNotFoundError:
    from audit_vault import parse_note
    from config import load_config
    from scan_vault import SKIP_DIRS


def should_archive_empty_note(path: Path) -> bool:
    """Archive only files that are fully empty and carry no frontmatter."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    if text.strip():
        return False
    record = parse_note(path)
    if record is None:
        return False
    return record.words == 0 and not record.frontmatter


def archive_destination(vault_path: Path, note_path: Path, *, stamp: str) -> Path:
    """Build an archive path that preserves the relative folder structure."""
    rel = note_path.relative_to(vault_path)
    return vault_path / ".archive" / "empty-notes" / stamp / rel


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Archive truly empty vault notes with no frontmatter or body."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which files would be archived without modifying the vault",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Move empty notes into the .archive folder",
    )
    args = parser.parse_args()

    config = load_config(strict=True)
    vault_path = Path(config["vault"]["vault_path"])
    candidates = []
    stamp = date.today().isoformat()
    for note_path in vault_path.rglob("*.md"):
        rel = note_path.relative_to(vault_path)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if not should_archive_empty_note(note_path):
            continue
        destination = archive_destination(vault_path, note_path, stamp=stamp)
        candidates.append({"path": str(note_path), "archive_path": str(destination)})
        if args.apply and not args.dry_run:
            destination.parent.mkdir(parents=True, exist_ok=True)
            note_path.rename(destination)

    print(
        json.dumps(
            {
                "summary": {
                    "candidate_notes": len(candidates),
                    "archived_notes": len(candidates) if args.apply and not args.dry_run else 0,
                    "dry_run": args.dry_run or not args.apply,
                },
                "notes": candidates,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
