"""doctor.py — Validate local setup for ObsidianDataWeave."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

try:
    from scripts.config import PROJECT_ROOT, REGISTRY_PATH, load_config
    from scripts.rebuild_processed import rebuild_registry
except ModuleNotFoundError:
    from config import PROJECT_ROOT, REGISTRY_PATH, load_config
    from rebuild_processed import rebuild_registry


def check_path(label: str, path: Path, *, must_exist: bool = True) -> bool:
    """Print a status line for a filesystem path."""
    exists = path.exists()
    status = "OK" if (exists or not must_exist) else "MISSING"
    print(f"{status:<8} {label}: {path}")
    return exists or not must_exist


def check_command(name: str) -> bool:
    """Print a status line for a shell command."""
    resolved = shutil.which(name)
    status = "OK" if resolved else "MISSING"
    location = resolved or "not in PATH"
    print(f"{status:<8} command `{name}`: {location}")
    return resolved is not None


def main() -> None:
    ok = True

    print("ObsidianDataWeave doctor")
    print(f"Project root: {PROJECT_ROOT}")

    ok &= check_path("config.example.toml", PROJECT_ROOT / "config.example.toml")
    ok &= check_path("AGENTS.md", PROJECT_ROOT / "AGENTS.md")
    ok &= check_path("SKILL.md", PROJECT_ROOT / "SKILL.md")
    ok &= check_path("SKILL_PERSONAL.md", PROJECT_ROOT / "SKILL_PERSONAL.md")
    ok &= check_path("rules/atomization.md", PROJECT_ROOT / "rules" / "atomization.md")
    ok &= check_path("rules/taxonomy.md", PROJECT_ROOT / "rules" / "taxonomy.md")
    ok &= check_path("rules/personal_notes.md", PROJECT_ROOT / "rules" / "personal_notes.md")
    ok &= check_path("tags.yaml", PROJECT_ROOT / "tags.yaml")

    config_path = PROJECT_ROOT / "config.toml"
    ok &= check_path("config.toml", config_path)

    if config_path.exists():
        cfg = load_config(strict=True)
        vault_path = Path(cfg["vault"]["vault_path"])
        ok &= check_path("vault_path", vault_path)
        if vault_path.exists():
            rebuilt = rebuild_registry(vault_path)
            if REGISTRY_PATH.exists():
                try:
                    current = REGISTRY_PATH.read_text(encoding="utf-8")
                    current_count = len(__import__("json").loads(current))
                except Exception:
                    current_count = -1
                rebuilt_count = len(rebuilt)
                status = "OK" if current_count == rebuilt_count else "WARN"
                print(
                    f"{status:<8} processed.json coverage: file={current_count} rebuilt={rebuilt_count}",
                )
            else:
                print("WARN     processed.json coverage: file missing, rebuild recommended")

    ok &= check_command("python3")
    ok &= check_command("claude")
    ok &= check_command("codex")
    ok &= check_command("rclone")

    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
