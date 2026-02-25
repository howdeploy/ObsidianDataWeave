# Stack Research

**Domain:** CLI/scripting toolkit — .docx → Obsidian knowledge base automation
**Researched:** 2026-02-25
**Confidence:** MEDIUM overall (web search unavailable this session; based on training data to Aug 2025 + PyPI ecosystem knowledge; versions flagged LOW where unverified)

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| Python 3 | 3.11+ | Primary scripting language | Pre-installed on Manjaro, best .docx/markdown ecosystem, Claude Code skills are bash/python native. No Node.js runtime required. | HIGH |
| python-docx | 1.1.x | Parse .docx files — extract paragraphs, headings, styles, runs | The de-facto standard for .docx reading in Python. Direct access to document XML structure, heading levels (Heading 1/2/3), bold/italic runs, tables. Actively maintained. Alternatives are either lower-level (raw XML) or convert to HTML first (mammoth) which loses structural metadata needed for Zettelkasten splitting. | MEDIUM (version needs pip verify) |
| PyYAML | 6.0.x | Generate YAML frontmatter for Obsidian notes | Standard Python YAML library. Used for writing `---` frontmatter blocks with tags, aliases, date, source fields. `yaml.dump()` with `allow_unicode=True` handles Cyrillic titles correctly. | HIGH |
| Click | 8.1.x | CLI argument parsing for the skill entry points | The standard Python CLI framework. Clean decorator syntax, auto-generates `--help`, handles `--vault-path`, `--source-file`, `--dry-run` flags naturally. Used by Flask, Black, pip itself. Better than argparse for user-facing tools. | HIGH |
| Rich | 13.x | Terminal output formatting — progress bars, tables, colored status | Makes skill output readable during processing (shows which notes were created, warnings about structure). Zero-dependency install overhead justified by UX. Essential for a skill that processes 20-50 atomic notes per run. | HIGH |

### Supporting Libraries

| Library | Version | Purpose | When to Use | Confidence |
|---------|---------|---------|-------------|------------|
| python-frontmatter | 3.x | Read/write markdown files with YAML frontmatter | Use when updating existing notes (check if note already exists, read its frontmatter, merge tags). Not needed for pure creation flow, but critical for idempotent re-runs. | MEDIUM |
| pathlib (stdlib) | stdlib | File path manipulation for vault directory traversal | Always. Use `pathlib.Path` over `os.path` everywhere — cleaner syntax, handles `/mnt/sda1/KISA's Space/` paths with spaces correctly via `.resolve()`. | HIGH |
| re (stdlib) | stdlib | Regex for wikilink generation, tag sanitization | Always. Used to convert heading text to `[[Note Title]]` format, strip illegal characters from Obsidian note filenames (`\ / : * ? " < > |`). | HIGH |
| subprocess (stdlib) | stdlib | Call rclone for Google Drive download | Use for the download step: `subprocess.run(["rclone", "copy", "gdrive:path/file.docx", "/tmp/"], check=True)`. Better than shell=True for security and error handling. | HIGH |
| tomllib / tomli | stdlib (3.11+) / 0.2.x | Config file parsing (pyproject.toml-style config) | Use for `~/.config/obsidian-dataweave/config.toml` — vault path, folder mappings, tag prefixes. tomllib is stdlib in Python 3.11+, no install needed. | MEDIUM |
| mammoth | 1.8.x | Convert .docx to clean HTML/markdown as fallback | Use ONLY when python-docx fails to parse a document (corrupted styles, non-standard .docx from Google Docs export). Mammoth strips structure but gives clean text. Not primary — it loses heading hierarchy which is essential for atomic note splitting. | MEDIUM (version needs verify) |
| pytest | 7.x+ | Unit testing for parser and note generator logic | Use for testing the splitting logic, YAML generation, wikilink resolution. Run with `pytest tests/` before any release. | HIGH |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| rclone | Google Drive file download | Already configured (`gdrive:` remote). Use `rclone copy gdrive:path /tmp/odw/` to pull files. No Python wrapper needed — call via subprocess. rclone handles auth, retry, partial downloads. | HIGH confidence it's the right choice |
| pandoc | Fallback .docx → markdown conversion | Optional system dependency. Use only as last-resort fallback when both python-docx and mammoth fail. Output requires post-processing to add frontmatter and fix wikilinks. Install: `sudo pacman -S pandoc`. | LOW confidence it's needed in v1 |
| uv | Python package manager for install script | Faster than pip for the one-command install (`uv pip install -r requirements.txt`). Available on Manjaro via `pacman -S uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`. Makes `install.sh` more reliable across Python versions. | MEDIUM |

