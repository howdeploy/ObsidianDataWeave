# Phase 4: Publish - Research

**Researched:** 2026-02-26
**Domain:** Bash install scripts, README authoring, Obsidian vault templates, Claude Code skill registration
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### README Structure
- Bilingual EN+RU in a single file (sections in both languages)
- Brief introduction to MOC + Zettelkasten methodology (1-2 paragraphs), then practical instructions
- Quick Start section: 2-3 copy-paste commands for Claude Code (1. Install, 2. Configure, 3. Process a document)
- Minimum explanations — user copies commands into Claude Code and it handles the rest

#### install.sh Scope
- Cross-platform: Linux (pacman/apt/dnf) + macOS (brew) — detect package manager automatically
- Installs rclone if not present (via package manager or official script)
- Installs python-docx via pip
- Creates config.toml from config.example.toml interactively — prompts for vault_path and rclone remote name
- Automatically registers SKILL.md as a Claude Code skill
- Creates vault folders (notes_folder, moc_folder, source_folder) in the configured vault if they don't exist
- install.sh should be idempotent — safe to re-run without breaking existing config

#### Obsidian Templates
- Starter vault structure with folders (Notes, MOCs, Sources) included in repo under templates/
- Example notes: 1 atomic note + 1 MOC — English language, showing proper frontmatter and wikilinks format
- Smart Connections config: Claude's discretion (ready JSON config or text recommendations in README)

#### Security & Portability
- MIT license
- .gitignore: Claude's discretion (comprehensive list beyond config.toml and processed.json)
- Security audit approach: Claude's discretion (automated grep scan or robust .gitignore only)
- No git push in this phase — user tests locally first, pushes manually after verifying the pipeline works on their Obsidian vault

### Claude's Discretion
- Smart Connections config format (JSON file vs README text)
- Full .gitignore list (beyond the two already gitignored files)
- Security audit approach (grep scan vs .gitignore-only)
- install.sh error handling and rollback on failure
- README section ordering and formatting

### Deferred Ideas (OUT OF SCOPE)
- Git push / publishing to GitHub (user does manually after local verification)
- CI/CD or automated testing of the install script
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DIST-01 | README contains copy-paste commands that a user sends to Claude for installation | README Quick Start section design: 2-3 commands using `python3 scripts/process.py` pattern; bilingual structure documented |
| DIST-02 | Claude follows README commands: clones repo, installs dependencies, creates config, registers skill | install.sh covers all steps; skill registration pattern identified (append section to ~/.claude/CLAUDE.md) |
| DIST-03 | README includes Obsidian templates: folder structure, starter MOC hubs, atomic note examples | templates/ directory with 1 atomic note + 1 MOC; frontmatter schema v1 locked and documented |
| DIST-04 | Recommended Smart Connections config delivered with templates | smart_env.json format identified from real vault; recommended settings documented |
</phase_requirements>

---

## Summary

This phase has four distinct deliverables: install.sh (cross-platform installer), README.md (bilingual), templates/ (Obsidian vault starter kit), and MIT license. The project is already clean — no hardcoded personal paths exist in any script, config.toml and processed.json are already gitignored. The primary technical complexity is in install.sh: handling three package managers (pacman/apt/dnf + brew) plus pip's "externally-managed-environment" restriction on Manjaro/Arch.

The Python dependency situation is confirmed from the running system: python-docx 1.2.0 requires lxml as a hard dependency. On Manjaro, pip3 install python-docx works with `--break-system-packages` flag and installs lxml via pre-built wheel to `~/.local`. On Ubuntu 22.04, the default Python is 3.10 — the scripts handle this gracefully (tomllib falls back to tomli, with an informative warning). On macOS with Homebrew, pip3 works normally without restrictions. install.sh must detect which environment it's in and use the correct pip invocation.

The "register SKILL.md as a Claude Code skill" requirement means: append a pipeline skill section to `~/.claude/CLAUDE.md` that teaches the user's Claude how to trigger ObsidianDataWeave by recognizing phrases like "process a document" and running `python3 scripts/process.py`. This is distinct from the existing SKILL.md (which is the atomization prompt for `atomize.py`'s subprocess call to Claude). Smart Connections config format is confirmed: `.smart-env/smart_env.json` in the vault root — we deliver this file in templates/ as a ready-to-copy drop-in.

