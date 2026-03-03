"""rebuild_processed.py — Rebuild processed.json from actual vault contents."""

from __future__ import annotations

import json
import os
import tempfile
from collections import defaultdict
from pathlib import Path

try:
    from scripts.config import REGISTRY_PATH, load_config
    from scripts.vault_writer import parse_frontmatter
except ModuleNotFoundError:
    from config import REGISTRY_PATH, load_config
    from vault_writer import parse_frontmatter


def rebuild_registry(vault_path: Path) -> dict[str, dict]:
    """Scan the vault and rebuild the processed registry from frontmatter."""
    grouped: dict[str, dict[str, object]] = defaultdict(
        lambda: {"source_doc": "", "date": "", "note_titles": []}
    )

    for md_file in vault_path.rglob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
        except OSError:
            continue

        frontmatter = parse_frontmatter(content)
        if not frontmatter:
            continue

        source_doc = frontmatter.get("source_doc")
        if not isinstance(source_doc, str) or not source_doc.strip():
            continue

        title = md_file.stem
        for line in content.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break

        entry = grouped[source_doc]
        entry["source_doc"] = source_doc
        date_val = frontmatter.get("date", "")
        if date_val and not entry["date"]:
            entry["date"] = str(date_val)
        entry["note_titles"].append(title)

    registry: dict[str, dict] = {}
    for source_doc, entry in sorted(grouped.items()):
        titles = sorted(set(entry["note_titles"]))
        registry[source_doc] = {
            "source_doc": source_doc,
            "date": entry["date"],
            "note_count": len(titles),
            "note_titles": titles,
        }

    return registry


def main() -> None:
    config = load_config(strict=True)
    vault_path = Path(config["vault"]["vault_path"])
    registry = rebuild_registry(vault_path)
    data = json.dumps(registry, ensure_ascii=False, indent=2)
    fd, tmp_path = tempfile.mkstemp(
        dir=REGISTRY_PATH.parent, suffix=".tmp", prefix=REGISTRY_PATH.stem
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp_path, REGISTRY_PATH)
    except BaseException:
        Path(tmp_path).unlink(missing_ok=True)
        raise
    print(f"Rebuilt {REGISTRY_PATH} from vault: {len(registry)} source_doc entries")


if __name__ == "__main__":
    main()
