#!/usr/bin/env bash
# install.sh — Cross-platform idempotent installer for ObsidianDataWeave
# Supports: pacman (Arch/Manjaro), brew (macOS), apt (Debian/Ubuntu), dnf (Fedora/RHEL)
# Usage: bash install.sh

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

# ── Package manager detection ─────────────────────────────────────────────────

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

PKG_MANAGER=$(detect_pkg_manager)
echo ""
echo "=== ObsidianDataWeave Installer ==="
echo "Detected package manager: ${PKG_MANAGER}"
echo "Repository: ${REPO_DIR}"
echo ""

# ── Python version check ──────────────────────────────────────────────────────

check_python() {
    echo "=== Step 0: Python version check ==="
    if ! command -v python3 &>/dev/null; then
        echo "ERROR: python3 not found. Please install Python 3.10 or later." >&2
        exit 1
    fi
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
    echo "Python version: ${PYTHON_VERSION}"
    if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]; }; then
        echo "ERROR: Python 3.10+ required. Found ${PYTHON_VERSION}." >&2
        exit 1
    fi
    if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]; then
        echo "WARNING: Python 3.10 detected. Scripts will work but consider upgrading to 3.11+ for native tomllib support."
        PYTHON_NEEDS_TOMLI=true
    else
        PYTHON_NEEDS_TOMLI=false
    fi
    echo "Python check passed."
}

# ── rclone installation ───────────────────────────────────────────────────────

install_rclone() {
    echo ""
    echo "=== Step 1: Install rclone ==="
    if command -v rclone &>/dev/null; then
        echo "rclone already installed: $(rclone --version 2>&1 | head -1)"
        return
    fi
    echo "Installing rclone..."
    case "$PKG_MANAGER" in
        pacman)
            sudo pacman -S --noconfirm rclone
            ;;
        brew)
            brew install rclone
            ;;
        apt)
            sudo apt-get update -qq && sudo apt-get install -y rclone
            ;;
        dnf)
            sudo dnf install -y rclone
            ;;
        unknown)
            echo "Unknown package manager. Installing rclone via official script..."
            curl https://rclone.org/install.sh | sudo bash
            ;;
    esac
    echo "rclone installed: $(rclone --version 2>&1 | head -1)"
}

# ── python-docx installation ──────────────────────────────────────────────────

install_python_docx() {
    echo ""
    echo "=== Step 2: Install python-docx ==="
    if python3 -c "import docx" 2>/dev/null; then
        echo "python-docx already installed."
    else
        echo "Installing python-docx..."
        case "$PKG_MANAGER" in
            pacman)
                # lxml C extension may need the system package on Arch/Manjaro
                sudo pacman -S --noconfirm python-lxml 2>/dev/null || true
                pip3 install --break-system-packages python-docx
                ;;
            *)
                pip3 install python-docx
                ;;
        esac
        echo "python-docx installed."
    fi

    # Install tomli backport for Python 3.10 (stdlib tomllib added in 3.11)
    if [ "${PYTHON_NEEDS_TOMLI:-false}" = "true" ]; then
        if python3 -c "import tomli" 2>/dev/null; then
            echo "tomli already installed."
        else
            echo "Installing tomli (backport for Python < 3.11)..."
            case "$PKG_MANAGER" in
                pacman)
                    pip3 install --break-system-packages tomli
                    ;;
                *)
                    pip3 install tomli
                    ;;
            esac
            echo "tomli installed."
        fi
    fi
}

# ── config.toml creation ──────────────────────────────────────────────────────

create_config() {
    echo ""
    echo "=== Step 3: Create config.toml ==="
    if [ -f "${REPO_DIR}/config.toml" ]; then
        echo "config.toml already exists — skipping."
        return
    fi

    echo "Creating config.toml from config.example.toml..."
    echo ""

    read -rp "Obsidian vault path (absolute, e.g. /home/user/MyVault): " VAULT_PATH
    read -rp "rclone remote name [gdrive:]: " RCLONE_REMOTE
    RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive:}"
    # Ensure remote name ends with colon
    [[ "$RCLONE_REMOTE" != *: ]] && RCLONE_REMOTE="${RCLONE_REMOTE}:"

    # Escape special characters in VAULT_PATH for sed (forward slashes)
    VAULT_PATH_ESC=$(printf '%s\n' "$VAULT_PATH" | sed 's/[\/&]/\\&/g')

    sed \
        -e "s|/path/to/your/obsidian/vault|${VAULT_PATH_ESC}|g" \
        -e "s|gdrive:|${RCLONE_REMOTE}|g" \
        "${REPO_DIR}/config.example.toml" > "${REPO_DIR}/config.toml"

    echo "config.toml created."

    # Warn if rclone remote is not configured yet
    if command -v rclone &>/dev/null; then
        if ! rclone listremotes 2>/dev/null | grep -qF "${RCLONE_REMOTE}"; then
            echo "WARNING: rclone remote '${RCLONE_REMOTE}' not found in 'rclone listremotes'."
            echo "  Run: rclone config  — then add your remote before using fetch_docx.sh"
        else
            echo "rclone remote '${RCLONE_REMOTE}' confirmed."
        fi
    fi
}

