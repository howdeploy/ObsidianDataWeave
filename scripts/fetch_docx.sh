#!/usr/bin/env bash
# fetch_docx.sh — Download a named .docx from Google Drive via rclone
# Usage: fetch_docx.sh <filename>
# Outputs: local file path to stdout (for piping)
# Diagnostics: written to stderr

set -euo pipefail

# ── Argument validation ────────────────────────────────────────────────────────
if [ $# -lt 1 ] || [ -z "${1:-}" ]; then
    echo "Usage: fetch_docx.sh <filename>" >&2
    echo "Example: fetch_docx.sh \"My Research Document.docx\"" >&2
    exit 1
fi

FILENAME="$1"

# ── Config reading ─────────────────────────────────────────────────────────────
# Resolve config.toml: project-local takes precedence over ~/.config location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "${SCRIPT_DIR}")"
LOCAL_CONFIG="${PROJECT_ROOT}/config.toml"

# parse_config <section> <key> <default>
# Uses python3 tomllib (Python 3.11+ stdlib) for reliable TOML parsing.
parse_config() {
    local section="$1"
    local key="$2"
    local default="$3"
    local config_file="${LOCAL_CONFIG}"

    if [ ! -f "${config_file}" ]; then
        echo "${default}"
        return
    fi

    python3 - "${config_file}" "${section}" "${key}" "${default}" <<'PYEOF'
import sys, tomllib
config_path, section, key, default = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
try:
    with open(config_path, "rb") as f:
        d = tomllib.load(f)
    print(d.get(section, {}).get(key, default))
except Exception:
    print(default)
PYEOF
}

# Read rclone remote and staging dir from config (or use fallbacks)
if [ ! -f "${LOCAL_CONFIG}" ]; then
    echo "WARNING: config.toml not found at ${LOCAL_CONFIG}" >&2
    echo "WARNING: Using default remote 'gdrive:' and staging '/tmp/dw/staging'" >&2
    RCLONE_REMOTE="gdrive:"
    STAGING_DIR="/tmp/dw/staging"
else
    RCLONE_REMOTE="$(parse_config "rclone" "remote" "gdrive:")"
    STAGING_DIR="$(parse_config "rclone" "staging_dir" "/tmp/dw/staging")"
fi

# ── Staging directory setup ────────────────────────────────────────────────────
mkdir -p "${STAGING_DIR}"

# ── Build rclone source path ───────────────────────────────────────────────────
# Strip trailing colon/slash from remote, then reattach with colon separator.
# Handles both "gdrive:" and "gdrive" remote names consistently.
REMOTE_BASE="${RCLONE_REMOTE%:}"
SOURCE="${REMOTE_BASE}:${FILENAME}"
DEST="${STAGING_DIR}/${FILENAME}"

echo "Fetching: ${FILENAME}" >&2
echo "Source:   ${SOURCE}" >&2
echo "Dest:     ${DEST}" >&2

# ── Execute rclone copyto ──────────────────────────────────────────────────────
# Use list-form (no eval/shell=True) to handle spaces, Cyrillic, and colons safely.
RCLONE_STDERR_FILE=$(mktemp)
RCLONE_EXIT=0

rclone copyto "${SOURCE}" "${DEST}" 2>"${RCLONE_STDERR_FILE}" || RCLONE_EXIT=$?

if [ "${RCLONE_EXIT}" -eq 0 ]; then
    echo "Downloaded to: ${DEST}" >&2
    # Emit local path to stdout for piping into parse_docx.py
    echo "${DEST}"
else
    RCLONE_STDERR_CONTENT=$(cat "${RCLONE_STDERR_FILE}")
    rm -f "${RCLONE_STDERR_FILE}"

    if [ "${RCLONE_EXIT}" -eq 3 ]; then
        echo "ERROR: File not found on Google Drive: ${FILENAME}" >&2
        echo "" >&2
        echo "Available .docx files in ${RCLONE_REMOTE}:" >&2
        rclone lsf "${RCLONE_REMOTE}" --max-depth 1 --include "*.docx" 2>/dev/null >&2 || \
            echo "(Could not list remote files)" >&2
    else
        echo "ERROR: rclone failed with exit code ${RCLONE_EXIT}" >&2
        if [ -n "${RCLONE_STDERR_CONTENT}" ]; then
            echo "${RCLONE_STDERR_CONTENT}" >&2
        fi
    fi

    exit "${RCLONE_EXIT}"
fi

rm -f "${RCLONE_STDERR_FILE}"
