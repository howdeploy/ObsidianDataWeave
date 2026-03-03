"""process_note.py — Process a personal Obsidian note: enrich or atomize.

Usage:
    python3 scripts/process_note.py "Note Title"
    python3 scripts/process_note.py "Note.md" --mode enrich
    python3 scripts/process_note.py "Note.md" --mode atomize
    python3 scripts/process_note.py "Note.md" --dry-run
    python3 scripts/process_note.py "Note.md" --mode atomize --non-interactive --on-conflict skip

Flow:
    1. Find note in vault (by title, filename, or absolute path)
    2. Read body + existing frontmatter
    3. Scan vault for existing titles (for wikilink resolution)
    4. Auto-detect mode (enrich/atomize) if not specified
    5. Assemble prompt (SKILL_PERSONAL.md + rules + tags + vault_titles + body)
    6. Call the active rewrite backend
    7. Validate response
    8. Write results to vault
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

try:
    from scripts.config import PROJECT_ROOT, load_config as load_config_strict
    from scripts.atomize import (
        extract_json, load_tags,
        validate_atom_plan, validate_tags, write_proposed_tags,
    )
    from scripts.rewrite_backend import call_rewriter
    from scripts.generate_notes import render_note_md, sanitize_filename
    from scripts.scan_vault import scan_vault
    from scripts.vault_writer import (
        get_vault_dest, load_registry, parse_frontmatter, save_registry,
    )
except ModuleNotFoundError:
    from config import PROJECT_ROOT, load_config as load_config_strict
    from atomize import (
        extract_json, load_tags,
        validate_atom_plan, validate_tags, write_proposed_tags,
    )
    from rewrite_backend import call_rewriter
    from generate_notes import render_note_md, sanitize_filename
    from scan_vault import scan_vault
    from vault_writer import (
        get_vault_dest, load_registry, parse_frontmatter, save_registry,
    )

SCRIPTS_DIR = Path(__file__).parent


def load_skill_personal_md() -> str:
    """Read SKILL_PERSONAL.md from project root."""
    path = PROJECT_ROOT / "SKILL_PERSONAL.md"
    return path.read_text(encoding="utf-8")


def load_rules() -> tuple[str, str, str]:
    """Read all three rule files."""
    atomization = (PROJECT_ROOT / "rules" / "atomization.md").read_text(encoding="utf-8")
    taxonomy = (PROJECT_ROOT / "rules" / "taxonomy.md").read_text(encoding="utf-8")
    personal = (PROJECT_ROOT / "rules" / "personal_notes.md").read_text(encoding="utf-8")
    return atomization, taxonomy, personal


# ── Note finding ──────────────────────────────────────────────────────────────


def find_note(query: str, config: dict) -> Path | None:
    """Find a note in the vault by title, filename, or absolute path.

    Search order:
    1. Absolute path (if query is an existing file path)
    2. Vault root
    3. notes_folder
    4. moc_folder
    5. Recursive search by stem match
    """
    # Absolute path
    query_path = Path(query)
    if query_path.is_absolute() and query_path.exists():
        return query_path

    vault_path = Path(config["vault"]["vault_path"])
    notes_folder = vault_path / config["vault"].get("notes_folder", "Notes")
    moc_folder = vault_path / config["vault"].get("moc_folder", "MOCs")

    # Normalize: add .md if missing
    filename = query if query.endswith(".md") else f"{query}.md"

    # Check specific locations first
    for folder in [vault_path, notes_folder, moc_folder]:
        candidate = folder / filename
        if candidate.exists():
            return candidate

    # Recursive search by stem
    stem = query.removesuffix(".md")
    for md_file in vault_path.rglob("*.md"):
        # Skip hidden/system dirs
        rel_parts = md_file.relative_to(vault_path).parts
        if any(part.startswith(".") for part in rel_parts):
            continue
        if md_file.stem == stem:
            return md_file

    return None


# ── Frontmatter extraction ────────────────────────────────────────────────────


def split_frontmatter_and_body(content: str) -> tuple[dict | None, str]:
    """Split .md content into frontmatter dict and body string.

    Returns (None, full_content) if no frontmatter found.
    """
    if not content.startswith("---"):
        return None, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return None, content

    fm = parse_frontmatter(content)
    body = parts[2].strip()
    return (fm if fm else None), body


# ── Mode detection ────────────────────────────────────────────────────────────


def detect_mode(body: str, frontmatter: dict | None) -> str | None:
    """Auto-detect processing mode based on content analysis.

    Returns: 'enrich', 'atomize', or None (skip — already processed).
    """
    words = body.split()
    word_count = len(words)

    # Already processed check
    if frontmatter:
        has_source_doc = "source_doc" in frontmatter
        has_note_type = "note_type" in frontmatter
        if has_source_doc and has_note_type:
            return None  # skip

    # Empty note
    if word_count < 20:
        print(
            f"ERROR: Note too short ({word_count} words, minimum 20).",
            file=sys.stderr,
        )
        sys.exit(1)

    # Long notes → atomize
    if word_count > 600:
        return "atomize"

    # Multi-topic detection: 3+ paragraphs with > 300 words
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    if len(paragraphs) >= 3 and word_count > 300:
        return "atomize"

    return "enrich"


# ── Prompt assembly ───────────────────────────────────────────────────────────


def assemble_prompt(
    note_input: dict,
    tags: list[str],
    skill_md: str,
    atomization_rules: str,
    taxonomy_rules: str,
    personal_rules: str,
) -> str:
    """Build the complete prompt for the rewrite backend."""
    lines: list[str] = []

    # SKILL_PERSONAL.md content
    lines.append(skill_md)

    # Rules
    lines.append("---")
    lines.append("## Atomization Rules")
    lines.append("")
    lines.append(atomization_rules)

    lines.append("---")
    lines.append("## Taxonomy Rules")
    lines.append("")
    lines.append(taxonomy_rules)

    lines.append("---")
    lines.append("## Personal Notes Rules")
    lines.append("")
    lines.append(personal_rules)

    # Canonical tag list
    lines.append("---")
    lines.append("## Available Tags (from tags.yaml)")
    lines.append("")
    for tag in tags:
        lines.append(f"- {tag}")

    # Note to process
    lines.append("")
    lines.append("---")
    lines.append("## Note to Process")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(note_input, ensure_ascii=False, indent=2))
    lines.append("```")

    # Final instruction
    lines.append("")
    lines.append(
        "Process this personal note now. Output ONLY the JSON, no prose."
    )

    return "\n".join(lines)


# ── Validation ────────────────────────────────────────────────────────────────


def validate_enrich_result(result: dict, vault_titles: set[str]) -> list[str]:
    """Validate enrich mode output."""
    errors: list[str] = []

    if "note" not in result:
        errors.append("Enrich result missing 'note' key")
        return errors

    note = result["note"]

    # Required fields
    required = {"title", "tags", "source_doc", "date", "note_type", "body"}
    missing = required - set(note.keys())
    if missing:
        errors.append(f"Note missing fields: {sorted(missing)}")

    # Tag count
    tags = note.get("tags", [])
    if not (2 <= len(tags) <= 5):
        errors.append(f"Note has {len(tags)} tags; must be 2–5")

    # source_doc must be "Личная заметка"
    if note.get("source_doc") != "Личная заметка":
        errors.append(
            f"source_doc must be 'Личная заметка', got '{note.get('source_doc')}'"
        )

    # Validate wikilinks point to vault titles
    wikilink_re = re.compile(r"\[\[([^\]]+)\]\]")
    body = note.get("body", "")
    for match in wikilink_re.finditer(body):
        target = match.group(1).strip()
        if target not in vault_titles:
            errors.append(f"Wikilink [[{target}]] not found in vault titles")

    return errors


def validate_atomize_result(result: dict, vault_titles: set[str]) -> list[str]:
    """Validate atomize mode output. Extends standard atom plan validation."""
    # Use standard validator first
    errors = validate_atom_plan(result)

    # Check wikilinks against both vault titles and plan titles
    plan_titles: set[str] = {
        note.get("title", "") for note in result.get("notes", [])
    }
    all_valid_targets = vault_titles | plan_titles

    wikilink_re = re.compile(r"\[\[([^\]]+)\]\]")
    for note in result.get("notes", []):
        note_id = note.get("id", "<unknown>")
        body = note.get("body", "")
        for match in wikilink_re.finditer(body):
            target = match.group(1).strip()
            if target not in all_valid_targets:
                errors.append(
                    f"Note '{note_id}': wikilink [[{target}]] not found in "
                    f"vault titles or plan titles"
                )

    # Check source_doc
    for note in result.get("notes", []):
        if note.get("source_doc") != "Личная заметка":
            errors.append(
                f"Note '{note.get('id')}': source_doc must be 'Личная заметка'"
            )

    # Check title collisions with vault
    for note in result.get("notes", []):
        title = note.get("title", "")
        note_type = note.get("note_type", "")
        if note_type != "moc" and title in vault_titles:
            errors.append(
                f"Note '{note.get('id')}': title '{title}' collides with "
                f"existing vault note"
            )

    return errors


# ── Result writing ────────────────────────────────────────────────────────────


def archive_original(note_path: Path, vault_path: Path) -> None:
    """Move original note to .archive/ in vault root."""
    archive_dir = vault_path / ".archive"
    archive_dir.mkdir(exist_ok=True)

    today = date.today().isoformat()
    archive_name = f"{today}_{note_path.stem}.md"
    dest = archive_dir / archive_name

    # Handle name collision in archive
    counter = 1
    while dest.exists():
        archive_name = f"{today}_{note_path.stem}_{counter}.md"
        dest = archive_dir / archive_name
        counter += 1

    shutil.move(str(note_path), str(dest))
    print(f"  Archived original: {dest.name}", file=sys.stderr)


def write_enrich_result(
    result: dict,
    original_path: Path,
    config: dict,
) -> None:
    """Write enriched note back to vault."""
    note = result["note"]
    title = note["title"]
    original_title = note.get("original_title", title)
    vault_path = Path(config["vault"]["vault_path"])
    notes_folder = vault_path / config["vault"].get("notes_folder", "Notes")

    # Render the note content
    content = render_note_md(note)

    if title == original_title:
        # Title unchanged: overwrite in place
        original_path.write_text(content, encoding="utf-8")
        print(f"  Updated in place: {original_path.name}", file=sys.stderr)
    else:
        # Title changed: new file in notes_folder, archive original
        new_filename = sanitize_filename(title) + ".md"
        notes_folder.mkdir(parents=True, exist_ok=True)
        dest = notes_folder / new_filename
        dest.write_text(content, encoding="utf-8")
        print(f"  Created: {dest.name}", file=sys.stderr)
        archive_original(original_path, vault_path)

    # Update registry
    registry = load_registry()
    source_key = "Личная заметка"
    existing = registry.get(source_key, {
        "source_doc": source_key,
        "date": date.today().isoformat(),
        "note_count": 0,
        "note_titles": [],
    })
    titles_set = set(existing.get("note_titles", []))
    titles_set.add(title)
    existing["note_titles"] = sorted(titles_set)
    existing["note_count"] = len(existing["note_titles"])
    registry[source_key] = existing
    save_registry(registry)
    print("  Registry updated: processed.json", file=sys.stderr)


def write_atomize_result(
    result: dict,
    original_path: Path,
    config: dict,
    *,
    non_interactive: bool = False,
    on_conflict: str = "skip",
) -> None:
    """Write atomized notes to vault via staging → generate → vault_writer flow."""
    staging_root = Path(config.get("rclone", {}).get("staging_dir", "/tmp/dw/staging"))
    staging_root.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(prefix="personal-", dir=staging_root))

    # Write atom plan to staging
    plan_path = staging_dir / "personal-atom-plan.json"
    plan_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Generate .md files from atom plan
    notes = result.get("notes", [])
    for note in notes:
        title = note.get("title", "untitled")
        filename = sanitize_filename(title) + ".md"
        content = render_note_md(note)
        (staging_dir / filename).write_text(content, encoding="utf-8")

    atomic_count = sum(1 for n in notes if n.get("note_type") == "atomic")
    moc_count = sum(1 for n in notes if n.get("note_type") == "moc")
    print(
        f"  Generated {len(notes)} .md files ({atomic_count} atomic + {moc_count} MOC)",
        file=sys.stderr,
    )

    # Write proposed tags
    source_file = result.get("source_file", "personal")
    write_proposed_tags(result, staging_dir, source_file)

    # Use vault_writer.py subprocess for actual vault writing (handles dedup, routing)
    vault_writer_py = str(SCRIPTS_DIR / "vault_writer.py")
    vw_cmd = [
        sys.executable, vault_writer_py,
        "--staging", str(staging_dir),
        "--atom-plan", str(plan_path),
    ]
    if non_interactive:
        vw_cmd.extend(["--non-interactive", "--on-conflict", on_conflict])

    vw_result = subprocess.run(
        vw_cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if vw_result.stderr:
        print(vw_result.stderr, end="", file=sys.stderr)
    if vw_result.returncode != 0:
        print("ERROR: vault_writer.py failed.", file=sys.stderr)
        sys.exit(1)
    if vw_result.stdout:
        print(f"  {vw_result.stdout.strip()}", file=sys.stderr)

    # Archive original
    vault_path = Path(config["vault"]["vault_path"])
    archive_original(original_path, vault_path)


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process a personal Obsidian note: enrich or atomize."
    )
    parser.add_argument(
        "input",
        help="Note title, filename (with or without .md), or absolute path",
    )
    parser.add_argument(
        "--mode",
        choices=["enrich", "atomize"],
        help="Processing mode (default: auto-detect based on content)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print assembled prompt to stdout and exit without running the semantic rewrite step",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Disable prompts during vault writes and use the policy from --on-conflict",
    )
    parser.add_argument(
        "--on-conflict",
        choices=("skip", "overwrite"),
        default="skip",
        help="Duplicate note policy for atomize writes in non-interactive mode (default: skip)",
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

    # Load config
    config = load_config_strict()
    vault_path = Path(config["vault"]["vault_path"])

    # Step 1: Find the note
    print(f">> Finding note: {args.input}", file=sys.stderr)
    note_path = find_note(args.input, config)
    if note_path is None:
        print(f"ERROR: Note not found: '{args.input}'", file=sys.stderr)
        print(
            f"  Searched: vault root, "
            f"{config['vault'].get('notes_folder', 'Notes')}, "
            f"{config['vault'].get('moc_folder', 'MOCs')}, "
            f"recursive by stem",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"  Found: {note_path}", file=sys.stderr)

    # Step 2: Read content
    content = note_path.read_text(encoding="utf-8")
    frontmatter, body = split_frontmatter_and_body(content)

    word_count = len(body.split())
    print(f"  Word count: {word_count}", file=sys.stderr)

    # Step 3: Scan vault
    print(">> Scanning vault for existing titles...", file=sys.stderr)
    exclude = {note_path.name}
    vault_data = scan_vault(vault_path, exclude=exclude)
    vault_titles = vault_data["titles"]
    print(f"  Found {len(vault_titles)} existing notes", file=sys.stderr)

    # Step 4: Detect mode
    if args.mode:
        mode = args.mode
        print(f">> Mode (user-specified): {mode}", file=sys.stderr)
    else:
        mode = detect_mode(body, frontmatter)
        if mode is None:
            print(
                "SKIP: Note appears already processed "
                "(has source_doc and note_type in frontmatter). "
                "Use --mode to force reprocessing.",
                file=sys.stderr,
            )
            sys.exit(0)
        print(f">> Mode (auto-detected): {mode}", file=sys.stderr)

    # Step 5: Assemble prompt
    tags = load_tags()
    skill_md = load_skill_personal_md()
    atomization_rules, taxonomy_rules, personal_rules = load_rules()

    note_input = {
        "source_file": note_path.name,
        "mode": mode,
        "body": body,
        "existing_frontmatter": frontmatter,
        "vault_titles": vault_titles,
        "word_count": word_count,
    }

    prompt = assemble_prompt(
        note_input, tags, skill_md,
        atomization_rules, taxonomy_rules, personal_rules,
    )

    # Dry-run: print prompt and exit
    if args.dry_run:
        print(prompt)
        sys.exit(0)

    # Step 6: Call rewrite backend
    print(">> Calling rewrite backend...", file=sys.stderr)
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
    print(f"  Rewrite backend: {resolved_backend}", file=sys.stderr)

    # Step 7: Extract and validate
    try:
        result = extract_json(raw_response)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    vault_titles_set = set(vault_titles)
    valid_tags_set = set(tags)

    if mode == "enrich":
        errors = validate_enrich_result(result, vault_titles_set)
    else:
        errors = validate_atomize_result(result, vault_titles_set)

    if errors:
        print("ERROR: Validation failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        # Write raw response for debugging
        debug_path = Path("/tmp/dw/debug-response.json")
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        debug_path.write_text(raw_response, encoding="utf-8")
        print(f"  Raw response saved to: {debug_path}", file=sys.stderr)
        sys.exit(1)

    # Tag warnings (non-fatal)
    if mode == "enrich":
        note_for_tags = {"notes": [result["note"]]}
    else:
        note_for_tags = result
    tag_warnings = validate_tags(note_for_tags, valid_tags_set)
    for warn in tag_warnings:
        print(f"WARNING: {warn}", file=sys.stderr)

    # Step 8: Write results
    print(f">> Writing results ({mode} mode)...", file=sys.stderr)

    if mode == "enrich":
        write_enrich_result(result, note_path, config)
    else:
        write_atomize_result(
            result,
            note_path,
            config,
            non_interactive=args.non_interactive,
            on_conflict=args.on_conflict,
        )

    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
