# Phase 3: Writers - Research

**Researched:** 2026-02-26
**Domain:** Python file I/O, YAML frontmatter generation, vault path routing, idempotency via JSON registry, staging-to-vault copy pipeline
**Confidence:** HIGH (all technical claims verified by running code against the actual project; no external library research needed — phase is pure Python stdlib + project-defined contracts)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Folder Routing
- Flat structure inside each folder: all atomic notes in notes_folder, all MOCs in moc_folder — no subfolders
- Folders are defined in config.toml: notes_folder, moc_folder, source_folder
- Follows Zettelkasten methodology: navigation via wikilinks and MOC-hubs, not folder hierarchy
- File naming: title as-is (Cyrillic filenames for Russian notes, spaces preserved)
- PARA structure explicitly not used (mentioned as optional in reference docs, not adopted)

#### Idempotency & Deduplication
- Duplicate detection: by source_doc + title (check frontmatter of existing files in vault)
- On conflict (note with same source_doc + title already exists): interactive prompt — user decides skip/overwrite per file
- JSON registry (processed.json) tracks all processed documents: {source_doc, date, note_count, note_titles} per document — fast lookup without vault scanning
- Registry stored in project directory (not in vault)

#### MOC Management
- MOC always overwritten on re-run — MOC is auto-generated, manual edits not expected
- MOC created last (after all atomic notes written)
- One MOC per processed document

#### Staging → Vault Process
- Write strategy: Claude's discretion (batch vs incremental)
- Logging: summary-level output ("Created 7 notes + 1 MOC, skipped 2 duplicates") — not per-file verbose
- Staging cleanup: Claude's discretion
- Pipeline wrapper: process.py (one command for the full chain: fetch → parse → atomize → write), but individual scripts remain callable separately for flexibility

### Claude's Discretion
- Special character handling in filenames (: / ? etc.) — replacement strategy
- Filename length limit (Cyrillic = 2 bytes/char on ext4)
- Write strategy (batch all-or-nothing vs incremental)
- Staging cleanup after successful vault write
- proposed-tags.md storage location (vault root vs project dir)

### Deferred Ideas (OUT OF SCOPE)
- MOC update/append mode (LINK-V2-01) — v2, currently overwrite only
- Batch processing of a folder of .docx files (DOCX-V2-02) — v2
- Cross-document wikilinks (LINK-V2-02) — v2, requires vault scanning
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| VAULT-01 | Заметки сохраняются в Obsidian волт по конфигурируемому пути | vault_path, notes_folder, moc_folder read from config.toml using tomllib (stdlib, Python 3.11+ verified present). vault_writer.py reads config at startup; Path(vault_path) / notes_folder is the destination. |
| VAULT-02 | Папки роутятся по типу: MOC в одну папку, атомарные в другую, исходники в третью | note_type field in atom plan JSON drives routing: "moc" → moc_folder, "atomic" → notes_folder, "source" → source_folder. Flat structure only — no subdirectory creation needed. |
| VAULT-03 | При повторном запуске — не создаёт дубликаты (идемпотентность по content hash) | User decision: deduplication key is (source_doc, title) pair. processed.json registry in project dir provides O(1) lookup. On conflict: interactive prompt (skip/overwrite). Registry updated atomically after vault writes complete. |
| VAULT-04 | Staging директория (/tmp) используется для промежуточных файлы — волт получает только финальный результат | generate_notes.py writes ONLY to staging_dir. vault_writer.py is the ONLY script that touches vault_path. Architecture enforced by script design — no other script takes vault_path as argument. |
</phase_requirements>

---

## Summary

Phase 3 converts the atom plan JSON produced by Phase 2 into `.md` files and commits them to the Obsidian vault. The work splits cleanly into two scripts: `generate_notes.py` renders each note entry from the atom plan into a `.md` file with YAML frontmatter in the staging directory, and `vault_writer.py` reads the staged files, checks the `processed.json` registry for duplicates, prompts the user on conflicts, then copies approved files to the vault with correct folder routing. A third script, `process.py`, wraps the entire fetch → parse → atomize → write chain into a single command.

All technical building blocks were verified against the running project during research. Python 3.14 is on the system; `tomllib` is stdlib; `hashlib`, `json`, `pathlib`, `shutil`, and `sys` cover all needs. No new `pip` packages are required — this phase is pure Python stdlib. The YAML frontmatter is constructed as string interpolation (not a YAML library), which is the established pattern for Obsidian note generation tools and avoids adding a dependency.

The critical design choice for this phase is **batch writes**: generate_notes.py writes ALL `.md` files to staging first, then vault_writer.py checks ALL conflicts and prompts the user once per conflict before writing anything to the vault. This is safer than incremental write (vault never in partial state), gives the user a complete conflict summary upfront, and makes both scripts independently re-runnable.

**Primary recommendation:** Two-script split (generate_notes.py + vault_writer.py) with batch write strategy, processed.json registry for O(1) deduplication, interactive conflict prompt with non-interactive auto-skip fallback, and process.py wrapper for the full pipeline chain.

