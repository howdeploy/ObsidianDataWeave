<div align="center">

# ObsidianDataWeave

**Research docs from Google Drive → structured atomic notes in Obsidian. One command, fully automated.**

**Исследовательские документы из Google Drive → структурированные атомарные заметки в Obsidian. Одна команда, полная автоматизация.**

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Claude Code](https://img.shields.io/badge/Claude%20Code-Skill-blueviolet)
![Codex](https://img.shields.io/badge/Codex-AGENTS.md-green)

---

[**На русском**](#русский) | [**In English**](#english)

</div>

---

<a id="русский"></a>

## На русском

### Что это

ObsidianDataWeave — навык для [Claude Code](https://docs.anthropic.com/en/docs/claude-code) и [Codex](https://openai.com/index/codex/), который скачивает `.docx` файлы из Google Drive, разбивает их на атомарные заметки по методологии MOC + Zettelkasten, присваивает теги и вики-ссылки, и записывает результат напрямую в ваш vault Obsidian. Также умеет обогащать и атомизировать существующие заметки в vault.

### Установка

```bash
git clone https://github.com/howdeploy/ObsidianDataWeave.git
cd ObsidianDataWeave
bash install.sh --vault-path "/путь/к/вашему/vault"
```

Или скопируйте этот промпт в Claude Code — он сделает всё сам:

```
Клонируй https://github.com/howdeploy/ObsidianDataWeave.git и запусти bash install.sh --vault-path "/путь/к/vault" в клонированной директории.
```

Установщик:
- Проверит Python 3.10+ и установит зависимости (`python-docx`, `pyyaml`)
- Создаст `config.toml` с путём к vault
- Зарегистрирует навык глобально в `~/.claude/skills/obsidian-dataweave/`
- Добавит блок в `~/.claude/CLAUDE.md`

После установки навык работает **из любой директории**.

#### Режимы установки

| Режим | Флаг | Что делает |
|-------|------|-----------|
| **claude** (по умолчанию) | `--mode claude` | Зависимости + config + глобальный навык в `~/.claude/` |
| **codex** | `--mode codex` | Зависимости + config + проверка `AGENTS.md` |
| **local** | `--mode local` | Только зависимости + config |

### Как использовать

После установки просто говорите Claude Code что нужно:

```
Обработай документ "Архитектура второго мозга.docx"
```

```
Обработай заметку "Мои мысли о продуктивности"
```

```
Скачай мои файлы с Google Drive и разбей на атомарные заметки
```

```
Проверь настройку — запусти doctor
```

Ещё примеры:

| Что сказать | Что произойдёт |
|-------------|---------------|
| `process МойДокумент.docx` | Полный цикл: скачать → разобрать → атомизировать → записать в vault |
| `process МойДокумент.docx --non-interactive --on-conflict skip` | То же, без вопросов (для автоматизации) |
| `обработай заметку "Название"` | Enrich или atomize существующей заметки |
| `process_note "Note" --mode atomize` | Принудительная атомизация заметки |
| `dedup --dry-run` | Показать дубликаты без изменений |

### Что происходит под капотом

```
Google Drive → fetch → parse → atomize (Claude) → generate → write → Obsidian vault
```

1. **Fetch** — `rclone` скачивает `.docx` из Google Drive во временную директорию
2. **Parse** — извлекает заголовки, абзацы и таблицы в JSON
3. **Atomize** — Claude читает JSON и генерирует план атомизации (заголовки, теги, вики-ссылки)
4. **Generate** — создаёт `.md` файлы с YAML-фронтматером
5. **Write** — перемещает готовые заметки в папки vault, дедупликация по `(source_doc, title)`

Для личных заметок процесс проще:

```
Vault note → detect mode → rewrite (Claude) → write back
```

- **Enrich** — короткая заметка → добавляет теги, вики-ссылки, расширяет текст (1 → 1)
- **Atomize** — длинная заметка → разбивает на атомарные заметки + MOC (1 → N)

### MOC + Zettelkasten

**MOC (Map of Content)** — навигационный хаб: собирает ссылки на все атомарные заметки из документа. Один MOC на документ.

**Атомарные заметки** — одна идея, 150–600 слов, самодостаточные. Связаны `[[вики-ссылками]]` друг с другом и с MOC.

**Smart Connections** находит семантически близкие заметки через локальные эмбеддинги — второй слой связей поверх ручных.

### Шаблоны

Директория `templates/` содержит стартовую структуру vault:

- `Notes/Atomic Note Example.md` — пример атомарной заметки
- `MOCs/Topic Map - MOC.md` — пример MOC

### Конфигурация

Файл `config.toml` (создаётся при установке, не коммитится):

```toml
[vault]
vault_path = "/путь/к/вашему/vault"          # обязательно, абсолютный путь
notes_folder = "Research & Insights"          # куда пишутся атомарные заметки
moc_folder = "Guides & Overviews"             # куда пишутся MOC
source_folder = "Sources"                      # ссылки на исходники

[rclone]
remote = "gdrive:"                             # имя rclone remote
staging_dir = "/tmp/dw/staging"               # временная директория
```

### Требования

- Python 3.10+ (рекомендуется 3.11+)
- [rclone](https://rclone.org/) с доступом к Google Drive (для импорта `.docx`)
- [Claude Code](https://claude.ai/code) или [Codex](https://openai.com/index/codex/)
- `vault_path` в `config.toml` — абсолютный путь к вашему Obsidian vault

**Рекомендуемые плагины Obsidian:**

- [Smart Connections](https://github.com/brianpetro/obsidian-smart-connections) — векторный семантический поиск по vault (локальные эмбеддинги, без API ключа)

### Структура проекта

```
ObsidianDataWeave/
├── scripts/
│   ├── process.py            # Главный пайплайн (.docx → vault)
│   ├── process_note.py       # Обработка личных заметок (enrich/atomize)
│   ├── fetch_docx.sh         # Скачивание с Google Drive
│   ├── parse_docx.py         # .docx → JSON
│   ├── atomize.py            # JSON → план атомизации (через Claude)
│   ├── generate_notes.py     # План → .md файлы
│   ├── vault_writer.py       # Staging → vault (с дедупликацией)
│   ├── dedup_vault.py        # Поиск и мерж дубликатов
│   ├── scan_vault.py         # Сканирование существующих заметок
│   ├── rewrite_backend.py    # Бэкенд семантической перезаписи (Claude CLI)
│   ├── config.py             # Загрузчик конфигурации
│   └── doctor.py             # Проверка окружения
├── rules/
│   ├── atomization.md        # Правила атомизации
│   ├── taxonomy.md           # Правила таксономии тегов
│   └── personal_notes.md     # Правила обработки личных заметок
├── templates/                # Стартовая структура vault
├── tests/                    # Регрессионные тесты
├── docs/                     # Документация для агентов
├── AGENTS.md                 # Контракт агента (Claude Code + Codex)
├── SKILL.md                  # Claude-адаптер
├── SKILL_PERSONAL.md         # Промпт для обработки личных заметок
├── tags.yaml                 # Каноничный список тегов
├── config.example.toml       # Шаблон конфигурации
├── install.sh                # Установщик с глобальной регистрацией
└── requirements.txt          # Python-зависимости
```

### Лицензия

MIT — см. [LICENSE](LICENSE).

---

<a id="english"></a>

## In English

### What is this

ObsidianDataWeave is a [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [Codex](https://openai.com/index/codex/) skill that fetches `.docx` files from Google Drive, splits them into atomic notes using the MOC + Zettelkasten methodology, assigns tags and wikilinks, and writes the results directly to your Obsidian vault. It can also enrich and atomize existing notes in your vault.

### Install

```bash
git clone https://github.com/howdeploy/ObsidianDataWeave.git
cd ObsidianDataWeave
bash install.sh --vault-path "/path/to/your/obsidian/vault"
```

Or copy this prompt into Claude Code — it handles everything:

```
Clone https://github.com/howdeploy/ObsidianDataWeave.git and run bash install.sh --vault-path "/path/to/vault" in the cloned directory.
```

The installer will:
- Check Python 3.10+ and install dependencies (`python-docx`, `pyyaml`)
- Create `config.toml` with your vault path
- Register the skill globally in `~/.claude/skills/obsidian-dataweave/`
- Add a helper block to `~/.claude/CLAUDE.md`

After installation the skill works **from any directory**.

#### Install modes

| Mode | Flag | What it does |
|------|------|-------------|
| **claude** (default) | `--mode claude` | Deps + config + global skill in `~/.claude/` |
| **codex** | `--mode codex` | Deps + config + verify `AGENTS.md` |
| **local** | `--mode local` | Deps + config only |

### How to use

After installation, just tell Claude Code what you need:

```
Process the document "Second Brain Architecture.docx"
```

```
Process note "My thoughts on productivity"
```

```
Download my files from Google Drive and split into atomic notes
```

```
Check setup — run doctor
```

More examples:

| What to say | What happens |
|-------------|-------------|
| `process MyDocument.docx` | Full cycle: download → parse → atomize → write to vault |
| `process MyDocument.docx --non-interactive --on-conflict skip` | Same, no prompts (for automation) |
| `process note "Title"` | Enrich or atomize an existing note |
| `process_note "Note" --mode atomize` | Force atomization of a note |
| `dedup --dry-run` | Show duplicates without changes |

### How it works

```
Google Drive → fetch → parse → atomize (Claude) → generate → write → Obsidian vault
```

1. **Fetch** — `rclone` downloads `.docx` from Google Drive to a staging directory
2. **Parse** — extracts headings, paragraphs, and tables into JSON
3. **Atomize** — Claude reads JSON and generates an atom plan (titles, tags, wikilinks)
4. **Generate** — creates `.md` files with YAML frontmatter
5. **Write** — moves notes to vault folders, deduplicates by `(source_doc, title)`

For personal notes the process is simpler:

```
Vault note → detect mode → rewrite (Claude) → write back
```

- **Enrich** — short note → adds tags, wikilinks, expands text (1 → 1)
- **Atomize** — long note → splits into atomic notes + MOC (1 → N)

### MOC + Zettelkasten

**MOC (Map of Content)** — a navigation hub collecting links to all atomic notes from a document. One MOC per document.

**Atomic notes** — one idea, 150–600 words, fully self-contained. Connected via `[[wikilinks]]` to each other and to the MOC.

**Smart Connections** finds semantically similar notes via local embeddings — a second layer of connections on top of manual links.

### Templates

The `templates/` directory contains a starter vault structure:

- `Notes/Atomic Note Example.md` — example atomic note
- `MOCs/Topic Map - MOC.md` — example MOC

### Configuration

`config.toml` (created during installation, never committed):

```toml
[vault]
vault_path = "/path/to/your/obsidian/vault"   # required, absolute path
notes_folder = "Research & Insights"           # atomic notes destination
moc_folder = "Guides & Overviews"              # MOC files destination
source_folder = "Sources"                       # source document references

[rclone]
remote = "gdrive:"                              # rclone remote name
staging_dir = "/tmp/dw/staging"                # temporary staging area
```

### Requirements

- Python 3.10+ (3.11+ recommended)
- [rclone](https://rclone.org/) configured with Google Drive access (for `.docx` import)
- [Claude Code](https://claude.ai/code) or [Codex](https://openai.com/index/codex/)
- `vault_path` in `config.toml` — absolute path to your Obsidian vault

**Recommended Obsidian plugins:**

- [Smart Connections](https://github.com/brianpetro/obsidian-smart-connections) — vector semantic search across your vault (local embeddings, no API key)

### Project structure

```
ObsidianDataWeave/
├── scripts/
│   ├── process.py            # Main pipeline (.docx → vault)
│   ├── process_note.py       # Personal note processing (enrich/atomize)
│   ├── fetch_docx.sh         # Download from Google Drive
│   ├── parse_docx.py         # .docx → JSON
│   ├── atomize.py            # JSON → atom plan (via Claude)
│   ├── generate_notes.py     # Plan → .md files
│   ├── vault_writer.py       # Staging → vault (with deduplication)
│   ├── dedup_vault.py        # Find and merge duplicate notes
│   ├── scan_vault.py         # Scan existing vault notes
│   ├── rewrite_backend.py    # Semantic rewrite backend (Claude CLI)
│   ├── config.py             # Configuration loader
│   └── doctor.py             # Environment check
├── rules/
│   ├── atomization.md        # Atomization rules
│   ├── taxonomy.md           # Tag taxonomy rules
│   └── personal_notes.md     # Personal note processing rules
├── templates/                # Starter vault structure
├── tests/                    # Regression tests
├── docs/                     # Agent-facing documentation
├── AGENTS.md                 # Agent contract (Claude Code + Codex)
├── SKILL.md                  # Claude adapter
├── SKILL_PERSONAL.md         # Prompt header for personal note processing
├── tags.yaml                 # Canonical tag list
├── config.example.toml       # Configuration template
├── install.sh                # Installer with global skill registration
└── requirements.txt          # Python dependencies
```

### License

MIT — see [LICENSE](LICENSE).
