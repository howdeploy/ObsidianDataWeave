#!/usr/bin/env bash
# install.sh — one-command setup for ObsidianDataWeave
#
# One-liner install:
#   git clone https://github.com/<user>/ObsidianDataWeave && cd ObsidianDataWeave && bash install.sh --vault-path "/path/to/vault"
#
# Claude Code prompt:
#   "Clone github.com/<user>/ObsidianDataWeave and run install.sh with my vault at /path/to/vault"

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="claude"
VAULT_PATH=""
RCLONE_REMOTE="gdrive:"
SKILL_DIR="${HOME}/.claude/skills/obsidian-dataweave"

usage() {
    cat <<'EOF'
Usage:
  bash install.sh [--vault-path /abs/path] [--rclone-remote name:] [--mode local|claude|codex]

Modes:
  claude  (default) Install locally + register global Claude Code skill.
  codex   Install locally + verify Codex AGENTS.md.
  local   Install locally only (deps + config).

Examples:
  bash install.sh --vault-path "/home/user/Obsidian Vault"
  bash install.sh --mode codex --vault-path "/home/user/Vault"
  bash install.sh --mode local
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)       MODE="${2:-}"; shift 2 ;;
        --vault-path) VAULT_PATH="${2:-}"; shift 2 ;;
        --rclone-remote) RCLONE_REMOTE="${2:-}"; shift 2 ;;
        --help|-h)    usage; exit 0 ;;
        *) echo "ERROR: Unknown argument: $1" >&2; usage >&2; exit 1 ;;
    esac
done

if [[ "$MODE" != "local" && "$MODE" != "claude" && "$MODE" != "codex" ]]; then
    echo "ERROR: Unsupported mode '$MODE'" >&2
    usage >&2
    exit 1
fi

[[ "$RCLONE_REMOTE" != *: ]] && RCLONE_REMOTE="${RCLONE_REMOTE}:"

# ── Step 1: Python ──────────────────────────────────────────────────────────

echo "== Python =="
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 not found." >&2
    exit 1
fi
python3 --version

echo ""
echo "== Dependencies =="
if python3 -c "import docx, yaml" >/dev/null 2>&1; then
    echo "Already installed."
else
    pip3 install -r "${REPO_DIR}/requirements.txt"
fi

# ── Step 2: config.toml ─────────────────────────────────────────────────────

echo ""
echo "== Config =="
config_path="${REPO_DIR}/config.toml"
if [[ -f "$config_path" ]]; then
    echo "config.toml already exists."
else
    cp "${REPO_DIR}/config.example.toml" "$config_path"
    if [[ -n "$VAULT_PATH" ]]; then
        escaped=$(printf '%s\n' "$VAULT_PATH" | sed 's/[\/&]/\\&/g')
        sed -i \
            -e "s|/path/to/your/obsidian/vault|${escaped}|g" \
            -e "s|gdrive:|${RCLONE_REMOTE}|g" \
            "$config_path"
        echo "Created config.toml with vault: ${VAULT_PATH}"
    else
        echo "Created config.toml from template — fill in vault_path before use."
    fi
fi

# ── Step 3: Verify repo files ───────────────────────────────────────────────

echo ""
echo "== Repository files =="
for path in AGENTS.md SKILL.md SKILL_PERSONAL.md rules/atomization.md rules/taxonomy.md rules/personal_notes.md tags.yaml; do
    if [[ -f "${REPO_DIR}/${path}" ]]; then
        echo "  present: ${path}"
    else
        echo "  ERROR: missing ${path}" >&2
        exit 1
    fi
done

# ── Step 4: Mode-specific registration ──────────────────────────────────────

