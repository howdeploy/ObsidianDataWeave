"""scan_vault.py — Scan Obsidian vault and collect all note titles for wikilink resolution.

Usage:
    python3 scripts/scan_vault.py [--exclude "filename.md"]

Output (stdout): JSON with vault titles and notes grouped by folder.
Diagnostics go to stderr.
"""

import argparse
import json
import sys
from pathlib import Path

try:
    from scripts.config import load_config as _load_config
except ModuleNotFoundError:
    from config import load_config as _load_config

# Directories to skip during vault scan
SKIP_DIRS = {".obsidian", ".trash", ".smart-env", ".archive", ".git"}


def load_config() -> dict:
    """Strict config loader — vault_path required for scanning."""
    return _load_config(strict=True)


def scan_vault(vault_path: Path, exclude: set[str] | None = None) -> dict:
    """Recursively scan vault for .md files.

    Args:
        vault_path: Root path of the Obsidian vault.
        exclude: Set of filenames (with .md) to exclude from results.

    Returns:
        {
            "titles": ["Title1", "Title2", ...],
            "notes_by_folder": {
                "FolderName": ["Title1", "Title2"],
                ".": ["RootNote1"]
            }
        }
    """
    if exclude is None:
        exclude = set()

    titles: list[str] = []
    notes_by_folder: dict[str, list[str]] = {}

    for md_file in vault_path.rglob("*.md"):
        # Skip files in excluded directories
        if any(part in SKIP_DIRS for part in md_file.relative_to(vault_path).parts):
            continue

        # Skip explicitly excluded files
        if md_file.name in exclude:
            continue

        title = md_file.stem
        titles.append(title)

        # Group by relative parent folder
        rel_parent = md_file.parent.relative_to(vault_path)
        folder_key = str(rel_parent) if str(rel_parent) != "." else "."
        if folder_key not in notes_by_folder:
            notes_by_folder[folder_key] = []
        notes_by_folder[folder_key].append(title)

    titles.sort()
    for folder in notes_by_folder:
        notes_by_folder[folder].sort()

    return {"titles": titles, "notes_by_folder": notes_by_folder}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan Obsidian vault and collect note titles for wikilink resolution."
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Filename(s) to exclude from scan (e.g., 'Note.md'). Can be repeated.",
    )
    args = parser.parse_args()

    config = load_config()
    vault_path = Path(config["vault"]["vault_path"])

    if not vault_path.exists():
        print(f"ERROR: Vault path does not exist: {vault_path}", file=sys.stderr)
        sys.exit(1)

    exclude_set = set(args.exclude)
    result = scan_vault(vault_path, exclude=exclude_set)

    print(
        f"Scanned vault: {len(result['titles'])} notes in "
        f"{len(result['notes_by_folder'])} folders",
        file=sys.stderr,
    )

    # Output JSON to stdout
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