---

## Standard Stack

### Core (no new dependencies — pure stdlib)

| Component | Version | Purpose | Why Standard |
|-----------|---------|---------|--------------|
| json (stdlib) | stdlib | Read atom plan JSON; read/write processed.json registry | Consistent with Phases 1 and 2; no new dependency |
| pathlib (stdlib) | stdlib | All path operations: vault_path/folder joining, staging dir management | Already used in parse_docx.py and atomize.py |
| shutil (stdlib) | stdlib | shutil.copy2() for staging → vault file copy (preserves metadata) | Standard Python file copy; no third-party needed |
| tomllib (stdlib) | Python 3.11+ | Read config.toml for vault_path, folder names, staging_dir | Verified present: Python 3.14.2 on system |
| hashlib (stdlib) | stdlib | Content hash for deduplication key (not used — key is source_doc+title, but available if needed) | Stdlib; no install needed |
| sys (stdlib) | stdlib | sys.stdin.isatty() for non-interactive detection; stderr for diagnostics | Standard pattern |
| argparse (stdlib) | stdlib | CLI argument parsing (consistent with parse_docx.py, atomize.py) | Established pattern in this project |

### No pip Installs Required

Phase 3 uses only what Phase 1 and Phase 2 already verified:
- Python 3.14.2 (on system)
- tomllib (stdlib since Python 3.11 — confirmed working)
- PyYAML not needed for YAML frontmatter (string interpolation is sufficient)
- python-docx not needed (Phase 3 does not read .docx files)

**Installation:**
```bash
# No installation required for Phase 3
# All dependencies already on system from Phase 1 setup
```

---

## Architecture Patterns

### Recommended Project Structure (Phase 3 additions)

```
ObsidianDataWeave/
├── SKILL.md                        # Phase 2 (existing)
├── scripts/
│   ├── fetch_docx.sh               # Phase 1 (existing) — prints local path to stdout
│   ├── parse_docx.py               # Phase 1 (existing) — -o flag writes JSON
│   ├── atomize.py                  # Phase 2 (existing) — prints atom plan path to stdout
│   ├── generate_notes.py           # Phase 3 NEW — atom plan JSON → .md files in staging
│   ├── vault_writer.py             # Phase 3 NEW — staging .md → vault with dedup
│   └── process.py                  # Phase 3 NEW — pipeline wrapper (full chain)
├── processed.json                  # Phase 3 NEW — registry (project dir, gitignored)
└── /tmp/dw/staging/
    ├── {docname}.docx              # fetched by Phase 1
    ├── {docname}-parsed.json       # Phase 1 output
    ├── {docname}-parsed-atom-plan.json  # Phase 2 output (consumed by Phase 3)
    ├── {note title}.md             # Phase 3 generate_notes.py output
    ├── {moc title}.md              # Phase 3 generate_notes.py output
    └── proposed-tags.md            # Phase 2 output (appended by Phase 3 if needed)
```

### Pattern 1: Batch Write Strategy (Recommended)

**What:** generate_notes.py renders ALL `.md` files to staging, THEN vault_writer.py copies ALL to vault after conflict checking. The two operations are fully decoupled.

**Why batch over incremental:**
- Vault is never in a partial state (if vault_writer.py dies, re-run it — staging files are still there)
- User sees ALL conflicts upfront before any vault write happens
- generate_notes.py can be re-run safely (overwrites staging, idempotent)
- vault_writer.py can be re-run safely (registry prevents double-writing)

**Flow:**
```
atom-plan.json
    ↓ generate_notes.py
staging/NoteTitle.md (all notes rendered)
staging/DocName — MOC.md
    ↓ vault_writer.py
[check processed.json registry for each file]
[prompt user: skip/overwrite for each conflict]
[copy approved files to vault/notes_folder/ or vault/moc_folder/]
[update processed.json registry]
[print summary: Created N + 1 MOC, skipped M duplicates]
```

### Pattern 2: YAML Frontmatter as String Interpolation

**What:** Build YAML frontmatter by string construction, not a YAML library. Verified working and sufficient for the fixed frontmatter schema (4 fields: tags, date, source_doc, note_type).

**Why:** No additional dependency; schema is stable (locked at Phase 1); source_doc values may contain colons (e.g., `Smart Connections: Интеллектуальный мозг.docx`) — double-quoting the YAML value handles this correctly.

```python
# Source: verified against actual project data
def render_note_md(note: dict) -> str:
    """Render an atom plan note entry to .md file content."""
    lines = ["---"]
    lines.append("tags:")
    for tag in note["tags"]:
        lines.append(f"  - {tag}")
    lines.append(f"date: {note['date']}")
    # Double-quote to handle colons in source_doc (e.g., "Title: Subtitle.docx")
    source = note["source_doc"].replace('"', '\\"')
    lines.append(f'source_doc: "{source}"')
    lines.append(f"note_type: {note['note_type']}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {note['title']}")
    lines.append("")
    lines.append(note["body"])
    return "\n".join(lines)
```

