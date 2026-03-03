"""atomize.py — Orchestrate Claude to convert parsed .docx JSON into atom plan JSON.

Usage:
    python3 scripts/atomize.py <parsed.json> [-o atom-plan.json] [--dry-run]
"""

import json
import yaml
import sys
import argparse
import re
from pathlib import Path
from datetime import date

try:
    from scripts.config import PROJECT_ROOT, load_config
    from scripts.rewrite_backend import call_rewriter
except ModuleNotFoundError:
    from config import PROJECT_ROOT, load_config
    from rewrite_backend import call_rewriter

REQUIRED_ATOM_FIELDS = {
    "id",
    "title",
    "note_type",
    "tags",
    "source_doc",
    "date",
    "body",
}
# Fields that get a default value if missing (e.g. truncated response)
OPTIONAL_ATOM_FIELDS_DEFAULTS = {
    "proposed_new_tags": [],
}
VALID_NOTE_TYPES = {"atomic", "moc", "source"}


# ── File loaders ───────────────────────────────────────────────────────────────


def load_tags(tags_path: Path | None = None) -> list[str]:
    """Load tags.yaml and flatten to sorted list of 'domain/subtag' strings."""
    if tags_path is None:
        tags_path = PROJECT_ROOT / "tags.yaml"
    with open(tags_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    tags: list[str] = []
    for domain, subtags in data.get("tags", {}).items():
        for subtag in subtags:
            tags.append(f"{domain}/{subtag}")
    return sorted(tags)


def load_skill_md() -> str:
    """Read SKILL.md from project root."""
    skill_path = PROJECT_ROOT / "SKILL.md"
    return skill_path.read_text(encoding="utf-8")


def load_rules() -> tuple[str, str]:
    """Read rules/atomization.md and rules/taxonomy.md."""
    atomization_path = PROJECT_ROOT / "rules" / "atomization.md"
    taxonomy_path = PROJECT_ROOT / "rules" / "taxonomy.md"
    atomization_text = atomization_path.read_text(encoding="utf-8")
    taxonomy_text = taxonomy_path.read_text(encoding="utf-8")
    return atomization_text, taxonomy_text


# ── Prompt assembly ────────────────────────────────────────────────────────────


def assemble_prompt(
    parsed_json: dict,
    tags: list[str],
    skill_md: str,
    atomization_rules: str,
    taxonomy_rules: str,
) -> str:
    """Build the complete prompt for Claude."""
    lines: list[str] = []

    # SKILL.md content (master instructions)
    lines.append(skill_md)

    # Atomization rules
    lines.append("---")
    lines.append("## Atomization Rules")
    lines.append("")
    lines.append(atomization_rules)

    # Taxonomy rules
    lines.append("---")
    lines.append("## Taxonomy Rules")
    lines.append("")
    lines.append(taxonomy_rules)

    # Canonical tag list
    lines.append("---")
    lines.append("## Available Tags (from tags.yaml)")
    lines.append("")
    for tag in tags:
        lines.append(f"- {tag}")

    # Document to process
    lines.append("")
    lines.append("---")
    lines.append("## Document to Process")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(parsed_json, ensure_ascii=False, indent=2))
    lines.append("```")

    # Final instruction
    lines.append("")
    lines.append(
        "Produce the complete atom plan JSON now. Output ONLY the JSON, no prose."
    )

    return "\n".join(lines)


# ── Rewrite backend invocation ────────────────────────────────────────────────


def _repair_truncated_json(text: str) -> dict | None:
    """Attempt to close unclosed JSON structures and parse.

    Returns parsed dict on success, None on failure.
    """
    # Strip trailing comma or incomplete tokens
    repaired = text.rstrip()
    # Remove trailing comma
    while repaired and repaired[-1] in (",", ":", " ", "\n", "\r", "\t"):
        repaired = repaired[:-1]

    # Close open brackets/braces
    stack: list[str] = []
    in_str = False
    escape = False
    for ch in repaired:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch in ("{", "["):
            stack.append("}" if ch == "{" else "]")
        elif ch in ("}", "]"):
            if stack:
                stack.pop()

    # Close unterminated string
    if in_str:
        repaired += '"'

    # Append closing chars in reverse order
    repaired += "".join(reversed(stack))

    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        return None


# ── JSON extraction ────────────────────────────────────────────────────────────


