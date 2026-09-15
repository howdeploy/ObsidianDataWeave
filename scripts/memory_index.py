"""memory_index.py — FTS5 full-text memory over the Obsidian vault.

Lexical search instead of embeddings: a single SQLite database with an FTS5
table indexes every vault note (title / headings / tags / body). Replaces the
Smart Connections embedding layer (now legacy) with a zero-dependency,
fully local index.

The database lives OUTSIDE the vault (so vault sync never sees it):
    <db_dir>/<vault-slug>-<hash>.db        db_dir default: ~/.cache/obsidian-dataweave

Usage:
    python3 scripts/memory_index.py build                  # full (re)index
    python3 scripts/memory_index.py update                 # incremental by mtime/size
    python3 scripts/memory_index.py search "query" [--limit 10] [--prefix]
                                          [--folder Notes] [--tag ai] [--json] [--raw]
    python3 scripts/memory_index.py status

Config (config.toml):
    [memory]
    enabled = true
    db_dir = ""              # empty → ~/.cache/obsidian-dataweave (XDG aware)
    tokenizer = "unicode61"  # or "trigram" (substring matching, needs SQLite >= 3.34)
    auto_update = true       # vault_writer refreshes the index after each write
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

try:
    from scripts.config import load_config
    from scripts.scan_vault import SKIP_DIRS
except ModuleNotFoundError:
    from config import load_config
    from scan_vault import SKIP_DIRS

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is a hard repo dependency
    yaml = None

DEFAULT_DB_DIR = Path.home() / ".cache" / "obsidian-dataweave"
VALID_TOKENIZERS = ("unicode61", "trigram")
TRIGRAM_MIN_SQLITE = (3, 34, 0)

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
_HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$", re.MULTILINE)


# ── config helpers ────────────────────────────────────────────────────────────


def memory_config(config: dict) -> dict:
    """Normalize the [memory] section with defaults."""
    raw = config.get("memory", {}) or {}
    tokenizer = str(raw.get("tokenizer", "unicode61")).strip() or "unicode61"
    if tokenizer not in VALID_TOKENIZERS:
        print(
            f"WARNING: [memory].tokenizer={tokenizer!r} unknown — using unicode61",
            file=sys.stderr,
        )
        tokenizer = "unicode61"
    return {
        "enabled": bool(raw.get("enabled", True)),
        "db_dir": str(raw.get("db_dir", "") or ""),
        "tokenizer": tokenizer,
        "auto_update": bool(raw.get("auto_update", True)),
    }


def vault_path_from(config: dict) -> Path:
    vault = config.get("vault", {}).get("vault_path", "")
    if not vault or vault == "/path/to/your/obsidian/vault":
        raise ValueError("vault_path is not configured in config.toml")
    return Path(vault).expanduser()


def db_path_for_vault(vault_path: Path, db_dir: str = "") -> Path:
    """Stable per-vault database path outside the vault."""
    base = Path(db_dir).expanduser() if db_dir else DEFAULT_DB_DIR
    digest = hashlib.sha1(str(vault_path.resolve()).encode("utf-8")).hexdigest()[:10]
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", vault_path.name).strip("-") or "vault"
    return base / f"{slug}-{digest}.db"


# ── sqlite / schema ───────────────────────────────────────────────────────────


def fts5_available() -> bool:
    try:
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        conn.close()
        return True
    except sqlite3.OperationalError:
        return False


def resolve_tokenizer(name: str) -> str:
    """Map config tokenizer to the FTS5 tokenize= clause (with fallback)."""
    if name == "trigram":
        if sqlite3.sqlite_version_info >= TRIGRAM_MIN_SQLITE:
            return "trigram"
        print(
            f"WARNING: trigram tokenizer needs SQLite >= 3.34 "
            f"(found {sqlite3.sqlite_version}) — falling back to unicode61",
            file=sys.stderr,
        )
    return "unicode61 remove_diacritics 2"


def open_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def ensure_schema(conn: sqlite3.Connection, tokenizer: str) -> None:
    """Create tables if missing. A tokenizer change forces a rebuild."""
    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    row = conn.execute("SELECT value FROM meta WHERE key='tokenizer'").fetchone()
    if row and row[0] != tokenizer:
        print(
            f"INFO: tokenizer changed {row[0]!r} → {tokenizer!r} — rebuilding index",
            file=sys.stderr,
        )
        conn.execute("DROP TABLE IF EXISTS notes_fts")
        conn.execute("DROP TABLE IF EXISTS files")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS files ("
        " path TEXT PRIMARY KEY, mtime REAL NOT NULL, size INTEGER NOT NULL)"
    )
    conn.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5("
        " title, headings, tags, body, path UNINDEXED, folder UNINDEXED,"
        f" tokenize=\"{resolve_tokenizer(tokenizer)}\", prefix='2 3')"
    )
    conn.execute(
        "INSERT INTO meta(key, value) VALUES('tokenizer', ?)"
        " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (tokenizer,),
    )
    conn.commit()


# ── note parsing ──────────────────────────────────────────────────────────────


def parse_note(md_file: Path, vault_path: Path) -> dict:
    """Extract indexable fields from one markdown note. Never raises."""
    try:
        text = md_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""

    tags: list[str] = []
    body = text
    match = _FRONTMATTER_RE.match(text)
    if match:
        body = text[match.end():]
        if yaml is not None:
            try:
                fm = yaml.safe_load(match.group(1)) or {}
            except yaml.YAMLError:
                fm = {}
            raw_tags = fm.get("tags", []) if isinstance(fm, dict) else []
            if isinstance(raw_tags, str):
                tags = [raw_tags]
            elif isinstance(raw_tags, list):
                tags = [str(t) for t in raw_tags if t]

    headings = " ".join(_HEADING_RE.findall(body))
    h1 = _HEADING_RE.search(body)
    title = md_file.stem
    if h1 and h1.group(1).strip() and h1.group(1).strip() != title:
        title = f"{title} {h1.group(1).strip()}"

    rel = md_file.relative_to(vault_path)
    folder = rel.parent.as_posix()
    return {
        "title": title,
        "headings": headings,
        "tags": " ".join(tags),
        "body": body,
        "path": rel.as_posix(),
        "folder": folder,
    }


def scan_files(vault_path: Path) -> dict[str, tuple[float, int]]:
    """Map of rel-path → (mtime, size) for every indexable .md file."""
    out: dict[str, tuple[float, int]] = {}
    for md_file in vault_path.rglob("*.md"):
        rel = md_file.relative_to(vault_path)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        try:
            stat = md_file.stat()
        except OSError:
            continue
        out[rel.as_posix()] = (stat.st_mtime, stat.st_size)
    return out


# ── index operations ──────────────────────────────────────────────────────────


def update_index(config: dict, *, full: bool = False, quiet: bool = False) -> dict:
    """Build (full=True) or incrementally refresh the index. Returns stats."""
    mem = memory_config(config)
    vault_path = vault_path_from(config)
    if not vault_path.is_dir():
        raise ValueError(f"vault_path does not exist: {vault_path}")
    if not fts5_available():
        raise RuntimeError("this Python's sqlite3 lacks FTS5 support")

    db_path = db_path_for_vault(vault_path, mem["db_dir"])
    conn = open_db(db_path)
    try:
        if full:
            conn.execute("DROP TABLE IF EXISTS notes_fts")
            conn.execute("DROP TABLE IF EXISTS files")
        ensure_schema(conn, mem["tokenizer"])

        on_disk = scan_files(vault_path)
        in_db = {
            path: (mtime, size)
            for path, mtime, size in conn.execute("SELECT path, mtime, size FROM files")
        }

        changed = [
            p for p, sig in on_disk.items()
            if p not in in_db or (abs(in_db[p][0] - sig[0]) > 1e-6 or in_db[p][1] != sig[1])
        ]
        removed = [p for p in in_db if p not in on_disk]

        for rel in removed:
            conn.execute("DELETE FROM notes_fts WHERE path = ?", (rel,))
            conn.execute("DELETE FROM files WHERE path = ?", (rel,))

        for rel in changed:
            note = parse_note(vault_path / rel, vault_path)
            conn.execute("DELETE FROM notes_fts WHERE path = ?", (rel,))
            conn.execute(
                "INSERT INTO notes_fts(title, headings, tags, body, path, folder)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (note["title"], note["headings"], note["tags"], note["body"],
                 note["path"], note["folder"]),
            )
            mtime, size = on_disk[rel]
            conn.execute(
                "INSERT INTO files(path, mtime, size) VALUES (?, ?, ?)"
                " ON CONFLICT(path) DO UPDATE SET mtime=excluded.mtime, size=excluded.size",
                (rel, mtime, size),
            )

        conn.execute(
            "INSERT INTO meta(key, value) VALUES('last_update', ?)"
            " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(int(time.time())),),
        )
        conn.commit()
    finally:
        conn.close()

    stats = {
        "db": str(db_path),
        "indexed": len(changed),
        "removed": len(removed),
        "total": len(on_disk),
    }
    if not quiet:
        mode = "rebuilt" if full else "updated"
        print(
            f"Index {mode}: {stats['indexed']} indexed, {stats['removed']} removed, "
            f"{stats['total']} notes total\nDB: {db_path}"
        )
    return stats


def auto_update_after_write(config: dict) -> None:
    """Best-effort refresh used by vault_writer after a successful write.

    Intentionally conservative: runs only when memory is enabled, auto_update
    is on AND the database already exists (first build stays an explicit
    `memory_index.py build` / migrate.py step, so tests and fresh setups are
    never surprised by index creation).

    When memory is wanted (enabled + auto_update) but the index was never
    built, the write would otherwise leave the agent's memory empty with no
    signal. To avoid that silent dead-end it prints a one-line hint to stderr
    (once per write — vault_writer calls this once per run) and stays a no-op.
    """
    mem = memory_config(config)
    if not (mem["enabled"] and mem["auto_update"]):
        return
    try:
        vault_path = vault_path_from(config)
    except ValueError:
        return
    db_path = db_path_for_vault(vault_path, mem["db_dir"])
    if not db_path.exists():
        print(
            "NOTE: vault memory index not built yet — new notes are NOT searchable "
            "until you run: python3 scripts/memory_index.py build",
            file=sys.stderr,
        )
        return
    update_index(config, quiet=True)


# ── search ────────────────────────────────────────────────────────────────────


def build_match_expr(query: str, *, prefix: bool = False, raw: bool = False,
                     tag: str = "") -> str:
    """Turn a user query into a safe FTS5 MATCH expression."""
    if raw:
        expr = query
    else:
        terms = [t for t in query.split() if t]
        if not terms:
            raise ValueError("empty query")
        quoted = ['"' + t.replace('"', '""') + '"' for t in terms]
        if prefix:
            quoted[-1] += "*"
        expr = " ".join(quoted)
    if tag:
        expr = f'({expr}) AND tags:"{tag.replace(chr(34), chr(34) * 2)}"'
    return expr


def search(config: dict, query: str, *, limit: int = 10, folder: str = "",
           tag: str = "", prefix: bool = False, raw: bool = False) -> list[dict]:
    mem = memory_config(config)
    vault_path = vault_path_from(config)
    db_path = db_path_for_vault(vault_path, mem["db_dir"])
    if not db_path.exists():
        raise RuntimeError(
            f"index not built yet ({db_path}) — run: python3 scripts/memory_index.py build"
        )

    expr = build_match_expr(query, prefix=prefix, raw=raw, tag=tag)
    sql = (
        "SELECT path, folder, title,"
        " snippet(notes_fts, 3, '«', '»', '…', 12) AS snip,"
        " bm25(notes_fts, 10.0, 4.0, 6.0, 1.0) AS rank"
        " FROM notes_fts WHERE notes_fts MATCH ?"
    )
    params: list = [expr]
    if folder:
        sql += " AND (folder = ? OR folder LIKE ?)"
        params += [folder, folder.rstrip("/") + "/%"]
    sql += " ORDER BY rank LIMIT ?"
    params.append(max(1, limit))

    conn = open_db(db_path)
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    return [
        {
            "path": path,
            "folder": fold,
            "title": title,
            "snippet": " ".join(snip.split()),
            "score": round(-rank, 3),
        }
        for path, fold, title, snip, rank in rows
    ]


# ── status ────────────────────────────────────────────────────────────────────


def status(config: dict) -> dict:
    mem = memory_config(config)
    vault_path = vault_path_from(config)
    db_path = db_path_for_vault(vault_path, mem["db_dir"])
    if not db_path.exists():
        return {"db": str(db_path), "exists": False}
    conn = open_db(db_path)
    try:
        notes = conn.execute("SELECT count(*) FROM files").fetchone()[0]
        meta = dict(conn.execute("SELECT key, value FROM meta"))
    finally:
        conn.close()
    return {
        "db": str(db_path),
        "exists": True,
        "notes": notes,
        "size_kb": db_path.stat().st_size // 1024,
        "tokenizer": meta.get("tokenizer", "?"),
        "last_update": meta.get("last_update", "never"),
    }


# ── CLI ───────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="FTS5 memory index over the vault")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build", help="full rebuild of the index")
    sub.add_parser("update", help="incremental refresh (mtime/size)")
    sub.add_parser("status", help="show index status")
    p_search = sub.add_parser("search", help="full-text search")
    p_search.add_argument("query")
    p_search.add_argument("--limit", type=int, default=10)
    p_search.add_argument("--folder", default="", help="restrict to a vault subfolder")
    p_search.add_argument("--tag", default="", help="require a frontmatter tag")
    p_search.add_argument("--prefix", action="store_true",
                          help="treat the last term as a prefix (term*)")
    p_search.add_argument("--raw", action="store_true",
                          help="pass the query as raw FTS5 syntax")
    p_search.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    config = load_config(strict=True)
    mem = memory_config(config)
    if not mem["enabled"] and args.cmd != "status":
        print("memory is disabled ([memory].enabled = false)", file=sys.stderr)
        return 2

    try:
        if args.cmd == "build":
            update_index(config, full=True)
        elif args.cmd == "update":
            update_index(config)
        elif args.cmd == "status":
            info = status(config)
            print(json.dumps(info, ensure_ascii=False, indent=2))
        elif args.cmd == "search":
            results = search(
                config, args.query, limit=args.limit, folder=args.folder,
                tag=args.tag, prefix=args.prefix, raw=args.raw,
            )
            if args.as_json:
                print(json.dumps(results, ensure_ascii=False, indent=2))
            elif not results:
                print("no matches")
            else:
                for r in results:
                    print(f"{r['score']:>7}  {r['path']}\n         {r['snippet']}")
    except (ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except sqlite3.OperationalError as exc:
        print(f"ERROR: FTS5 query failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
