"""process.py — Full pipeline wrapper: fetch -> parse -> atomize -> generate -> write.

Usage:
    # Full pipeline (fetches from Google Drive):
    python3 scripts/process.py "Research.docx"

    # Skip fetch (docx already in staging):
    python3 scripts/process.py "Research.docx" --skip-fetch

    # Start from atom plan JSON (skip fetch/parse/atomize):
    python3 scripts/process.py /path/to/atom-plan.json --from-plan

Stdout from each step is piped as input to the next step.
Stderr from each step is passed through (diagnostics visible to user).
"""

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = Path(__file__).parent


# ── Subprocess runner ────────────────────────────────────────────────────────────


def run(cmd: list[str], desc: str) -> str:
    """Run a subprocess, pass stderr through, and return stripped stdout.

    On non-zero exit: prints a descriptive error and raises SystemExit.
    """
    print(f">> {desc}", file=sys.stderr)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    # Always pass subprocess stderr through to the user
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)

    if result.returncode != 0:
        print(
            f"ERROR: Step '{desc}' failed with exit code {result.returncode}.",
            file=sys.stderr,
        )
        if result.stdout:
            print(f"stdout: {result.stdout}", file=sys.stderr)
        raise SystemExit(result.returncode)

    return result.stdout.strip()


# ── Main ────────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Full ObsidianDataWeave pipeline: "
            "fetch_docx.sh -> parse_docx.py -> atomize.py -> generate_notes.py -> vault_writer.py"
        )
    )
    parser.add_argument(
        "input",
        help=(
            "Google Drive filename (e.g. 'Research.docx') for the full pipeline, "
            "or path to an atom plan JSON file when using --from-plan"
        ),
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Skip the fetch step; expect the .docx already present in staging",
    )
    parser.add_argument(
        "--from-plan",
        action="store_true",
        help=(
            "Input is an atom plan JSON path; "
            "skip fetch/parse/atomize and go straight to generate_notes + vault_writer"
        ),
    )
    args = parser.parse_args()

    fetch_docx_sh = str(SCRIPTS_DIR / "fetch_docx.sh")
    parse_docx_py = str(SCRIPTS_DIR / "parse_docx.py")
    atomize_py = str(SCRIPTS_DIR / "atomize.py")
    generate_notes_py = str(SCRIPTS_DIR / "generate_notes.py")
    vault_writer_py = str(SCRIPTS_DIR / "vault_writer.py")

    if args.from_plan:
        # ── Short-circuit: input is an atom plan JSON path ──────────────────────
        atom_plan_path = args.input

        # Step 4: generate_notes.py
        staging_dir = run(
            [sys.executable, generate_notes_py, atom_plan_path],
            desc=f"generate_notes: atom plan -> staging .md files",
        )

        # Step 5: vault_writer.py
        summary = run(
            [
                sys.executable, vault_writer_py,
                "--staging", staging_dir,
                "--atom-plan", atom_plan_path,
            ],
            desc="vault_writer: staging -> vault",
        )
        print(summary)
        return

    # ── Full pipeline ────────────────────────────────────────────────────────────

    docx_filename = args.input

    if args.skip_fetch:
        # Derive .docx path from config staging_dir (best effort; user must have fetched it)
        # We still need a path — tell vault_writer where to find it.
        # Use generate_notes to discover staging dir from config.
        # Actually: we need the docx path. It should be in staging_dir/<docx_filename>.
        # Build a placeholder path here; parse_docx.py will error if it doesn't exist.
        from pathlib import Path as P

        # Try to derive staging_dir from config.toml
        try:
            import tomllib  # noqa: F401 — already imported at top, but try here too
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore
            except ImportError:
                tomllib = None  # type: ignore

        staging_dir_guess = "/tmp/dw/staging"
        config_path = PROJECT_ROOT / "config.toml"
        if config_path.exists() and tomllib is not None:
            with open(config_path, "rb") as f:
                cfg = tomllib.load(f)
            staging_dir_guess = cfg.get("rclone", {}).get("staging_dir", staging_dir_guess)

        docx_path = str(P(staging_dir_guess) / docx_filename)
        print(
            f"  [skip-fetch] Expecting .docx at: {docx_path}",
            file=sys.stderr,
        )
    else:
        # Step 1: fetch_docx.sh
        docx_path = run(
            ["bash", fetch_docx_sh, docx_filename],
            desc=f"fetch_docx: download '{docx_filename}' from Google Drive",
        )

    # Step 2: parse_docx.py
    # Output path: same directory as .docx, stem + '-parsed.json'
    docx_path_obj = Path(docx_path)
    parsed_json_path = str(docx_path_obj.parent / f"{docx_path_obj.stem}-parsed.json")

    run(
        [sys.executable, parse_docx_py, docx_path, "-o", parsed_json_path],
        desc=f"parse_docx: '{docx_path_obj.name}' -> '{Path(parsed_json_path).name}'",
    )

    # Step 3: atomize.py — emits atom plan path to stdout
    atom_plan_path = run(
        [sys.executable, atomize_py, parsed_json_path],
        desc="atomize: parsed JSON -> atom plan (calls Claude)",
    )

    # Step 4: generate_notes.py — emits staging dir to stdout
    staging_dir = run(
        [sys.executable, generate_notes_py, atom_plan_path],
        desc="generate_notes: atom plan -> staging .md files",
    )

    # Step 5: vault_writer.py — emits summary to stdout
    summary = run(
        [
            sys.executable, vault_writer_py,
            "--staging", staging_dir,
            "--atom-plan", atom_plan_path,
        ],
        desc="vault_writer: staging -> vault",
    )
    print(summary)


if __name__ == "__main__":
    main()