def extract_json(response: str) -> dict:
    """Strip markdown code fences from Claude's JSON response, then parse."""
    text = response.strip()

    if "```json" in text:
        # Extract content between ```json and the next ```
        match = re.search(r"```json\s*([\s\S]*?)\s*```", text)
        if match:
            text = match.group(1).strip()
    elif "```" in text:
        # Extract content between first ``` and next ```
        match = re.search(r"```\s*([\s\S]*?)\s*```", text)
        if match:
            text = match.group(1).strip()
    # else: use response as-is

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        # Attempt structural repair before giving up
        repaired = _repair_truncated_json(text)
        if repaired is not None:
            print(
                "WARNING: JSON was malformed; auto-repaired truncated structure.",
                file=sys.stderr,
            )
            return repaired
        raise ValueError(
            f"Failed to parse JSON from Claude response: {e}\n"
            f"Snippet: {text[:200]!r}"
        ) from e


# ── Validation ─────────────────────────────────────────────────────────────────


def validate_atom_plan(plan: dict) -> list[str]:
    """Validate the atom plan structure. Returns list of error strings."""
    errors: list[str] = []

    if "notes" not in plan:
        errors.append("Atom plan missing required 'notes' key")
        return errors  # can't continue without notes

    notes = plan["notes"]
    seen_ids: set[str] = set()
    moc_count = 0

    for i, note in enumerate(notes):
        note_id = note.get("id", f"<note[{i}]>")

        # Check required fields
        missing = REQUIRED_ATOM_FIELDS - set(note.keys())
        if missing:
            errors.append(
                f"Note '{note_id}' missing fields: {sorted(missing)}"
            )

        # Check note_type validity
        note_type = note.get("note_type")
        if note_type not in VALID_NOTE_TYPES:
            errors.append(
                f"Note '{note_id}' has invalid note_type '{note_type}'; "
                f"must be one of {sorted(VALID_NOTE_TYPES)}"
            )

        # Check tag count
        tags = note.get("tags", [])
        if not (2 <= len(tags) <= 5):
            errors.append(
                f"Note '{note_id}' has {len(tags)} tags; must be 2–5"
            )

        # Count MOCs
        if note_type == "moc":
            moc_count += 1

        # Check ID uniqueness
        if note_id in seen_ids:
            errors.append(f"Duplicate note id: '{note_id}'")
        seen_ids.add(note_id)

    # Exactly 1 MOC required
    if moc_count != 1:
        errors.append(
            f"Expected exactly 1 MOC note (note_type='moc'), found {moc_count}"
        )

    return errors


def validate_tags(plan: dict, valid_tags: set[str]) -> list[str]:
    """Identify non-canonical tags used in notes. Returns warning strings."""
    warnings: list[str] = []

    for note in plan.get("notes", []):
        note_id = note.get("id", "<unknown>")
        for tag in note.get("tags", []):
            if tag not in valid_tags:
                warnings.append(
                    f"Note '{note_id}' uses non-canonical tag '{tag}' "
                    f"(not in tags.yaml)"
                )
    return warnings


def validate_wikilinks(plan: dict) -> list[str]:
    """Check that all [[wikilinks]] in note bodies reference existing note titles."""
    errors: list[str] = []

    # Collect all note titles
    all_titles: set[str] = {
        note.get("title", "") for note in plan.get("notes", [])
    }

    wikilink_pattern = re.compile(r"\[\[([^\]]+)\]\]")

    for note in plan.get("notes", []):
        note_id = note.get("id", "<unknown>")
        body = note.get("body", "")
        for match in wikilink_pattern.finditer(body):
            target = match.group(1).strip()
            if target not in all_titles:
                errors.append(
                    f"Note '{note_id}' contains orphaned wikilink [[{target}]] "
                    f"— no note with that title exists in the plan"
                )
    return errors


# ── Output ─────────────────────────────────────────────────────────────────────