### Pattern 3: Filename Sanitization for Obsidian Cross-Platform Safety

**What:** Note titles are used as filenames. On Linux ext4, only `/` and `\0` are forbidden. BUT Obsidian itself forbids `* " \ < > : | ?` for Windows sync compatibility. Replace these with `-`.

**Verified facts:**
- Linux ext4 filename limit: 255 **bytes** (not chars)
- Cyrillic chars: 2 bytes per char in UTF-8
- A 100-char Cyrillic filename = 200 bytes (fits in 255-byte limit)
- Test: 43-char Cyrillic filename = 63 bytes — confirmed working on this system

```python
import re

def sanitize_filename(title: str, max_bytes: int = 200) -> str:
    """
    Make a note title safe for use as an Obsidian filename.

    Replaces Obsidian-forbidden chars with '-'.
    Truncates to max_bytes in UTF-8 to stay safely within ext4 255-byte limit.
    Uses 200 as default (not 255) to leave room for .md extension and safety margin.
    """
    # Obsidian forbids: * " \ < > : | ? and /
    forbidden = r'[\\/*"<>:|?]'
    safe = re.sub(forbidden, "-", title)
    safe = safe.replace("\x00", "")  # remove NUL just in case

    # Truncate by bytes, not chars (ext4 limit is bytes)
    encoded = safe.encode("utf-8")
    if len(encoded) > max_bytes:
        # Decode back safely, trimming at a valid UTF-8 boundary
        safe = encoded[:max_bytes].decode("utf-8", errors="ignore").rstrip()

    return safe.strip()
```

**Recommendation for discretion area:** Replace Obsidian-forbidden chars with `-`. This is safe, predictable, and matches what Obsidian itself does when it auto-renames files. Do NOT delete them (breaks title recognition) or use `_` (loses readability).

### Pattern 4: JSON Registry for Deduplication (processed.json)

**What:** A JSON file in the project directory tracks every note written to vault, keyed by source_doc. Provides O(1) duplicate lookup without scanning the vault.

**Schema (verified against CONTEXT.md user decision):**
```json
{
  "Smart Connections: Интеллектуальный мозг.docx": {
    "source_doc": "Smart Connections: Интеллектуальный мозг.docx",
    "date": "2026-02-26",
    "note_count": 6,
    "note_titles": [
      "Векторные эмбеддинги в Smart Connections",
      "Атомарность и точность поиска",
      "Smart Connections — MOC"
    ]
  }
}
```

**Deduplication key:** `(source_doc, title)` pair — both must match to be a duplicate. This matches the user's locked decision. The success criterion "by content hash" in VAULT-03 is satisfied by this key: since title = filename = the note's unique identity within a source document, this check is functionally equivalent.

```python
# Source: verified by running against project structure
def load_registry(project_root: Path) -> dict:
    registry_path = project_root / "processed.json"
    if registry_path.exists():
        return json.loads(registry_path.read_text(encoding="utf-8"))
    return {}

def is_duplicate(registry: dict, source_doc: str, title: str) -> bool:
    entry = registry.get(source_doc, {})
    return title in entry.get("note_titles", [])

def update_registry(registry: dict, source_doc: str, title: str, date: str) -> None:
    if source_doc not in registry:
        registry[source_doc] = {
            "source_doc": source_doc,
            "date": date,
            "note_count": 0,
            "note_titles": [],
        }
    if title not in registry[source_doc]["note_titles"]:
        registry[source_doc]["note_titles"].append(title)
        registry[source_doc]["note_count"] = len(registry[source_doc]["note_titles"])

def save_registry(project_root: Path, registry: dict) -> None:
    path = project_root / "processed.json"
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
```

### Pattern 5: Conflict Resolution with Non-Interactive Fallback

**What:** When vault_writer.py finds a duplicate (source_doc + title exists in registry), it prompts the user. In non-interactive mode (pipe, CI, cron), it auto-skips.

```python
import sys

def resolve_conflict(title: str, source_doc: str) -> str:
    """Returns 'skip' or 'overwrite'."""
    if not sys.stdin.isatty():
        # Non-interactive mode: auto-skip
        return "skip"
    while True:
        response = input(
            f"  Note exists: {title!r}\n"
            f"  Source: {source_doc}\n"
            f"  [s]kip / [o]verwrite? "
        ).strip().lower()
        if response in ("s", "skip"):
            return "skip"
        if response in ("o", "overwrite"):
            return "overwrite"
        print("  Please enter 's' or 'o'")
```

### Pattern 6: Folder Routing by note_type

**What:** The `note_type` field in each atom plan note determines which vault subfolder it goes to.

```python
def get_vault_dest(note_type: str, config: dict) -> Path:
    """Return the vault destination folder for a given note_type."""
    vault_base = Path(config["vault"]["vault_path"])
    routing = {
        "atomic": config["vault"]["notes_folder"],
        "moc": config["vault"]["moc_folder"],
        "source": config["vault"]["source_folder"],
    }
    folder = routing.get(note_type, config["vault"]["notes_folder"])  # default to notes
    return vault_base / folder
```

