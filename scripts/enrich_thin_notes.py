"""enrich_thin_notes.py — Deterministically expand thin atomic notes."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

try:
    from scripts.audit_vault import NoteRecord, iter_notes
    from scripts.config import load_config
except ModuleNotFoundError:
    from audit_vault import NoteRecord, iter_notes
    from config import load_config


ENRICH_HEADER = "## Practical Notes"


def is_thin_atomic(note: NoteRecord, *, min_words: int) -> bool:
    """Return True for atomic notes that need extra substance."""
    return note.note_type == "atomic" and 0 < note.words < min_words


def extract_title_tokens(title: str) -> set[str]:
    """Extract stable comparison tokens from a note title."""
    return {
        token
        for token in re.findall(r"\w+", title.lower())
        if len(token) >= 4
    }


def related_titles(note: NoteRecord, notes: list[NoteRecord], *, limit: int = 3) -> list[str]:
    """Find nearby notes that share a source document or title vocabulary."""
    note_tokens = extract_title_tokens(note.title)
    ranked: list[tuple[int, str]] = []
    for candidate in notes:
        if candidate.path == note.path:
            continue
        score = 0
        if note.source_doc and candidate.source_doc == note.source_doc:
            score += 3
        shared = note_tokens & extract_title_tokens(candidate.title)
        score += len(shared)
        if score <= 0:
            continue
        ranked.append((score, candidate.title))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [title for _, title in ranked[:limit]]


def build_enrichment_paragraphs(note: NoteRecord, suggestions: list[str]) -> list[str]:
    """Generate deterministic context paragraphs tailored to a thin note."""
    title = note.title.lower()
    if "subprocess" in title and "codex" in title:
        return [
            (
                "На практике такой вызов строится вокруг subprocess.run или Popen с явным "
                "таймаутом, захватом stdout и stderr и проверкой кода возврата. Это позволяет "
                "боту передавать в Codex уже очищенный промпт, а затем разбирать результат как "
                "обычный текстовый ответ без интерактивного TUI."
            ),
            (
                "В Telegram-боте такой слой полезно изолировать в отдельный worker: он ограничивает "
                "время выполнения, логирует сбои сети или авторизации и не смешивает orchestration-код "
                f"с доменной логикой заметок. В связке с [[{suggestions[0]}]] и [[{suggestions[1]}]] "
                "это превращает CLI-вызов в предсказуемый шаг пайплайна, а не в хрупкий shell-хак."
                if len(suggestions) >= 2
                else (
                    "В Telegram-боте такой слой полезно изолировать в отдельный worker: он ограничивает "
                    "время выполнения, логирует сбои сети или авторизации и не смешивает orchestration-код "
                    "с доменной логикой заметок."
                )
            ),
        ]

    if "пайплайн" in title or "pipeline" in title:
        return [
            (
                "Смысл Unix-пайплайна здесь в том, что Telegram-бот остаётся тонким маршрутизатором: "
                "он принимает вход, передаёт данные через stdin и stdout между подготовительными "
                "скриптами и Claude Code и не встраивает весь анализ документов в один монолитный процесс."
            ),
            (
                "Такой подход упрощает отладку и масштабирование: препроцессор может нормализовать файл, "
                "следующий шаг обогащает контекст, а финальный постпроцессор приводит ответ к формату "
                f"vault. Связанные заметки вроде [[{suggestions[0]}]] и [[{suggestions[1]}]] показывают, "
                "как этот конвейер связывается с постепенной подачей контекста и доступом к внешним инструментам."
                if len(suggestions) >= 2
                else (
                    "Такой подход упрощает отладку и масштабирование: препроцессор может нормализовать файл, "
                    "следующий шаг обогащает контекст, а финальный постпроцессор приводит ответ к формату vault."
                )
            ),
        ]

    if suggestions:
        intro = "Связанный контекст: " + ", ".join(f"[[{title}]]" for title in suggestions) + "."
    else:
        intro = "Связанный контекст помогает удерживать заметку в общей сети знаний."
    return [
        (
            "Эта заметка требует практического контекста, чтобы её можно было читать отдельно от исходного "
            f"документа. {intro}"
        ),
        (
            "Хорошая atomic note должна не только назвать инструмент или паттерн, но и зафиксировать, "
            "какую операционную роль он играет в пайплайне, какие ограничения у него есть и с какими "
            "соседними концептами его стоит связывать."
        ),
    ]


def append_enrichment(content: str, paragraphs: list[str]) -> str:
    """Insert enrichment paragraphs before the Related section."""
    if ENRICH_HEADER in content:
        return content

    block = ENRICH_HEADER + "\n\n" + "\n\n".join(paragraphs).strip() + "\n"
    stripped = content.rstrip()
    related_header = "\n## Related"
    if related_header in stripped:
        head, tail = stripped.split(related_header, 1)
        return head.rstrip() + "\n\n" + block + "\n## Related" + tail + "\n"
    return stripped + "\n\n" + block


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Expand thin atomic notes with deterministic practical context."
    )
    parser.add_argument(
        "--min-words",
        type=int,
        default=80,
        help="Minimum healthy word count for atomic notes (default: 80)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of thin notes to process (default: 10)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show proposed enrichments without modifying files",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write enrichments into the note files",
    )
    args = parser.parse_args()

    config = load_config(strict=True)
    vault_path = Path(config["vault"]["vault_path"])
    notes = iter_notes(vault_path)
    targets = [note for note in notes if is_thin_atomic(note, min_words=args.min_words)]
    targets.sort(key=lambda note: (note.words, note.title))
    targets = targets[:args.limit]

    results: list[dict] = []
    modified = 0
    for note in targets:
        suggestions = related_titles(note, notes)
        paragraphs = build_enrichment_paragraphs(note, suggestions)
        updated_text = append_enrichment(note.path.read_text(encoding="utf-8"), paragraphs)
        changed = updated_text != note.path.read_text(encoding="utf-8")
        if args.apply and not args.dry_run and changed:
            note.path.write_text(updated_text, encoding="utf-8")
            modified += 1

        results.append(
            {
                "title": note.title,
                "path": str(note.path),
                "words": note.words,
                "related_titles": suggestions,
                "paragraphs": paragraphs,
                "changed": changed,
            }
        )

    print(
        json.dumps(
            {
                "summary": {
                    "target_notes": len(targets),
                    "modified_notes": modified,
                    "dry_run": args.dry_run or not args.apply,
                },
                "notes": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
