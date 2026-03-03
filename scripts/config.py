"""config.py — Shared configuration loader for ObsidianDataWeave scripts.

Single source of truth for:
- tomllib import (stdlib 3.11+ / tomli fallback)
- PROJECT_ROOT path
- STAGING_DIR default
- REGISTRY_PATH
- load_config() with soft/strict modes
"""

import sys
from pathlib import Path

# ── tomllib import ────────────────────────────────────────────────────────────

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

# ── Path constants ────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_STAGING_DIR = "/tmp/dw/staging"
REGISTRY_PATH = PROJECT_ROOT / "processed.json"

# ── Config loader ─────────────────────────────────────────────────────────────


def load_config(*, strict: bool = False) -> dict:
    """Read config.toml via tomllib.

    Args:
        strict: If True, missing config or tomllib is a hard error (sys.exit(1)).
                If False, returns defaults with a warning.

    Returns:
        Parsed config dict.
    """
    config_path = PROJECT_ROOT / "config.toml"

    if not config_path.exists():
        if strict:
            print(
                "ERROR: config.toml not found. Copy config.example.toml to "
                "config.toml and fill in your vault path.",
                file=sys.stderr,
            )
            sys.exit(1)
        print(
            f"WARNING: config.toml not found; using default staging_dir={DEFAULT_STAGING_DIR}",
            file=sys.stderr,
        )
        return {"rclone": {"staging_dir": DEFAULT_STAGING_DIR}}

    if tomllib is None:
        if strict:
            print(
                "ERROR: tomllib/tomli not available. Cannot parse config.toml. "
                "Upgrade to Python 3.11+ or: pip install tomli",
                file=sys.stderr,
            )
            sys.exit(1)
        print(
            "WARNING: tomllib/tomli not available; using default config. "
            "Upgrade to Python 3.11+ or: pip install tomli",
            file=sys.stderr,
        )
        return {"rclone": {"staging_dir": DEFAULT_STAGING_DIR}}

    with open(config_path, "rb") as f:
        return tomllib.load(f)