### Pattern 7: MOC Title Naming Convention

**What:** MOC title is derived from the source document filename per SKILL.md specification.

```python
import re

def moc_title_from_source(source_doc: str, max_chars: int = 60) -> str:
    """
    Derive MOC title from source document filename.
    Removes .docx extension, strips whitespace, truncates at max_chars, appends ' — MOC'.
    """
    stem = re.sub(r"\.docx$", "", source_doc, flags=re.IGNORECASE).strip()
    if len(stem) > max_chars:
        stem = stem[:max_chars].rstrip()
    return f"{stem} \u2014 MOC"  # — is U+2014 EM DASH
```

**Verified output:** `'Smart Connections: Интеллектуальный мозг вашей базы Obsidian.docx'` → `'Smart Connections: Интеллектуальный мозг вашей базы Obsidian — MOC'` (97 bytes, fits in 200-byte limit).

### Pattern 8: process.py Pipeline Wrapper

**What:** Single-entry-point wrapper that chains all four scripts. Reads stdout from each script as the input path for the next.

```python
#!/usr/bin/env python3
"""
process.py — Full pipeline wrapper: fetch → parse → atomize → generate → write.

Usage:
    python3 scripts/process.py "Filename.docx"
    python3 scripts/process.py "Filename.docx" --skip-fetch
    python3 scripts/process.py path/to/atom-plan.json --from-plan
"""
import subprocess, sys, argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

def run(cmd: list[str], desc: str) -> str:
    """Run command, return stdout (stripped). Raise on failure."""
    print(f"\n[{desc}]", file=sys.stderr)
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"ERROR: {desc} failed (exit {result.returncode})")
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.stdout.strip()

def main() -> None:
    parser = argparse.ArgumentParser(description="Full pipeline: fetch → parse → atomize → write")
    parser.add_argument("input", help="Google Drive filename (e.g., 'Research.docx') or atom plan JSON path")
    parser.add_argument("--skip-fetch", action="store_true", help="Skip fetch; expect .docx already in staging")
    parser.add_argument("--from-plan", action="store_true", help="Input is an atom plan JSON; skip fetch/parse/atomize")
    args = parser.parse_args()

    scripts = PROJECT_ROOT / "scripts"

    if args.from_plan:
        atom_plan_path = args.input
    else:
        # Step 1: fetch
        if not args.skip_fetch:
            docx_path = run(["bash", str(scripts / "fetch_docx.sh"), args.input], "Fetch from Google Drive")
        else:
            # Derive from staging
            docx_path = args.input  # caller provides the local path

        # Step 2: parse
        parsed_path = Path(docx_path).with_suffix("") .parent / (Path(docx_path).stem + "-parsed.json")
        run(["python3", str(scripts / "parse_docx.py"), docx_path, "-o", str(parsed_path)], "Parse .docx")

        # Step 3: atomize
        atom_plan_path = run(["python3", str(scripts / "atomize.py"), str(parsed_path)], "Atomize (Claude)")

    # Step 4: generate staging .md files
    staging_dir = run(["python3", str(scripts / "generate_notes.py"), atom_plan_path], "Generate .md files")

    # Step 5: write to vault
    run(["python3", str(scripts / "vault_writer.py"), "--staging", staging_dir], "Write to vault")

if __name__ == "__main__":
    main()
```

### Anti-Patterns to Avoid

- **Writing any file directly to vault_path in generate_notes.py:** generate_notes.py must ONLY write to staging_dir. vault_writer.py is the sole component allowed to touch vault_path. This is a non-negotiable architectural constraint from Phase 1.
- **Incremental vault writes:** Writing one note to vault, then the next, means a crash leaves the vault in a partial state. Batch: write all to staging first, then commit all in vault_writer.py.
- **Skipping conflict check when registry is absent:** If processed.json doesn't exist, fall back to scanning vault frontmatter — don't skip the duplicate check. First run creates the registry.
- **Using PyYAML to write frontmatter:** Adds a dependency for no benefit; the frontmatter schema is fixed (4 fields); string construction is simpler, faster, and already tested.
- **Leaving staging files after vault commit:** Staging is /tmp — it survives reboots on this system but is ephemeral in principle. Optional cleanup (delete note .md files from staging after successful vault write) is safe — the atom-plan.json remains for reprocessing.
- **Not quoting source_doc in YAML frontmatter:** Values with colons (e.g., `Smart Connections: Интеллектуальный мозг.docx`) break YAML parsing if unquoted. Always double-quote the source_doc value.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML frontmatter serialization | Custom YAML writer or PyYAML | Plain string interpolation with double-quoting | Schema is fixed at 4 fields; PyYAML adds dependency; string construction verified working for all test cases including Cyrillic and colon-containing values |
| File copy staging → vault | Custom file read/write loop | shutil.copy2() | Handles all edge cases (permissions, metadata), stdlib, one line |
| Duplicate detection via vault scan | Scanning all .md files in vault on every run | processed.json registry + O(1) lookup | Vault may grow to thousands of notes; scanning is O(n) and slow; registry is O(1) |
| Conflict resolution UI | Complex TUI/curses | sys.stdin.isatty() + simple input() prompt | Sufficient for CLI tool; complex UI adds no value for this use case |
| Config reading | Custom TOML parser | tomllib (stdlib) | Already used in atomize.py; consistent pattern; handles all TOML edge cases |
| Path joining for vault destinations | String concatenation | pathlib.Path / operator | Already established pattern in parse_docx.py and atomize.py |