register_global_skill() {
    echo ""
    echo "== Global skill registration =="

    mkdir -p "${SKILL_DIR}/references"

    # Generate global SKILL.md with absolute paths to this repo
    cat > "${SKILL_DIR}/SKILL.md" <<SKILL_EOF
---
description: "Obsidian notes processing: enrich/atomize with Zettelkasten + .docx import"
trigger_phrases:
  - process note
  - enrich note
  - atomize note
  - docx import
  - zettelkasten rules
  - обработай заметку
  - обогати заметку
  - разбей заметку
  - обработай документ
  - импортируй документ
  - правила заметок
---

# ObsidianDataWeave

Obsidian note processing pipeline: Zettelkasten atomization, enrichment, and .docx import.

Repository: ${REPO_DIR}

## Commands

Process an existing note (auto-detects enrich/atomize):
\`\`\`bash
cd ${REPO_DIR} && python3 scripts/process_note.py "Note Title"
\`\`\`

Import a .docx document into the vault:
\`\`\`bash
cd ${REPO_DIR} && python3 scripts/process.py "Document.docx"
\`\`\`

Preview without changes:
\`\`\`bash
cd ${REPO_DIR} && python3 scripts/process_note.py "Note Title" --dry-run
\`\`\`

Non-interactive mode (safe for agents):
\`\`\`bash
cd ${REPO_DIR} && python3 scripts/process.py "Doc.docx" --non-interactive --on-conflict skip
cd ${REPO_DIR} && python3 scripts/process_note.py "Note" --mode atomize --non-interactive --on-conflict skip
\`\`\`

Dedup review:
\`\`\`bash
cd ${REPO_DIR} && python3 scripts/dedup_vault.py --dry-run
\`\`\`

Check setup:
\`\`\`bash
cd ${REPO_DIR} && python3 scripts/doctor.py
\`\`\`

## Rules

For detailed Zettelkasten rules, load the reference files:
- \`references/atomization-rules.md\` — note splitting
- \`references/taxonomy-rules.md\` — tags, wikilinks, MOC, frontmatter
- \`references/personal-notes-rules.md\` — personal note specifics
- \`references/tags.yaml\` — canonical tag taxonomy

## Agent Contract

Full agent contract: \`${REPO_DIR}/AGENTS.md\`
SKILL_EOF

    # Symlink references (auto-update on git pull)
    ln -sf "${REPO_DIR}/rules/atomization.md" "${SKILL_DIR}/references/atomization-rules.md"
    ln -sf "${REPO_DIR}/rules/taxonomy.md" "${SKILL_DIR}/references/taxonomy-rules.md"
    ln -sf "${REPO_DIR}/rules/personal_notes.md" "${SKILL_DIR}/references/personal-notes-rules.md"
    ln -sf "${REPO_DIR}/tags.yaml" "${SKILL_DIR}/references/tags.yaml"

    echo "Skill registered at: ${SKILL_DIR}"
}

register_claude_md() {
    echo ""
    echo "== Claude Code CLAUDE.md =="
    local claude_md="${HOME}/.claude/CLAUDE.md"
    mkdir -p "${HOME}/.claude"
    touch "$claude_md"

    # Remove old block if present, then add new one
    if grep -qF "## ObsidianDataWeave" "$claude_md"; then
        # Remove existing block (from ## ObsidianDataWeave to next ## or EOF)
        python3 -c "
import re, sys
with open('$claude_md', 'r') as f:
    content = f.read()
# Remove the ObsidianDataWeave section
content = re.sub(
    r'\n*## ObsidianDataWeave[^\n]*\n.*?(?=\n## |\Z)',
    '',
    content,
    flags=re.DOTALL
)
with open('$claude_md', 'w') as f:
    f.write(content.strip() + '\n')
"
        echo "Removed old ObsidianDataWeave block."
    fi

    cat >> "$claude_md" <<CLAUDE_EOF

## ObsidianDataWeave

Obsidian note processing: enrich/atomize by Zettelkasten + .docx import.

- **Skill:** \`~/.claude/skills/obsidian-dataweave/SKILL.md\`
- **Repo:** \`${REPO_DIR}\`

### Trigger phrases
- "process note X" / "обработай заметку X"
- "enrich note X" / "atomize note X"
- "import document X.docx" / "обработай документ X.docx"
- "zettelkasten rules" / "правила заметок"
CLAUDE_EOF

    echo "Registered in ${claude_md}"
}

case "$MODE" in
    claude)
        register_global_skill
        register_claude_md
        ;;
    codex)
        echo ""
        echo "== Codex integration =="
        echo "Codex uses repo-local AGENTS.md — no global registration needed."
        ;;
    local)
        :
        ;;
esac

# ── Done ─────────────────────────────────────────────────────────────────────

echo ""
echo "== Done =="
echo ""
echo "Next steps:"
echo "  1. Verify setup:    cd ${REPO_DIR} && python3 scripts/doctor.py"
if [[ "$MODE" == "claude" ]]; then
echo "  2. Use from anywhere: tell Claude 'process note \"My Note\"' or 'import document X.docx'"
elif [[ "$MODE" == "codex" ]]; then
echo "  2. From the repo:   python3 scripts/process.py \"Document.docx\""
else
echo "  2. Process a doc:   python3 scripts/process.py \"Document.docx\""
fi