# ── vault subfolder creation ──────────────────────────────────────────────────

create_vault_folders() {
    echo ""
    echo "=== Step 4: Create vault subfolders ==="
    if [ ! -f "${REPO_DIR}/config.toml" ]; then
        echo "WARNING: config.toml not found — skipping vault folder creation."
        return
    fi

    # Read vault config using inline Python (tomllib stdlib in 3.11+, tomli backport for 3.10)
    VAULT_INFO=$(python3 -c "
import sys
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        print('TOMLLIB_MISSING')
        sys.exit(0)
with open('${REPO_DIR}/config.toml', 'rb') as f:
    cfg = tomllib.load(f)
vault = cfg.get('vault', {})
vault_path = vault.get('vault_path', '')
notes_folder = vault.get('notes_folder', 'Research & Insights')
moc_folder = vault.get('moc_folder', 'Guides & Overviews')
source_folder = vault.get('source_folder', 'Sources')
print(vault_path)
print(notes_folder)
print(moc_folder)
print(source_folder)
" 2>/dev/null)

    if [ "$VAULT_INFO" = "TOMLLIB_MISSING" ] || [ -z "$VAULT_INFO" ]; then
        echo "WARNING: Could not read config.toml (tomllib/tomli not available)."
        echo "  Install tomli: pip3 install tomli"
        return
    fi

    VAULT_PATH=$(echo "$VAULT_INFO" | sed -n '1p')
    NOTES_FOLDER=$(echo "$VAULT_INFO" | sed -n '2p')
    MOC_FOLDER=$(echo "$VAULT_INFO" | sed -n '3p')
    SOURCE_FOLDER=$(echo "$VAULT_INFO" | sed -n '4p')

    if [ ! -d "$VAULT_PATH" ]; then
        echo "WARNING: Vault path does not exist: ${VAULT_PATH}"
        echo "  Create your Obsidian vault first, then run: bash install.sh"
        echo "  (Skipping folder creation — config.toml is still valid)"
        return
    fi

    echo "Vault path: ${VAULT_PATH}"
    for FOLDER in "$NOTES_FOLDER" "$MOC_FOLDER" "$SOURCE_FOLDER"; do
        FULL_PATH="${VAULT_PATH}/${FOLDER}"
        if [ -d "$FULL_PATH" ]; then
            echo "  [exists]  ${FOLDER}"
        else
            mkdir -p "$FULL_PATH"
            echo "  [created] ${FOLDER}"
        fi
    done
}

# ── Claude Code skill registration ────────────────────────────────────────────

register_claude_skill() {
    echo ""
    echo "=== Step 5: Register ObsidianDataWeave in Claude Code ==="
    CLAUDE_DIR="${HOME}/.claude"
    CLAUDE_MD="${CLAUDE_DIR}/CLAUDE.md"

    # Create ~/.claude/ directory if it doesn't exist
    if [ ! -d "$CLAUDE_DIR" ]; then
        mkdir -p "$CLAUDE_DIR"
        echo "Created ${CLAUDE_DIR}"
    fi

    # Create CLAUDE.md if it doesn't exist
    if [ ! -f "$CLAUDE_MD" ]; then
        touch "$CLAUDE_MD"
        echo "Created ${CLAUDE_MD}"
    fi

    # Guard: skip if already registered
    if grep -qF "## ObsidianDataWeave Pipeline" "$CLAUDE_MD"; then
        echo "ObsidianDataWeave already registered in ${CLAUDE_MD} — skipping."
        return
    fi

    # Append skill registration section
    cat >> "$CLAUDE_MD" << SKILL_EOF


## ObsidianDataWeave Pipeline

Converts research .docx documents into atomic Obsidian notes via the full pipeline.

### Trigger phrases
- "process [document].docx"
- "atomize document"
- "run the pipeline"
- "import to Obsidian"
- "convert docx to notes"

### Usage

\`\`\`bash
# Full pipeline (fetch from Google Drive, parse, atomize, write to vault):
cd ${REPO_DIR} && python3 scripts/process.py "Document.docx"

# Skip fetch (docx already in staging area):
cd ${REPO_DIR} && python3 scripts/process.py "Document.docx" --skip-fetch

# Start from existing atom plan JSON:
cd ${REPO_DIR} && python3 scripts/process.py /path/to/atom-plan.json --from-plan
\`\`\`

### Configuration
- Config: ${REPO_DIR}/config.toml
- SKILL.md: ${REPO_DIR}/SKILL.md
SKILL_EOF

    echo "Registered ObsidianDataWeave in ${CLAUDE_MD}"
}

# ── Main ──────────────────────────────────────────────────────────────────────

main() {
    check_python
    install_rclone
    install_python_docx
    create_config
    create_vault_folders
    register_claude_skill

    echo ""
    echo "=== Setup complete ==="
    echo ""
    echo "Next steps:"
    echo "  1. Open README.md for Quick Start commands"
    echo "  2. If rclone remote not configured: run 'rclone config'"
    echo "  3. Process a document: python3 scripts/process.py \"Document.docx\""
    echo ""
}

main