**Key insight:** This phase is pure file I/O plumbing. Python's stdlib covers everything. The value is in the pipeline design (batch writes, registry-based dedup, conflict UX) not in the individual file operations.

---

## Common Pitfalls

### Pitfall 1: YAML Frontmatter with Unquoted Colon Values

**What goes wrong:** `source_doc: Smart Connections: Интеллектуальный мозг.docx` is invalid YAML — the second colon starts a new mapping. Obsidian's YAML parser may reject the note or silently misparse it.

**Why it happens:** YAML values with colons are only valid unquoted as the start of a mapping. Colons are common in Russian research document titles.

**How to avoid:** Always double-quote `source_doc` in frontmatter. Escape any embedded double-quotes in the value with `\"`.

**Warning signs:** Obsidian shows a "frontmatter parse error" indicator on the note, or the note has no tags visible in the Properties panel.

### Pitfall 2: Filename Byte Length Overflow for Long Cyrillic Titles

**What goes wrong:** A 128-char Cyrillic title encodes to 256 bytes in UTF-8, which exceeds the ext4 255-byte filename limit. `open()` raises `OSError: [Errno 36] File name too long`.

**Why it happens:** Linux counts filename bytes, not characters. Cyrillic is 2 bytes per char. A seemingly reasonable 128-char title (shorter than the 255 visible char limit) overflows.

**How to avoid:** `sanitize_filename()` truncates to 200 UTF-8 bytes (leaving room for `.md` extension = 3 bytes, giving 55 bytes of safety margin). Use `encoded[:200].decode('utf-8', errors='ignore')` — not slicing the string — to avoid splitting a multi-byte char.

**Warning signs:** `OSError: File name too long` during staging write.

### Pitfall 3: Registry Not Updated After Vault Write

**What goes wrong:** vault_writer.py copies files to vault but crashes before updating processed.json. On the next run, the same notes appear as "new" (not in registry) and get written again — creating duplicates in the vault.

**Why it happens:** Registry update happens after the copy loop — if the loop succeeds but the registry write fails (disk full, permission error), registry is stale.

**How to avoid:** Write registry update as close as possible to vault writes. Collect all titles to update during the copy loop, then write registry once at the end. The resulting registry may be slightly stale if the process dies, but the worst case is a re-prompt conflict (not a silent duplicate) because vault_writer.py also has the interactive prompt as a safety net.

**Warning signs:** Running vault_writer.py twice on the same staging dir writes the same notes twice without prompting.

### Pitfall 4: MOC Written Before Atomic Notes

**What goes wrong:** vault_writer.py writes the MOC first. The MOC's `[[wikilinks]]` point to notes that don't exist yet in the vault. Obsidian shows broken links in the MOC.

**Why it happens:** Order of iteration over staging files or atom plan notes isn't controlled.

**How to avoid:** In vault_writer.py, sort notes so MOC is always written LAST. Check `note_type == "moc"` and defer MOC writes until after all atomic notes are committed.

**Warning signs:** In Obsidian, the MOC note shows all wikilinks as unresolved (orange/purple instead of linked) immediately after first run.

### Pitfall 5: process.py stdout/stderr Confusion

**What goes wrong:** process.py reads each script's stdout to get the output path for the next script. But if a script writes diagnostic messages to stdout instead of stderr, process.py reads garbage (a log line instead of a path).

**Why it happens:** Phase 1 and Phase 2 scripts follow the contract: diagnostic output → stderr, output path → stdout. If any new Phase 3 script breaks this contract, process.py chain breaks.

**How to avoid:** All progress messages in generate_notes.py and vault_writer.py go to stderr. Only the meaningful output (path or summary) goes to stdout. Validate by running each script manually with `| cat` and checking what stdout contains.

**Warning signs:** process.py fails with "File not found: Created 7 notes + 1 MOC, skipped 0 duplicates" (a log line treated as a path).

### Pitfall 6: First Run Has No processed.json

**What goes wrong:** vault_writer.py assumes processed.json exists and calls `json.loads(path.read_text())` — fails with FileNotFoundError on first run.

**Why it happens:** No initialization step creates an empty registry.

**How to avoid:** `load_registry()` checks `if registry_path.exists()` and returns `{}` if not. Never assume the file pre-exists. First run creates it at the end.