**Primary recommendation:** Build install.sh with a `detect_pkg_manager()` function at the top, use idempotency guards (`command -v`, `[ -f ]`, `grep -q`) throughout, and write the Claude Code skill section to `~/.claude/CLAUDE.md` by appending — not overwriting — checking first for duplicate registration.

---

## Standard Stack

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| bash | system | install.sh interpreter | Universal on Linux/macOS, no dep needed |
| python3 | 3.10+ (3.11+ recommended) | runtime for all scripts | Already required by the pipeline |
| pip3 | bundled with python3 | install python-docx | Standard Python package installer |
| rclone | 1.73+ | Google Drive access | Already used by fetch_docx.sh |

### Supporting
| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| pacman | system | Manjaro/Arch package manager | Linux Arch-based distros |
| apt | system | Debian/Ubuntu package manager | Debian-based Linux |
| dnf | system | Fedora/RHEL package manager | RPM-based Linux |
| brew | system | macOS package manager | macOS only |
| curl | system | Download rclone install script fallback | When rclone not in package manager |

### python-docx Dependency Chain
| Package | Version | Notes |
|---------|---------|-------|
| python-docx | >=1.1.0,<2.0.0 | Hard requires lxml |
| lxml | >=3.1.0 | C extension — has pre-built wheels for Linux/macOS |
| typing_extensions | >=4.9.0 | Pure Python, no issues |

**Key finding (HIGH confidence — tested on running system):** `pip3 install python-docx` pulls lxml as a wheel (no compilation) on all major platforms. On Manjaro/Arch with externally-managed Python, use `pip3 install --break-system-packages python-docx` which installs to `~/.local`.

**Alternative for Manjaro:** `sudo pacman -S python-lxml` then `pip3 install --break-system-packages python-docx`. Avoids pip's wheel and uses system lxml. Cleaner on Arch-based distros.

---

## Architecture Patterns

### Recommended Project Structure After Phase 4

```
ObsidianDataWeave/
├── install.sh                 # Cross-platform installer (NEW)
├── README.md                  # Bilingual EN+RU docs (NEW)
├── LICENSE                    # MIT license (NEW)
├── config.example.toml        # Template config (already exists)
├── config.toml                # gitignored — user copy
├── requirements.txt           # python-docx>=1.1.0,<2.0.0
├── SKILL.md                   # Atomization prompt for atomize.py
├── tags.yaml                  # Canonical tag taxonomy
├── rules/
│   ├── atomization.md
│   └── taxonomy.md
├── scripts/
│   ├── process.py             # Pipeline entry point
│   ├── fetch_docx.sh
│   ├── parse_docx.py
│   ├── atomize.py
│   ├── generate_notes.py
│   └── vault_writer.py
└── templates/                 # Obsidian vault starter kit (NEW)
    ├── README.md              # Template usage instructions
    ├── Notes/
    │   └── Atomic Note Example.md
    ├── MOCs/
    │   └── Topic Map — MOC.md
    ├── Sources/
    │   └── .gitkeep
    └── .smart-env/
        └── smart_env.json     # Smart Connections config
```

### Pattern 1: Package Manager Detection in install.sh

```bash
#!/usr/bin/env bash
set -euo pipefail

detect_pkg_manager() {
    if command -v pacman &>/dev/null; then
        echo "pacman"
    elif command -v brew &>/dev/null; then
        echo "brew"
    elif command -v apt-get &>/dev/null; then
        echo "apt"
    elif command -v dnf &>/dev/null; then
        echo "dnf"
    else
        echo "unknown"
    fi
}

PKG_MGR=$(detect_pkg_manager)
```

**What:** Detects system package manager at runtime, drives all install decisions.
**When to use:** First thing in install.sh; all package install blocks branch on PKG_MGR.

### Pattern 2: Idempotency Guards

```bash
# Guard: only install if not present
install_rclone() {
    if command -v rclone &>/dev/null; then
        echo "  rclone already installed: $(rclone --version | head -1)"
        return 0
    fi
    case "$PKG_MGR" in
        pacman) sudo pacman -S --noconfirm rclone ;;
        brew)   brew install rclone ;;
        apt)    sudo apt-get install -y rclone ;;
        dnf)    sudo dnf install -y rclone ;;
        *)      curl https://rclone.org/install.sh | sudo bash ;;
    esac
}

# Guard: only create config if not present
create_config() {
    if [ -f "config.toml" ]; then
        echo "  config.toml already exists — skipping interactive setup"
        return 0
    fi
    # Interactive prompt
    ...
}
```