---

## Installation

```bash
# Core runtime dependencies
pip3 install python-docx PyYAML click rich

# Supporting (recommended for production use)
pip3 install python-frontmatter

# Dev dependencies (testing only)
pip3 install pytest

# System tools (already present per project constraints)
# rclone — already configured
# python3 3.11+ — pre-installed on Manjaro
```

**One-command install approach for the GitHub package:**
```bash
# install.sh pattern
python3 -m pip install --user python-docx PyYAML click rich python-frontmatter
```

Using `--user` avoids sudo and works cleanly on Manjaro without virtualenv. For the Claude Code skill, dependencies are installed at first run via the install script.

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative | Why NOT for This Project |
|-------------|-------------|------------------------|--------------------------|
| python-docx | mammoth | When you only need clean prose text and don't care about heading hierarchy | mammoth converts to HTML/markdown but loses Heading 1 / Heading 2 style metadata — which is exactly what we use to decide where to split atomic notes |
| python-docx | docx2python | When you need precise cell-level table extraction | docx2python is excellent for tables but overkill; python-docx handles tables adequately and is more widely documented |
| python-docx | pandoc (subprocess) | When output format flexibility matters more than control | Pandoc output requires heavy post-processing to add YAML frontmatter and convert to wikilinks; adds a system dependency |
| Click | argparse (stdlib) | Internal scripts not meant for end users | argparse is fine for simple scripts; Click is worth the install for user-facing skill CLI because of `--help` auto-generation and decorator cleanliness |
| Click | Typer | If you want auto-typed CLI from Python type hints | Typer is excellent but adds Pydantic dependency; Click is lighter and more stable for a simple skill package |
| PyYAML | ruamel.yaml | When you need to preserve comments and ordering in YAML round-trips | ruamel.yaml is better for editing existing YAML; PyYAML is sufficient for writing fresh frontmatter |
| TOML config | JSON config | When config is machine-generated only | JSON is harder to hand-edit (no comments); TOML is more ergonomic for vault path and folder mapping config users will edit manually |
| Rich | colorama | Basic color output only | colorama only adds ANSI colors; Rich adds progress bars and structured output tables which are useful for showing "created 23 notes" summaries |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| docx2txt | Read-only text extraction, strips all structure — no heading levels, no style metadata | python-docx with `.paragraphs[].style.name` to get Heading 1/2/3 |
| textract | Complex C-library dependencies (antiword, pdftotext), breaks on Manjaro installs, unmaintained since 2021 | python-docx + mammoth as fallback |
| Apache Tika (tika-python) | Requires JVM running as a server, massive overhead for a CLI tool | python-docx for .docx specifically |
| Obsidian Plugin JS | The project requirement explicitly excludes Obsidian plugins — different runtime, different deployment, requires Obsidian desktop open | Claude Code skills in Python/bash |
| watchdog (file watcher) | Auto-monitoring of Google Drive is out of scope for v1 per PROJECT.md | Manual rclone + skill invocation |
| SQLite / database | Overkill for tracking note state; flat file index or frontmatter `source` field is sufficient | Frontmatter `source_doc` field in each note for traceability |
| LangChain | Heavy dependency for text splitting; the splitting logic is deterministic (heading-based), not semantic | Custom Python splitter using python-docx heading styles |
| openai / anthropic SDK | Note generation uses Claude Code (the LLM context window), not API calls inside the skill | The skill itself is pure Python; Claude Code invokes it and reads output |

---

## Stack Patterns by Variant

**For the core .docx → atomic notes pipeline:**
- Use `python-docx` to walk `.paragraphs`, split on `style.name in ["Heading 1", "Heading 2"]`
- Each heading becomes one atomic note
- Sub-headings become body content or nested notes depending on depth
- Because `python-docx` gives direct heading level access without regex heuristics