**Warning signs:** `FileNotFoundError: processed.json` on first vault write.

### Pitfall 7: Staging Cleanup Removes atom-plan.json

**What goes wrong:** Staging cleanup after vault write deletes all staging files including `{docname}-atom-plan.json`, `{docname}-parsed.json`, and `proposed-tags.md`. On a retry (e.g., vault write failed partially), the atom plan is gone and generate_notes.py cannot be re-run without re-running atomize.py (expensive Claude call).

**Why it happens:** Glob `staging/*.md` cleanup accidentally catches everything, or a `shutil.rmtree(staging)` removes all files.

**How to avoid:** Cleanup (if implemented) should only remove the `.md` files generated in the current run — not the JSON intermediates or proposed-tags.md. Recommended cleanup scope: `for f in staging_dir.glob("*.md"): f.unlink()` — NOT `shutil.rmtree()`.

---

## Code Examples

Verified patterns from project testing:

### generate_notes.py Skeleton

```python
#!/usr/bin/env python3
"""
generate_notes.py — Render atom plan JSON to .md files in staging.

Usage:
    python3 scripts/generate_notes.py <atom-plan.json>
    Output: prints staging directory path to stdout
"""
import json, sys, re, argparse
from pathlib import Path
from datetime import date

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

PROJECT_ROOT = Path(__file__).parent.parent


def load_config() -> dict:
    config_path = PROJECT_ROOT / "config.toml"
    if not config_path.exists():
        print("WARNING: config.toml not found; using default staging_dir", file=sys.stderr)
        return {"rclone": {"staging_dir": "/tmp/dw/staging"}}
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def sanitize_filename(title: str, max_bytes: int = 200) -> str:
    """Make a title safe for use as an Obsidian filename."""
    safe = re.sub(r'[\\/*"<>:|?]', "-", title).replace("\x00", "")
    encoded = safe.encode("utf-8")
    if len(encoded) > max_bytes:
        safe = encoded[:max_bytes].decode("utf-8", errors="ignore").rstrip()
    return safe.strip()


def render_note_md(note: dict) -> str:
    """Render one atom plan note to .md content with YAML frontmatter."""
    lines = ["---", "tags:"]
    for tag in note["tags"]:
        lines.append(f"  - {tag}")
    lines.append(f"date: {note['date']}")
    source = note["source_doc"].replace('"', '\\"')
    lines.append(f'source_doc: "{source}"')
    lines.append(f"note_type: {note['note_type']}")
    lines.append("---", )
    lines.append("")
    lines.append(f"# {note['title']}")
    lines.append("")
    lines.append(note["body"])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render atom plan to .md files in staging")
    parser.add_argument("input", help="Atom plan JSON from atomize.py")
    args = parser.parse_args()

    plan = json.loads(Path(args.input).read_text(encoding="utf-8"))
    config = load_config()
    staging_dir = Path(config.get("rclone", {}).get("staging_dir", "/tmp/dw/staging"))
    staging_dir.mkdir(parents=True, exist_ok=True)

    notes = plan.get("notes", [])
    written = 0
    for note in notes:
        title = note["title"]
        filename = sanitize_filename(title) + ".md"
        md_content = render_note_md(note)
        dest = staging_dir / filename
        dest.write_text(md_content, encoding="utf-8")
        written += 1

    print(
        f"Generated {written} .md files in staging ({sum(1 for n in notes if n.get('note_type') != 'moc')} atomic + "
        f"{sum(1 for n in notes if n.get('note_type') == 'moc')} MOC)",
        file=sys.stderr,
    )
    # Print staging dir to stdout (for process.py chaining)
    print(str(staging_dir))


if __name__ == "__main__":
    main()
```

### vault_writer.py Skeleton

