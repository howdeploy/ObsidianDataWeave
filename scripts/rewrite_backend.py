"""rewrite_backend.py — Select and call the active text-rewrite backend."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def detect_backend(explicit: str | None = None) -> str:
    """Resolve the active rewrite backend.

    Precedence:
    1. Explicit CLI/config value if not "auto"
    2. Environment override OBSIDIAN_DATAWEAVE_BACKEND
    3. Codex markers
    4. Claude markers
    5. Fallback to claude
    """
    if explicit and explicit != "auto":
        return explicit

    env_override = os.environ.get("OBSIDIAN_DATAWEAVE_BACKEND")
    if env_override in {"claude", "codex"}:
        return env_override

    if os.environ.get("CODEX_THREAD_ID") or os.environ.get("CODEX_CI"):
        return "codex"

    if os.environ.get("CLAUDECODE"):
        return "claude"

    return "claude"


def write_debug_prompt(prompt: str, prefix: str) -> Path:
    """Persist a prompt for manual inspection or replay."""
    debug_dir = Path("/tmp/dw/debug-prompts")
    debug_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    path = debug_dir / f"{prefix}-{timestamp}.prompt.md"
    path.write_text(prompt, encoding="utf-8")
    return path


def looks_truncated(text: str) -> bool:
    """Heuristic: detect if a JSON response was cut off mid-stream."""
    stripped = text.rstrip()
    if not stripped:
        return True
    if stripped.endswith('"') and stripped.count('"') % 2 != 0:
        return True
    opens = stripped.count("{") + stripped.count("[")
    closes = stripped.count("}") + stripped.count("]")
    if opens > closes + 1:
        return True
    if stripped[-1] in (",", ":", "\\"):
        return True
    return False


def call_claude(
    prompt: str,
    *,
    max_retries: int = 3,
    max_continuations: int = 2,
    timeout_seconds: int = 300,
) -> str:
    """Call Claude CLI with the assembled prompt, return stdout."""
    clean_env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    for attempt in range(1, max_retries + 1):
        try:
            result = subprocess.run(
                ["claude", "--print"],
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=clean_env,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            debug_path = write_debug_prompt(prompt, "claude-timeout")
            raise RuntimeError(
                f"Claude CLI timed out after {timeout_seconds}s. Prompt saved to {debug_path}"
            ) from None

        if result.returncode == 0:
            response = result.stdout.strip()

            for cont in range(max_continuations):
                if not looks_truncated(response):
                    break
                print(
                    f"  Truncated response detected (continuation {cont + 1}/{max_continuations})...",
                    file=sys.stderr,
                )
                tail = response[-8000:]
                cont_prompt = (
                    "Your previous response was truncated. Here is the end of what you produced:\n\n"
                    f"```\n{tail}\n```\n\n"
                    "Continue outputting the JSON from EXACTLY where you stopped. "
                    "Output ONLY the remaining JSON, no commentary."
                )
                try:
                    cont_result = subprocess.run(
                        ["claude", "--print"],
                        input=cont_prompt,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        env=clean_env,
                        timeout=timeout_seconds,
                    )
                except subprocess.TimeoutExpired:
                    debug_path = write_debug_prompt(cont_prompt, "claude-continuation-timeout")
                    raise RuntimeError(
                        "Claude CLI continuation timed out after "
                        f"{timeout_seconds}s. Prompt saved to {debug_path}"
                    ) from None
                if cont_result.returncode == 0 and cont_result.stdout.strip():
                    continuation = cont_result.stdout.strip()
                    continuation = re.sub(r"^```(?:json)?\s*", "", continuation)
                    continuation = re.sub(r"\s*```$", "", continuation)
                    response += continuation
                else:
                    break

            return response

        if attempt < max_retries:
            delay = 2 ** attempt
            print(
                f"WARNING: Claude CLI attempt {attempt}/{max_retries} failed "
                f"(exit code {result.returncode}). Retrying in {delay}s...",
                file=sys.stderr,
            )
            time.sleep(delay)

    raise RuntimeError(
        f"Claude CLI failed after {max_retries} attempts "
        f"(exit code {result.returncode}).\n"
        f"stderr: {result.stderr}"
    )


def call_codex(
    prompt: str,
    *,
    timeout_seconds: int = 300,
    project_root: Path | None = None,
) -> str:
    """Call Codex CLI non-interactively and return the final message."""
    if project_root is None:
        project_root = Path.cwd()

    debug_path = write_debug_prompt(prompt, "codex")
    with tempfile.NamedTemporaryFile(prefix="codex-last-message-", suffix=".txt", delete=False) as tmp:
        output_path = Path(tmp.name)

    cmd = [
        "codex",
        "exec",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--color",
        "never",
        "-C",
        str(project_root),
        "-o",
        str(output_path),
        "-",
    ]

    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"Codex CLI timed out after {timeout_seconds}s. Prompt saved to {debug_path}"
        ) from None

    if result.returncode != 0:
        raise RuntimeError(
            f"Codex CLI failed with exit code {result.returncode}.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}\n"
            f"Prompt saved to {debug_path}"
        )

    if not output_path.exists():
        raise RuntimeError(
            "Codex CLI completed without producing the final message file. "
            f"Prompt saved to {debug_path}"
        )

    response = output_path.read_text(encoding="utf-8").strip()
    if not response:
        raise RuntimeError(
            "Codex CLI completed but returned an empty final message. "
            f"Prompt saved to {debug_path}"
        )
    return response


def call_rewriter(
    prompt: str,
    *,
    backend: str = "auto",
    timeout_seconds: int = 300,
    project_root: Path | None = None,
) -> tuple[str, str]:
    """Call the selected rewrite backend and return (backend, response)."""
    resolved = detect_backend(backend)
    if resolved == "claude":
        return resolved, call_claude(prompt, timeout_seconds=timeout_seconds)
    if resolved == "codex":
        return resolved, call_codex(prompt, timeout_seconds=timeout_seconds, project_root=project_root)
    raise ValueError(f"Unsupported rewrite backend: {resolved}")