**For Obsidian YAML frontmatter generation:**
- Use `PyYAML.dump()` with `allow_unicode=True, default_flow_style=False`
- Structure: `tags`, `aliases`, `date_created`, `source_doc`, `source_heading`
- Wrap in `---\n...\n---` manually (PyYAML doesn't write the delimiters)
- Because Obsidian's YAML parser is strict about formatting

**For wikilink generation between notes:**
- Build an index of all note titles in the current batch
- Run regex replacement on body text: any mention of a known note title → `[[Title]]`
- Use case-insensitive matching with Cyrillic support (`re.IGNORECASE | re.UNICODE`)
- Because Obsidian wikilinks are title-based, not path-based

**For MOC (Map of Content) generation:**
- MOC is a plain markdown file with a list of `[[wikilinks]]` grouped by theme
- Generate after all atomic notes are created
- Group by top-level heading from source doc (= thematic cluster)
- Because MOC files are just curated link lists, no special format required

**For rclone integration:**
- Use `subprocess.run(["rclone", "copy", source, dest], check=True, capture_output=True)`
- Parse stderr for progress/errors
- Stage files to `/tmp/odw_staging/` before processing, never write to vault until all notes generated
- Because rclone is already configured and battle-tested; reimplementing Drive API auth is unnecessary complexity

**For Claude Code skill packaging:**
- Entry point: `skill.py` with Click CLI, invoked by `claude` via the skill definition
- Skill definition in `~/.claude/skills/obsidian-dataweave/SKILL.md`
- The `.md` skill file describes what Claude should do (download, call parser, review output)
- The Python scripts do the mechanical work (parsing, writing files)
- Because Claude Code skills are prose instructions + tool invocations; the Python handles deterministic file manipulation

---

## Version Compatibility

| Package | Compatible With | Notes | Confidence |
|---------|-----------------|-------|------------|
| python-docx 1.1.x | Python 3.8–3.13 | Requires `lxml`; installs automatically | MEDIUM |
| PyYAML 6.0.x | Python 3.6–3.13 | YAML 1.1 spec; `yaml.safe_dump()` for untrusted input | HIGH |
| Click 8.1.x | Python 3.7–3.13 | No breaking changes expected in 8.x branch | HIGH |
| Rich 13.x | Python 3.7–3.13 | `Console()` API stable since v10 | HIGH |
| python-frontmatter 3.x | Python 3.7+ | Uses PyYAML internally; same YAML engine | MEDIUM |
| mammoth 1.8.x | Python 3.6+ | Actively maintained; no known conflicts | MEDIUM |

**Known issue:** `python-docx` depends on `lxml` which requires C build tools. On Manjaro this is handled by `pacman -S python-lxml` or pip installs the wheel directly. Include in install.sh check.

---

## Confidence Assessment Summary

| Area | Confidence | Reason |
|------|------------|--------|
| python-docx as primary .docx parser | HIGH | Industry standard, no real competitor for structured extraction |
| PyYAML for frontmatter | HIGH | stdlib-adjacent, universally used |
| Click for CLI | HIGH | Industry standard for Python CLIs |
| Rich for output | HIGH | Dominant in modern Python CLI tools |
| mammoth as fallback | MEDIUM | Version unverified (web search unavailable this session) |
| python-frontmatter for idempotency | MEDIUM | Stable library but version unverified |
| TOML for config | MEDIUM | tomllib is stdlib in 3.11+; confirm Manjaro Python version |
| uv as package manager | MEDIUM | Rapidly adopted in 2024-2025 but adoption in skill install scripts untested |
| pandoc as fallback | LOW | Adds system dependency; likely not needed in v1 |

---

## Sources

- PyPI ecosystem knowledge (training data to Aug 2025) — MEDIUM confidence; versions should be verified with `pip3 index versions <package>` before pinning in requirements.txt
- python-docx API: https://python-docx.readthedocs.io/en/latest/ — authoritative docs (not fetched this session — web tools unavailable)
- Obsidian markdown spec: https://help.obsidian.md/Editing+and+formatting/Basic+formatting+syntax — wikilinks and YAML frontmatter format
- Project constraints from `.planning/PROJECT.md` — HIGH confidence (first-party)
- rclone documentation: https://rclone.org/docs/ — HIGH confidence (already in use per project)

**Note on research constraints:** Web search and extract tools were unavailable this session (Tavily MCP permission denied, WebSearch/WebFetch hooks redirecting to unavailable server). Version numbers reflect training data to Aug 2025. Before pinning versions in `requirements.txt`, run:
```bash
pip3 index versions python-docx mammoth python-frontmatter
```

---

*Stack research for: ObsidianDataWeave — .docx → Obsidian MOC+Zettelkasten automation toolkit*
*Researched: 2026-02-25*