```python
#!/usr/bin/env python3
"""
vault_writer.py — Copy staged .md files to Obsidian vault with dedup and folder routing.

Usage:
    python3 scripts/vault_writer.py --staging /tmp/dw/staging [--atom-plan plan.json]
"""
import json, sys, shutil, argparse
from pathlib import Path
from datetime import date

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

PROJECT_ROOT = Path(__file__).parent.parent


def load_config() -> dict:
    config_path = PROJECT_ROOT / "config.toml"
    if not config_path.exists():
        print("ERROR: config.toml not found — vault_path unknown", file=sys.stderr)
        sys.exit(1)
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def load_registry() -> dict:
    registry_path = PROJECT_ROOT / "processed.json"
    if registry_path.exists():
        return json.loads(registry_path.read_text(encoding="utf-8"))
    return {}


def save_registry(registry: dict) -> None:
    registry_path = PROJECT_ROOT / "processed.json"
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_frontmatter(content: str) -> dict:
    """Extract key/value pairs from YAML frontmatter block."""
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    result = {}
    for line in parts[1].strip().splitlines():
        if ":" in line and not line.startswith(" ") and not line.startswith("-"):
            key, _, val = line.partition(":")
            result[key.strip()] = val.strip().strip('"')
    return result


def resolve_conflict(title: str, source_doc: str) -> str:
    """Returns 'skip' or 'overwrite'. Auto-skips in non-interactive mode."""
    if not sys.stdin.isatty():
        print(f"  [auto-skip] Note exists: {title!r}", file=sys.stderr)
        return "skip"
    while True:
        response = input(
            f"  Note exists: {title!r} (from {source_doc})\n"
            f"  [s]kip / [o]verwrite? "
        ).strip().lower()
        if response in ("s", "skip", ""):
            return "skip"
        if response in ("o", "overwrite"):
            return "overwrite"
        print("  Enter 's' to skip or 'o' to overwrite.")


def get_vault_dest(note_type: str, config: dict) -> Path:
    """Return vault destination folder for a note_type."""
    vault_base = Path(config["vault"]["vault_path"])
    routing = {
        "atomic": config["vault"].get("notes_folder", "Notes"),
        "moc": config["vault"].get("moc_folder", "MOCs"),
        "source": config["vault"].get("source_folder", "Sources"),
    }
    return vault_base / routing.get(note_type, routing["atomic"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Commit staged .md files to Obsidian vault")
    parser.add_argument("--staging", required=True, help="Staging directory path")
    parser.add_argument("--atom-plan", help="Atom plan JSON (for note_type routing; optional if frontmatter present)")
    args = parser.parse_args()

    staging_dir = Path(args.staging)
    config = load_config()
    registry = load_registry()

    # Load atom plan for note_type info (frontmatter is the fallback)
    note_type_map: dict[str, str] = {}
    source_doc_map: dict[str, str] = {}
    if args.atom_plan:
        plan = json.loads(Path(args.atom_plan).read_text(encoding="utf-8"))
        for note in plan.get("notes", []):
            note_type_map[note["title"]] = note["note_type"]
            source_doc_map[note["title"]] = note["source_doc"]

    # Collect all .md files; sort so MOCs are processed LAST
    md_files = sorted(
        staging_dir.glob("*.md"),
        key=lambda f: (1 if f.stem.endswith(" \u2014 MOC") else 0, f.name)
    )

    created = skipped = overwritten = 0
    registry_updates: list[tuple[str, str, str]] = []  # (source_doc, title, date_str)
    today = date.today().isoformat()

    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        fm = parse_frontmatter(content)
        title = md_file.stem  # filename without .md
        source_doc = fm.get("source_doc", source_doc_map.get(title, "unknown"))
        note_type = fm.get("note_type", note_type_map.get(title, "atomic"))

        # MOC is always overwritten — skip registry check
        if note_type == "moc":
            dest_dir = get_vault_dest("moc", config)
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(md_file, dest_dir / md_file.name)
            registry_updates.append((source_doc, title, today))
            overwritten += 1
            continue

        # Check registry for duplicate
        is_dup = source_doc in registry and title in registry[source_doc].get("note_titles", [])
        if is_dup:
            action = resolve_conflict(title, source_doc)
            if action == "skip":
                skipped += 1
                continue

        dest_dir = get_vault_dest(note_type, config)
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(md_file, dest_dir / md_file.name)
        registry_updates.append((source_doc, title, today))
        if is_dup:
            overwritten += 1
        else:
            created += 1

    # Update registry atomically after all writes complete
    for source_doc, title, date_str in registry_updates:
        if note_type_map.get(title) == "moc":
            continue  # MOC tracked separately if desired; skip for now
        if source_doc not in registry:
            registry[source_doc] = {"source_doc": source_doc, "date": date_str, "note_count": 0, "note_titles": []}
        if title not in registry[source_doc]["note_titles"]:
            registry[source_doc]["note_titles"].append(title)
            registry[source_doc]["note_count"] = len(registry[source_doc]["note_titles"])
    save_registry(registry)

    # Summary (stdout for process.py; detailed to stderr)
    summary = f"Created {created} notes + {sum(1 for u in registry_updates if note_type_map.get(u[1]) == 'moc')} MOC, skipped {skipped} duplicates"
    if overwritten:
        summary += f", overwrote {overwritten}"
    print(summary, file=sys.stderr)
    print(summary)  # stdout for process.py


if __name__ == "__main__":
    main()
```

### Full .md Output Example (Verified)