def write_proposed_tags(
    plan: dict,
    staging_dir: Path,
    source_file: str,
) -> None:
    """Write proposed-tags.md to staging_dir. Always creates the file."""
    staging_dir.mkdir(parents=True, exist_ok=True)
    proposed_tags_path = staging_dir / "proposed-tags.md"

    header = (
        "# Proposed New Tags\n\n"
        "Tags proposed by Claude not in tags.yaml. Review and add if appropriate.\n"
    )

    # Initialise file if it does not exist
    if not proposed_tags_path.exists():
        proposed_tags_path.write_text(header, encoding="utf-8")

    # Collect all proposed tags: top-level + per-note
    collected: list[dict] = list(plan.get("proposed_tags", []))
    for note in plan.get("notes", []):
        for entry in note.get("proposed_new_tags", []):
            if entry not in collected:
                collected.append(entry)

    if not collected:
        return  # file already created with header; nothing more to write

    # Append a dated section
    today = date.today().isoformat()
    lines: list[str] = [
        f"\n## {today} — {source_file}\n",
    ]
    for entry in collected:
        tag = entry.get("tag", "<unknown>")
        reason = entry.get("reason", "")
        lines.append(f"- `{tag}`: {reason}")

    with open(proposed_tags_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ── Main ───────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Convert parsed .docx JSON into an atom plan JSON using the active rewrite backend."
        )
    )
    parser.add_argument("input", help="Path to parsed JSON file from parse_docx.py")
    parser.add_argument(
        "-o",
        "--output",
        help="Output atom plan JSON path (default: <staging_dir>/<stem>-atom-plan.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print assembled prompt to stdout and exit without running the rewrite backend",
    )
    parser.add_argument(
        "--backend",
        choices=("auto", "claude", "codex"),
        default="auto",
        help="Rewrite backend to use (default: auto-detect from the current agent environment)",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=300,
        help="Timeout for each rewrite backend call (default: 300)",
    )
    args = parser.parse_args()

    # Load parsed JSON input
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    parsed_json = json.loads(input_path.read_text(encoding="utf-8"))

    # Load config and derive staging dir
    config = load_config()
    staging_dir = Path(config.get("rclone", {}).get("staging_dir", "/tmp/dw/staging"))

    # Load supporting artifacts
    tags = load_tags()
    skill_md = load_skill_md()
    atomization_rules, taxonomy_rules = load_rules()

    # Assemble prompt
    prompt = assemble_prompt(parsed_json, tags, skill_md, atomization_rules, taxonomy_rules)

    # Dry-run: print prompt and exit
    if args.dry_run:
        print(prompt)
        sys.exit(0)

    # Call rewrite backend
    print("Calling rewrite backend...", file=sys.stderr)
    try:
        resolved_backend, raw_response = call_rewriter(
            prompt,
            backend=args.backend,
            timeout_seconds=args.timeout_seconds,
            project_root=PROJECT_ROOT,
        )
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Rewrite backend: {resolved_backend}", file=sys.stderr)

    # Extract JSON from response
    try:
        atom_plan = extract_json(raw_response)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Backfill optional fields with defaults (handles truncated responses)
    for note in atom_plan.get("notes", []):
        for field, default in OPTIONAL_ATOM_FIELDS_DEFAULTS.items():
            if field not in note:
                note[field] = default

    # Validate atom plan structure (hard errors → exit 1)
    validation_errors = validate_atom_plan(atom_plan)
    if validation_errors:
        print("ERROR: Atom plan validation failed:", file=sys.stderr)
        for err in validation_errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    # Validate tags (warnings only)
    valid_tags_set = set(tags)
    tag_warnings = validate_tags(atom_plan, valid_tags_set)
    for warn in tag_warnings:
        print(f"WARNING: {warn}", file=sys.stderr)

    # Validate wikilinks (warnings only)
    wikilink_warnings = validate_wikilinks(atom_plan)
    for warn in wikilink_warnings:
        print(f"WARNING: {warn}", file=sys.stderr)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        stem = input_path.stem
        output_path = staging_dir / f"{stem}-atom-plan.json"

    # Write atom plan JSON
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(atom_plan, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Write proposed-tags.md to staging
    source_file = parsed_json.get("source_file", input_path.name)
    write_proposed_tags(atom_plan, staging_dir, source_file)

    # Print output path to stdout (for piping to Phase 3)
    print(str(output_path))

    # Print summary to stderr
    notes = atom_plan.get("notes", [])
    atomic_count = sum(1 for n in notes if n.get("note_type") == "atomic")
    proposed_count = len(
        [
            t
            for t in atom_plan.get("proposed_tags", [])
        ]
    )
    print(
        f"Atom plan: {atomic_count} atomic notes + 1 MOC, "
        f"{proposed_count} proposed new tags",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
