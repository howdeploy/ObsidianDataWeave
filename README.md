<div align="center">

# ObsidianDataWeave

**Research docs from Google Drive → structured atomic notes in Obsidian. One command, fully automated.**

**Исследовательские документы из Google Drive → структурированные атомарные заметки в Obsidian. Одна команда, полная автоматизация.**

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Claude Code](https://img.shields.io/badge/Claude%20Code-Skill-blueviolet)

---

[**На русском**](#русский) | [**In English**](#english)

</div>

---

<a id="русский"></a>

## На русском

### Что это

ObsidianDataWeave — навык для [Claude Code](https://docs.anthropic.com/en/docs/claude-code), который скачивает `.docx` файлы из Google Drive, разбивает их на атомарные заметки по методологии MOC + Zettelkasten, присваивает теги и вики-ссылки, и записывает результат напрямую в ваш vault Obsidian.

### Установка через Claude Code

Скопируйте этот промпт в Claude Code — он сделает всё сам:

```
Клонируй https://github.com/howdeploy/ObsidianDataWeave.git и запусти bash install.sh в клонированной директории. Установщик спросит путь к моему Obsidian vault и настроит всё остальное. После установки зарегистрируй навык в Claude Code.
```

Установщик:
- Проверит Python 3.10+ и установит зависимости (`python-docx`, `pyyaml`)
- Установит `rclone` (если нет)
- Создаст `config.toml` с путём к vault (спросит интерактивно)
- Создаст папки в vault
- Зарегистрирует навык в `~/.claude/CLAUDE.md`

### Как использовать

После установки просто говорите Claude Code что нужно:

```
Обработай документ "Архитектура второго мозга.docx"
```

```
Скачай мои файлы с Google Drive и разбей на атомарные заметки
```

```
Запусти пайплайн для Zettelkasten-методология.docx
```

```
Импортируй документ в Obsidian
```

Ещё примеры:

| Что сказать | Что произойдёт |
|-------------|---------------|
| `process МойДокумент.docx` | Полный цикл: скачать → разобрать → атомизировать → записать в vault |
| `process МойДокумент.docx --skip-fetch` | Документ уже скачан, пропустить загрузку с Drive |
| `process /tmp/dw/staging/plan.json --from-plan` | Начать с готового плана атомизации |

### Что происходит под капотом

```
Google Drive → fetch → parse → atomize (Claude) → generate → write → Obsidian vault
```

1. **Fetch** — `rclone` скачивает `.docx` из Google Drive во временную директорию
2. **Parse** — извлекает заголовки, абзацы и таблицы в JSON
3. **Atomize** — Claude читает JSON и генерирует план атомизации (заголовки, теги, вики-ссылки)
4. **Generate** — создаёт `.md` файлы с YAML-фронтматером
5. **Write** — перемещает готовые заметки в папки vault, дедупликация по `(source_doc, title)`

### MOC + Zettelkasten

**MOC (Map of Content)** — навигационный хаб: собирает ссылки на все атомарные заметки из документа. Один MOC на документ.

**Атомарные заметки** — одна идея, 150–600 слов, самодостаточные. Связаны `[[вики-ссылками]]` друг с другом и с MOC.

**Smart Connections** находит семантически близкие заметки через локальные эмбеддинги — второй слой связей поверх ручных.

### Шаблоны

Директория `templates/` содержит стартовую структуру vault:

- `Notes/Atomic Note Example.md` — пример атомарной заметки
- `MOCs/Topic Map - MOC.md` — пример MOC
- `.smart-env/smart_env.json` — конфиг Smart Connections (модель TaylorAI/bge-micro-v2, бесплатная, локальная)

### Конфигурация

Файл `config.toml` (создаётся при установке):

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
- [rclone](https://rclone.org/) с доступом к Google Drive
- [Claude Code](https://claude.ai/code)
- `vault_path` в `config.toml` — абсолютный путь к вашему Obsidian vault

**Обязательные плагины Obsidian:**

- [Smart Connections](https://github.com/brianpetro/obsidian-smart-connections) — векторный семантический поиск по vault (локальные эмбеддинги, без API ключа)
- [Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) — HTTP-интерфейс для чтения/записи vault
- [MCP Obsidian](https://github.com/MarkusPfundstein/mcp-obsidian) — MCP-сервер, соединяющий Claude Code с Obsidian через Local REST API

### Структура проекта

```
ObsidianDataWeave/
├── scripts/
│   ├── process.py          # Главный пайплайн (все шаги)
│   ├── fetch_docx.sh       # Скачивание с Google Drive
│   ├── parse_docx.py       # .docx → JSON
│   ├── atomize.py          # JSON → план атомизации (через Claude)
│   ├── generate_notes.py   # План → .md файлы
│   └── vault_writer.py     # Staging → vault (с дедупликацией)
├── rules/
│   ├── atomization.md      # Правила атомизации
│   └── taxonomy.md         # Правила таксономии тегов
├── templates/              # Стартовая структура vault
├── SKILL.md                # Промпт-инструкции для Claude
├── tags.yaml               # Каноничный список тегов
├── config.example.toml     # Шаблон конфигурации
├── install.sh              # Установщик
└── requirements.txt        # Python-зависимости
```

### Лицензия

MIT — см. [LICENSE](LICENSE).

---

<a id="english"></a>

## In English

### What is this

ObsidianDataWeave is a [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skill that fetches `.docx` files from Google Drive, splits them into atomic notes using the MOC + Zettelkasten methodology, assigns tags and wikilinks, and writes the results directly to your Obsidian vault.

### Install via Claude Code

Copy this prompt into Claude Code — it handles everything:

```
Clone https://github.com/howdeploy/ObsidianDataWeave.git and run bash install.sh in the cloned directory. The installer will ask for my Obsidian vault path and configure everything else. After installation, register the skill in Claude Code.
```

The installer will:
- Check Python 3.10+ and install dependencies (`python-docx`, `pyyaml`)
- Install `rclone` (if missing)
- Create `config.toml` with your vault path (interactive prompt)
- Create vault subfolders
- Register the skill in `~/.claude/CLAUDE.md`

### How to use

After installation, just tell Claude Code what you need:

```
Process the document "Second Brain Architecture.docx"
```

```
Download my files from Google Drive and split into atomic notes
```

```
Run the pipeline for Zettelkasten-methodology.docx
```

```
Import document to Obsidian
```

More examples:

| What to say | What happens |
|-------------|-------------|
| `process MyDocument.docx` | Full cycle: download → parse → atomize → write to vault |
| `process MyDocument.docx --skip-fetch` | Document already downloaded, skip Drive fetch |
| `process /tmp/dw/staging/plan.json --from-plan` | Start from an existing atom plan |

### How it works

```
Google Drive → fetch → parse → atomize (Claude) → generate → write → Obsidian vault
```

1. **Fetch** — `rclone` downloads `.docx` from Google Drive to a staging directory
2. **Parse** — extracts headings, paragraphs, and tables into JSON
3. **Atomize** — Claude reads JSON and generates an atom plan (titles, tags, wikilinks)
4. **Generate** — creates `.md` files with YAML frontmatter
5. **Write** — moves notes to vault folders, deduplicates by `(source_doc, title)`

### MOC + Zettelkasten

**MOC (Map of Content)** — a navigation hub collecting links to all atomic notes from a document. One MOC per document.

**Atomic notes** — one idea, 150–600 words, fully self-contained. Connected via `[[wikilinks]]` to each other and to the MOC.

**Smart Connections** finds semantically similar notes via local embeddings — a second layer of connections on top of manual links.

### Templates

The `templates/` directory contains a starter vault structure:

- `Notes/Atomic Note Example.md` — example atomic note
- `MOCs/Topic Map - MOC.md` — example MOC
- `.smart-env/smart_env.json` — Smart Connections config (TaylorAI/bge-micro-v2 model, free, local)

### Configuration

`config.toml` (created during installation):

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
- [rclone](https://rclone.org/) configured with Google Drive access
- [Claude Code](https://claude.ai/code)
- `vault_path` in `config.toml` — absolute path to your Obsidian vault

**Required Obsidian plugins:**

- [Smart Connections](https://github.com/brianpetro/obsidian-smart-connections) — vector semantic search across your vault (local embeddings, no API key)
- [Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) — HTTP interface for reading/writing vault contents
- [MCP Obsidian](https://github.com/MarkusPfundstein/mcp-obsidian) — MCP server connecting Claude Code to Obsidian via Local REST API

### Project structure

```
ObsidianDataWeave/
├── scripts/
│   ├── process.py          # Main pipeline (all steps)
│   ├── fetch_docx.sh       # Download from Google Drive
│   ├── parse_docx.py       # .docx → JSON
│   ├── atomize.py          # JSON → atom plan (via Claude)
│   ├── generate_notes.py   # Plan → .md files
│   └── vault_writer.py     # Staging → vault (with deduplication)
├── rules/
│   ├── atomization.md      # Atomization rules
│   └── taxonomy.md         # Tag taxonomy rules
├── templates/              # Starter vault structure
├── SKILL.md                # Prompt instructions for Claude
├── tags.yaml               # Canonical tag list
├── config.example.toml     # Configuration template
├── install.sh              # Installer
└── requirements.txt        # Python dependencies
```

### License

MIT — see [LICENSE](LICENSE).