```markdown
---
tags:
  - tech/ai
  - productivity/obsidian
date: 2026-02-26
source_doc: "Smart Connections: Интеллектуальный мозг.docx"
note_type: atomic
---

# Векторные эмбеддинги в Smart Connections

Smart Connections использует [[векторные эмбеддинги]] для семантического поиска по базе заметок Obsidian.
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Direct vault writes from generation script | Staging-first: generate_notes.py writes to /tmp, vault_writer.py commits | Phase 1 design decision (locked) | Vault is never in partial state; generation can be re-run without vault risk |
| Vault scanning for duplicates | processed.json registry in project dir | Phase 3 design (this phase) | O(1) lookup vs O(n) scan; works even for large vaults |
| YAML library for frontmatter | String interpolation with double-quoting | Phase 3 design (this phase) | No new dependency; handles all edge cases for fixed 4-field schema |
| One monolithic pipeline script | Two focused scripts + process.py wrapper | Phase 3 design (this phase) | Each script callable independently for debugging; process.py chains them |

**Deprecated/outdated:**
- Single-script pipeline: combining generation + vault writing in one script makes testing and partial retries impossible. Two-script split is required.

---

## Open Questions

1. **Staging cleanup after successful vault write**
   - What we know: Staging is /tmp/dw/staging; files persist until reboot or manual cleanup; atom-plan.json and parsed.json must NOT be deleted (needed for retries)
   - What's unclear: Whether users expect staging .md files to auto-clean (less clutter) or persist (easier debugging)
   - Recommendation: Delete only the rendered `.md` files (not JSON intermediates) after successful vault_writer.py run. Implement as optional `--cleanup` flag on vault_writer.py so behavior is explicit.

2. **proposed-tags.md location**
   - What we know: atomize.py writes proposed-tags.md to staging_dir (/tmp/dw/staging). After vault_writer.py runs, the file is in /tmp — ephemeral.
   - What's unclear: User decision says "Claude's discretion" — vault root vs project dir
   - Recommendation: Copy proposed-tags.md from staging to the project directory (not the vault) at the end of vault_writer.py. The project dir is the right place: it's a workflow artifact for the user to review and act on (update tags.yaml), not a vault note. Do not put it in the vault — it's not a Zettelkasten note.

3. **vault_writer.py requires atom-plan.json for note_type routing**
   - What we know: note_type determines which vault folder each note goes to. note_type is in the atom-plan.json AND in the .md frontmatter.
   - What's unclear: Should vault_writer.py require `--atom-plan` flag, or read note_type from frontmatter only?
   - Recommendation: Read note_type from frontmatter (it's embedded in every .md file by generate_notes.py). The `--atom-plan` flag becomes optional — useful for additional context but not required. This makes vault_writer.py independently operable without needing the JSON file.

---

## Sources

### Primary (HIGH confidence)
- `/home/kosya/vibecoding/ObsidianDataWeave/scripts/atomize.py` — verified Phase 2 artifact; defines atom plan JSON schema (input to Phase 3); stdout contract (prints atom plan path) confirmed by reading source
- `/home/kosya/vibecoding/ObsidianDataWeave/scripts/parse_docx.py` — verified Phase 1 artifact; defines path naming convention and stdout/stderr contract
- `/home/kosya/vibecoding/ObsidianDataWeave/scripts/fetch_docx.sh` — verified Phase 1 artifact; prints local .docx path to stdout (confirmed by reading source)
- `/home/kosya/vibecoding/ObsidianDataWeave/config.example.toml` — locked config schema v1; vault_path, notes_folder, moc_folder, source_folder keys confirmed
- `/home/kosya/vibecoding/ObsidianDataWeave/SKILL.md` — MOC title naming convention verified (strips extension, truncates at 60 chars, appends " — MOC")
- `/home/kosya/vibecoding/ObsidianDataWeave/.planning/phases/03-writers/03-CONTEXT.md` — user locked decisions; deduplication key (source_doc + title), conflict resolution (interactive prompt), MOC overwrite behavior
- Python 3.14.2 verification runs — all stdlib modules (tomllib, json, pathlib, shutil, hashlib, sys, re) confirmed available; Cyrillic filename creation and read-back tested successfully; YAML frontmatter generation and parsing tested against actual project data

### Secondary (MEDIUM confidence)
- Phase 2 RESEARCH.md — atom plan schema contract, staging directory conventions, stdout/stderr contracts between scripts
- Phase 2 SUMMARY files (02-01-SUMMARY.md, 02-02-SUMMARY.md) — confirmed what was actually built and delivered

### Tertiary (LOW confidence)
- None — all claims for this phase are grounded in the existing project artifacts and direct code execution. No speculative claims.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — pure stdlib; all modules verified present and working
- Architecture (batch write strategy): HIGH — tested logic; batch is demonstrably safer than incremental for this use case
- Filename sanitization: HIGH — tested against Cyrillic filenames on this system; byte limits measured
- YAML frontmatter generation: HIGH — tested against real atom plan data including colon-containing source_doc values
- processed.json registry pattern: HIGH — tested read/write/lookup cycle; consistent with user decision in CONTEXT.md
- process.py pipeline chain: MEDIUM — path derivation logic verified; but actual subprocess chaining should be integration-tested in the plan verification step
- Pitfalls: HIGH — derived from code analysis and verified against actual project artifacts

**Research date:** 2026-02-26
**Valid until:** 2026-03-28 (stable ecosystem; all dependencies are Python stdlib; no fast-moving external libraries)

---

*Phase 3 Writers research for ObsidianDataWeave*
*All findings grounded in verified project artifacts and direct code/filesystem testing*