**What:** Every install.sh step checks current state before acting.
**When to use:** All install/create operations — ensures re-running is safe.

### Pattern 3: pip Installation on Externally-Managed Environments

```bash
install_python_docx() {
    # Check if already available
    if python3 -c "import docx" 2>/dev/null; then
        echo "  python-docx already installed"
        return 0
    fi

    case "$PKG_MGR" in
        pacman)
            # Prefer system lxml, then user-install python-docx
            sudo pacman -S --noconfirm python-lxml 2>/dev/null || true
            pip3 install --break-system-packages python-docx
            ;;
        brew)
            pip3 install python-docx
            ;;
        apt|dnf)
            pip3 install python-docx
            ;;
        *)
            pip3 install python-docx
            ;;
    esac
}
```

**Key insight (HIGH confidence — verified on system):** `pip3 install --break-system-packages` is required on Manjaro/Arch. On macOS/Ubuntu pip3 works without this flag. The flag does NOT affect lxml wheel installation — pip downloads a pre-built wheel, no C compilation needed.

### Pattern 4: Claude Code Skill Registration

```bash
register_claude_skill() {
    local claude_md="$HOME/.claude/CLAUDE.md"
    local marker="## ObsidianDataWeave Pipeline"

    # Idempotency: skip if already registered
    if [ -f "$claude_md" ] && grep -q "$marker" "$claude_md"; then
        echo "  Claude Code skill already registered"
        return 0
    fi

    local repo_dir
    repo_dir="$(pwd)"

    cat >> "$claude_md" <<EOF

---

## ObsidianDataWeave Pipeline

When the user says:
- "process a document" / "atomize document"
- "run the pipeline" / "import to Obsidian"
- "process [filename].docx"

Run:
\`\`\`bash
cd ${repo_dir} && python3 scripts/process.py "Filename.docx"
\`\`\`

Or to skip fetch (file already in staging):
\`\`\`bash
cd ${repo_dir} && python3 scripts/process.py "Filename.docx" --skip-fetch
\`\`\`

Config: \`${repo_dir}/config.toml\`
EOF

    echo "  Registered ObsidianDataWeave skill in $claude_md"
}
```

**What:** Appends a trigger-phrase section to `~/.claude/CLAUDE.md`. Embeds the repo's absolute path so Claude runs commands in the correct directory.
**Critical:** Check for existing registration with grep before appending — re-running install.sh must not create duplicate sections.

### Pattern 5: Vault Folder Creation

```bash
create_vault_folders() {
    local vault_path notes_folder moc_folder source_folder

    vault_path=$(python3 - config.toml <<'PYEOF'
import sys, tomllib
with open(sys.argv[1], "rb") as f: d = tomllib.load(f)
print(d["vault"]["vault_path"])
PYEOF
    )

    notes_folder="$vault_path/Research & Insights"
    moc_folder="$vault_path/Guides & Overviews"
    source_folder="$vault_path/Sources"

    for folder in "$notes_folder" "$moc_folder" "$source_folder"; do
        [ -d "$folder" ] || mkdir -p "$folder"
        echo "  Folder ready: $folder"
    done
}
```

**Note:** Folder names should be read from config.toml, not hardcoded — config.example.toml has defaults but user may have customized them.

### Obsidian Note Template Formats

**Atomic Note frontmatter (schema v1, locked):**
```yaml
---
tags:
  - domain/subtag
  - domain/subtag
date: 2026-02-26
source_doc: "Example Document.docx"
note_type: atomic
---

# Note Title Here

Note body text with [[Wikilink to Related Note]] inline.
```

**MOC frontmatter (schema v1, locked):**
```yaml
---
tags:
  - domain/subtag
date: 2026-02-26
source_doc: "Example Document.docx"
note_type: moc
---

# Topic Map — MOC

## Section One

- [[Atomic Note Title A]]
- [[Atomic Note Title B]]

## Section Two

- [[Atomic Note Title C]]
```

**Source:** `scripts/generate_notes.py` `render_note_md()` function — schema locked in Phase 3.

### Smart Connections Config (smart_env.json)

Deliver `templates/.smart-env/smart_env.json` with these recommended settings:

```json
{
  "is_obsidian_vault": true,
  "smart_blocks": {
    "embed_blocks": true,
    "min_chars": 100
  },
  "smart_sources": {
    "min_chars": 100,
    "embed_model": {
      "adapter": "transformers",
      "transformers": {
        "model_key": "TaylorAI/bge-micro-v2"
      }
    },
    "excluded_headings": "",
    "file_exclusions": "Untitled",
    "folder_exclusions": ""
  },
  "language": "en",
  "connections_lists": {
    "results_collection_key": "smart_sources",
    "score_algo_key": "similarity",
    "connections_post_process": "none",
    "results_limit": 20,
    "exclude_frontmatter_blocks": true
  }
}
```

**Source:** Real vault `.smart-env/smart_env.json` from user's active Obsidian vault (HIGH confidence).
**Key choices:**
- `embed_model.adapter: "transformers"` with `TaylorAI/bge-micro-v2` — free, runs locally, no API key
- `min_chars: 100` — below the 150-word minimum of atomic notes, so all notes get embedded
- `embed_blocks: true` — enables paragraph-level connections in addition to note-level

**Delivery decision (Claude's discretion):** Ship as a ready JSON file at `templates/.smart-env/smart_env.json` (not just README text). Users copy entire `.smart-env/` directory to their vault root. This is more reliable than asking them to create JSON by hand.

**Installation instruction for README:** "Copy `templates/.smart-env/` to your vault root, then open Obsidian and enable the Smart Connections plugin from Community Plugins."

### Anti-Patterns to Avoid

- **Hardcoding vault path in CLAUDE.md skill registration:** Use `$(pwd)` at install time, not a path that may change.
- **Using `pip install` without `--break-system-packages` on Arch/Manjaro:** Will fail silently or error.
- **Writing config.toml if it already exists:** Overwrites user's real paths. Always guard with `[ -f config.toml ]`.
- **Overwriting ~/.claude/CLAUDE.md:** Only append, never overwrite. Always check for duplicate skill section first.
- **Putting the smart_env.json in the wrong location:** It must be at `.smart-env/smart_env.json` in the vault root, NOT inside `.obsidian/plugins/smart-connections/`.
- **README copy-paste commands that reference relative paths:** Commands in README should either be relative to the repo root (with `cd` instruction) or use the project path returned from install.sh.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| rclone installation on unknown platform | custom download logic | `curl https://rclone.org/install.sh \| sudo bash` fallback | Official script handles all platforms and architectures |
| TOML parsing in bash | bash TOML parser | inline python3 heredoc with tomllib | tomllib is stdlib in Python 3.11+; one-liner inline script is reliable |
| Interactive config prompts with validation | custom loop + validation | simple `read -p` prompts with sensible defaults | Config is just 2 fields (vault_path, rclone remote); validation is trivial |
| Smart Connections plugin installation | Obsidian API scripting | README instruction only | Plugin marketplace requires Obsidian GUI; cannot automate |

**Key insight:** install.sh should do mechanical operations (install packages, copy files, create directories, append text). Anything requiring user judgment (which Google Drive files to process, whether config is correct) stays in the README as human instructions.

---

## Common Pitfalls

### Pitfall 1: pip externally-managed-environment on Arch/Manjaro

**What goes wrong:** `pip3 install python-docx` on Manjaro fails with "externally-managed-environment" error, crashing the install script.
**Why it happens:** PEP 668 — Manjaro/Arch mark their Python environment as system-managed. pip refuses to install packages globally without explicit override.
**How to avoid:** Detect Arch-based distros (check for `pacman`) and use `pip3 install --break-system-packages python-docx`. This installs to `~/.local/lib/python3.X/site-packages` (user site), not system site-packages.
**Warning signs:** `error: externally-managed-environment` in stderr from pip.

### Pitfall 2: Duplicate skill registration in CLAUDE.md

**What goes wrong:** Re-running install.sh appends a second "ObsidianDataWeave Pipeline" section to `~/.claude/CLAUDE.md`, creating duplicate trigger entries.
**Why it happens:** Simple `cat >> file <<EOF` without idempotency check.
**How to avoid:** `grep -q "## ObsidianDataWeave Pipeline" "$HOME/.claude/CLAUDE.md"` before appending. If found, skip registration.
**Warning signs:** User sees duplicate skill sections when running `cat ~/.claude/CLAUDE.md`.

### Pitfall 3: Config vault_path used before validation

**What goes wrong:** install.sh reads vault_path from user input and immediately tries to create directories without validating the path exists.
**Why it happens:** `mkdir -p` succeeds even for nonexistent paths (creates them), but the user may have typo'd their vault path.
**How to avoid:** After reading vault_path, check `[ -d "$vault_path" ]` before creating subfolders. If vault doesn't exist, warn user but do not fail — they may be setting up a new vault.

### Pitfall 4: Hardcoded folder names in install.sh instead of reading from config.toml

**What goes wrong:** install.sh creates `"Research & Insights"` hardcoded, but user may have changed `notes_folder` in config.toml.
**Why it happens:** Treating config.example.toml values as constants.
**How to avoid:** After creating config.toml, read folder names back from it using the same `python3 -c "import tomllib..."` pattern used by fetch_docx.sh. Use the actual values when creating vault folders.

### Pitfall 5: Smart Connections data.json vs smart_env.json confusion

**What goes wrong:** Putting Smart Connections settings in `.obsidian/plugins/smart-connections/data.json` (the plugin's minimal install record) instead of `.smart-env/smart_env.json` (the actual settings file).
**Why it happens:** The plugin's standard Obsidian data.json contains only `installed_at` and `last_version` — it's NOT the settings file.
**How to avoid:** Settings live at `.smart-env/smart_env.json` in the vault root (NOT inside `.obsidian/`). Confirmed from actual vault at `/mnt/sda1/KISA's Space/`.

### Pitfall 6: Python < 3.11 with tomllib import error

**What goes wrong:** On Ubuntu 22.04, default Python is 3.10. `import tomllib` fails. The existing scripts handle this gracefully with a warning, but if install.sh doesn't account for this, users get confusing errors.
**Why it happens:** tomllib entered stdlib in Python 3.11 (released October 2022).
**How to avoid:** The scripts already handle this (fall back to tomli with warning). install.sh should check Python version and warn if < 3.11, but NOT fail — the fallback works. Optional: install `pip3 install tomli` if Python < 3.11 detected.

### Pitfall 7: README copy-paste commands not idempotent from user's perspective

**What goes wrong:** User sends Claude the install command, it works. Then they send the process command, but they're not in the right directory.
**Why it happens:** Commands assume `cwd = repo root` but Claude starts fresh each session.
**How to avoid:** README commands should either be absolute paths or include a `cd /path/to/ObsidianDataWeave &&` prefix. The CLAUDE.md skill section hardcodes `cd ${repo_dir}` for exactly this reason.

---

## Code Examples

### install.sh Skeleton

```bash
#!/usr/bin/env bash
# ObsidianDataWeave installer
# Idempotent — safe to re-run
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

# ── Detect package manager ────────────────────────────────────
detect_pkg_manager() {
    if command -v pacman &>/dev/null; then echo "pacman"
    elif command -v brew &>/dev/null; then echo "brew"
    elif command -v apt-get &>/dev/null; then echo "apt"
    elif command -v dnf &>/dev/null; then echo "dnf"
    else echo "unknown"
    fi
}
PKG_MGR=$(detect_pkg_manager)
echo "Detected package manager: $PKG_MGR"

# ── Install rclone ────────────────────────────────────────────
if command -v rclone &>/dev/null; then
    echo "rclone already installed: $(rclone --version | head -1)"
else
    case "$PKG_MGR" in
        pacman) sudo pacman -S --noconfirm rclone ;;
        brew)   brew install rclone ;;
        apt)    sudo apt-get install -y rclone ;;
        dnf)    sudo dnf install -y rclone ;;
        *)      echo "Installing rclone via official script..."
                curl https://rclone.org/install.sh | sudo bash ;;
    esac
fi

# ── Install python-docx ───────────────────────────────────────
if python3 -c "import docx" 2>/dev/null; then
    echo "python-docx already installed"
else
    if [ "$PKG_MGR" = "pacman" ]; then
        sudo pacman -S --noconfirm python-lxml 2>/dev/null || true
        pip3 install --break-system-packages python-docx
    else
        pip3 install python-docx
    fi
fi

# ── Create config.toml ────────────────────────────────────────
if [ -f "config.toml" ]; then
    echo "config.toml already exists — skipping"
else
    echo ""
    echo "=== Configuration Setup ==="
    read -rp "Obsidian vault path (absolute): " VAULT_PATH
    read -rp "rclone remote name [gdrive:]: " RCLONE_REMOTE
    RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive:}"

    sed -e "s|/path/to/your/obsidian/vault|${VAULT_PATH}|g" \
        -e "s|remote = \"gdrive:\"|remote = \"${RCLONE_REMOTE}\"|g" \
        config.example.toml > config.toml

    echo "config.toml created"
fi

# ── Create vault folders ──────────────────────────────────────
VAULT_PATH=$(python3 - "$REPO_DIR/config.toml" <<'PYEOF'
import sys
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        print(""); sys.exit(0)
with open(sys.argv[1], "rb") as f:
    d = tomllib.load(f)
print(d.get("vault", {}).get("vault_path", ""))
PYEOF
)

if [ -n "$VAULT_PATH" ] && [ -d "$VAULT_PATH" ]; then
    NOTES=$(python3 - "$REPO_DIR/config.toml" vault notes_folder "Research & Insights" <<'PYEOF'
import sys
try:
    import tomllib
except ImportError:
    print(sys.argv[3]); sys.exit(0)
with open(sys.argv[1], "rb") as f:
    d = tomllib.load(f)
print(d.get(sys.argv[2], {}).get(sys.argv[3], sys.argv[4]))
PYEOF
    )
    # Similar for moc_folder and source_folder...
    mkdir -p "$VAULT_PATH/$NOTES"
    echo "Vault folders created"
elif [ -n "$VAULT_PATH" ]; then
    echo "WARNING: vault_path '$VAULT_PATH' does not exist. Create it first, then re-run."
fi

# ── Register Claude Code skill ────────────────────────────────
CLAUDE_MD="$HOME/.claude/CLAUDE.md"
SKILL_MARKER="## ObsidianDataWeave Pipeline"

if [ -f "$CLAUDE_MD" ] && grep -qF "$SKILL_MARKER" "$CLAUDE_MD"; then
    echo "Claude Code skill already registered"
else
    cat >> "$CLAUDE_MD" <<SKILL

---

## ObsidianDataWeave Pipeline

When the user says "process [document].docx", "atomize document", "run the pipeline", or "import to Obsidian":

\`\`\`bash
cd ${REPO_DIR} && python3 scripts/process.py "Filename.docx"
\`\`\`

Skip Google Drive fetch (docx already downloaded):
\`\`\`bash
cd ${REPO_DIR} && python3 scripts/process.py "Filename.docx" --skip-fetch
\`\`\`

Config: \`${REPO_DIR}/config.toml\`
SKILL
    echo "Claude Code skill registered in $CLAUDE_MD"
fi

echo ""
echo "=== Setup complete ==="
echo "Next: send Claude the README Quick Start commands"
```

### README Quick Start Commands (what user copies to Claude)

```
1. Install:
   Run `bash install.sh` in the ObsidianDataWeave directory

2. Configure rclone (if not done):
   Run `rclone config` to set up your Google Drive remote named `gdrive:`

3. Process your first document:
   Run `python3 scripts/process.py "YourDocument.docx"` from the project root
```

### Atomic Note Example (templates/Notes/Atomic Note Example.md)

```markdown
---
tags:
  - productivity/zettelkasten
  - productivity/pkm
date: 2026-02-26
source_doc: "Example Document.docx"
note_type: atomic
---

# Atomic Note Principle

An atomic note contains exactly one idea — complete enough to understand without reading any other note. The reader who encounters this note should grasp the concept fully from the note alone.

This principle improves [[Semantic Search with Smart Connections]] because single-idea notes produce precise vector embeddings. A note mixing three concepts generates a blurred vector that ranks poorly against focused queries.

Replace direct document excerpts with your own phrasing. Paraphrasing forces genuine comprehension and produces cleaner embeddings than copy-pasted text.
```

### MOC Example (templates/MOCs/Topic Map — MOC.md)

```markdown
---
tags:
  - productivity/moc
  - productivity/pkm
date: 2026-02-26
source_doc: "Example Document.docx"
note_type: moc
---

# Topic Map — MOC

## Core Concepts

- [[Atomic Note Principle]]
- [[Semantic Search with Smart Connections]]

## Methodology

- [[Zettelkasten Folder Structure]]
- [[MOC as Navigation Hub]]
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Smart Connections settings in data.json | Settings in .smart-env/smart_env.json | Smart Connections v4.x | Templates must target .smart-env/, not .obsidian/plugins/ |
| pip install globally | pip install --break-system-packages (Arch) | PEP 668 / ~2023 | install.sh must branch on pacman detection |
| tomllib third-party (tomli) | tomllib in stdlib | Python 3.11 (Oct 2022) | Python 3.10 users need `pip install tomli` warning |

**Deprecated/outdated:**
- Smart Connections `data.json` as the settings file: it now only stores `installed_at` and `last_version`. Real settings are in `.smart-env/smart_env.json`.

---

## Open Questions

1. **Gitignore for generated staging files outside /tmp/**
   - What we know: Current `.gitignore` includes `/tmp/` which covers the default `staging_dir = /tmp/dw/staging`
   - What's unclear: If a user changes `staging_dir` to a path inside the repo (unlikely but possible), those files would not be gitignored
   - Recommendation: Add `*.atom-plan.json` and `*-parsed.json` patterns to .gitignore as safety net; also add `.venv/` and `venv/` for users who create virtual environments

2. **Python version check in install.sh**
   - What we know: Python 3.10 works (scripts fall back gracefully); Python 3.11+ has tomllib
   - What's unclear: Should install.sh fail hard on Python < 3.10 or warn-and-continue?
   - Recommendation: Check `python3 --version`, warn if < 3.11 (suggest upgrade or `pip install tomli`), but do NOT fail — the fallback code is already in place

3. **rclone remote validation**
   - What we know: install.sh prompts for rclone remote name; `rclone config` must be run separately
   - What's unclear: Should install.sh verify the rclone remote exists by running `rclone listremotes`?
   - Recommendation: After creating config.toml, run `rclone listremotes` and warn if the configured remote name doesn't appear. Non-blocking: user may not have completed rclone OAuth yet.

---

## .gitignore Recommendations (Claude's Discretion)

The existing .gitignore is solid. Add these patterns:

```gitignore
# Virtual environments (if user creates one for isolation)
.venv/
venv/
env/

# Editor/IDE configs (personal preference files)
.idea/
.vscode/
*.swp
*.swo

# Staging artifacts (safety net if staging_dir changed from /tmp/)
*-parsed.json
*-atom-plan.json
proposed-tags.md

# Logs
*.log
```

**What NOT to add:** `/tmp/` is already there. `config.toml` is already there. `processed.json` is already there.

---

## Sources

### Primary (HIGH confidence)
- Direct inspection of running system: `pip3 install --break-system-packages`, python-docx 1.2.0 with lxml 6.0.2 confirmed at `~/.local/lib/python3.14/site-packages`
- `/home/kosya/vibecoding/ObsidianDataWeave/scripts/generate_notes.py` — frontmatter schema v1 locked
- `/home/kosya/vibecoding/ObsidianDataWeave/scripts/fetch_docx.sh` — package manager detection pattern (pacman in existing code)
- `/mnt/sda1/KISA's Space/.smart-env/smart_env.json` — Smart Connections v4.1.8 real config format
- `~/.claude/CLAUDE.md` — skill registration format (append sections separated by `---`)
- `https://rclone.org/install.sh` — official rclone fallback script (confirmed reachable)

### Secondary (MEDIUM confidence)
- Python 3.11 release notes: tomllib added to stdlib — multiple sources confirm October 2022
- PEP 668 externally-managed-environment: Implemented in Arch/Manjaro pip — confirmed by live pip error on this system
- Smart Connections manifest.json: version 4.1.8, author brianpetro — confirms .smart-env format is current

### Tertiary (LOW confidence)
- Ubuntu 22.04 ships Python 3.10 as default — widely documented but not verified on this machine
- `lxml` has pre-built wheels for all major Linux distributions and macOS — pip documentation claim, consistent with observed wheel install

---

## Metadata

**Confidence breakdown:**
- install.sh patterns: HIGH — tested pip behavior, package detection, CLAUDE.md format verified from real files
- Obsidian templates: HIGH — frontmatter schema from locked source (generate_notes.py), MOC format from taxonomy.md
- Smart Connections config: HIGH — read from real active vault `.smart-env/smart_env.json`
- README structure: HIGH — locked decisions from CONTEXT.md, no ambiguity
- Python cross-platform: MEDIUM — Manjaro confirmed, Ubuntu 22.04 Python 3.10 claim from training data

**Research date:** 2026-02-26
**Valid until:** 2026-03-28 (30 days — stable tooling)
