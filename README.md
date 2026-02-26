# ObsidianDataWeave

Turn research documents from Google Drive into structured, linked atomic notes in Obsidian.

## What is this?

ObsidianDataWeave is a Claude Code skill that fetches `.docx` files from Google Drive, splits them into atomic notes using the MOC + Zettelkasten methodology, assigns tags and wikilinks, and writes the results directly to your Obsidian vault. One command processes a document end-to-end — no manual copy-pasting.

## MOC + Zettelkasten: the methodology

**Maps of Content (MOC)** are navigation hubs — notes that collect links to related ideas rather than holding content themselves. Each processed document produces one MOC that serves as the entry point into that document's ideas.

**Atomic notes** are single-idea units. The rule: one idea per note, expressed in 150-400 words. This constraint makes every idea reusable, linkable, and searchable. When ideas are separated, the connection between two notes becomes an explicit semantic claim — you are asserting that these concepts are related. Over time, the network of links becomes your actual knowledge graph.

**Wikilinks** (`[[Note Title]]`) connect atomic notes to each other and to MOCs. **Smart Connections** uses local vector embeddings (no API key) to surface related notes you have not linked yet — the second layer of semantic discovery.

---

## Quick Start

Open Claude Code in your terminal and send these commands one at a time:

**1. Install**

Clone the repo and run the installer:

```bash
git clone https://github.com/USER/ObsidianDataWeave.git && cd ObsidianDataWeave && bash install.sh
```

The installer will:
- Check Python 3.10+ and rclone
- Install python-docx
- Create `config.toml` with your vault path
- Register the `process` skill in Claude Code

**2. Configure rclone** (if not done yet)

Set up Google Drive access:

```bash
rclone config
```

Create a remote named `gdrive:` pointing to your Google Drive. Run `rclone listremotes` to verify.

**3. Process your first document**

Tell Claude Code:

```
process MyResearch.docx
```

Claude fetches the file, splits it into atomic notes, generates a MOC, and writes everything to your vault.

---

## What happens under the hood

1. **Fetch** — `rclone copy` downloads the `.docx` from Google Drive to a local staging directory
2. **Parse** — `scripts/parse_doc.py` extracts headings, paragraphs, and tables into structured JSON
3. **Atomize** — Claude reads the JSON and generates an atom plan (MOC title, atomic note titles, tags, wikilinks)
4. **Generate** — `scripts/generate_notes.py` writes staging files with correct v1 frontmatter
5. **Write** — `scripts/vault_writer.py` moves generated notes to your Obsidian vault folders

## Templates

The `templates/` directory contains a starter Obsidian vault structure:

```bash
cp -r templates/. /path/to/your/obsidian/vault/
```

- `Notes/Atomic Note Example.md` — example atomic note with v1 frontmatter schema
- `MOCs/Topic Map - MOC.md` — example MOC with two-level hierarchy and wikilinks
- `.smart-env/smart_env.json` — Smart Connections config with TaylorAI/bge-micro-v2 (free, local, no API key)

Delete the example files after reviewing them. The pipeline populates your vault with real notes.

To enable Smart Connections with the recommended model:

```bash
cp -r templates/.smart-env /path/to/your/obsidian/vault/
```

## Configuration

Copy `config.example.toml` to `config.toml` and fill in your values:

```toml
[vault]
vault_path = "/path/to/your/obsidian/vault"
notes_folder = "Research & Insights"   # atomic notes destination
moc_folder = "Guides & Overviews"      # MOC files destination
source_folder = "Sources"               # source document references

[rclone]
remote = "gdrive:"                      # rclone remote name
staging_dir = "/tmp/dw/staging"         # temporary staging area

[processing]
default_note_type = "atomic"
```

Key fields: `vault_path` (required), `remote` (must match your rclone remote name), `notes_folder` / `moc_folder` (where notes land in your vault).

## Requirements

- Python 3.10+ (3.11+ recommended)
- [rclone](https://rclone.org/) configured with Google Drive access
- [Claude Code](https://claude.ai/code)
- Obsidian with [Smart Connections](https://github.com/brianpetro/obsidian-smart-connections) plugin (optional, for vector search)

## License

MIT — see [LICENSE](LICENSE).

---

# ObsidianDataWeave (RU)

Превращает исследовательские документы из Google Drive в структурированные, связанные атомарные заметки в Obsidian.

## Что это?

ObsidianDataWeave — это навык для Claude Code, который скачивает `.docx` файлы из Google Drive, разбивает их на атомарные заметки по методологии MOC + Zettelkasten, присваивает теги и вики-ссылки, и записывает результат напрямую в ваш vault Obsidian. Одна команда обрабатывает документ от начала до конца — без ручного копирования.

## MOC + Zettelkasten: методология

**Maps of Content (MOC)** — навигационные хабы: заметки, которые собирают ссылки на связанные идеи, а не хранят контент напрямую. Каждый обработанный документ порождает один MOC — точку входа в идеи этого документа.

**Атомарные заметки** — единицы одной идеи. Правило: одна идея на заметку, 150-400 слов. Это делает каждую идею переиспользуемой, связываемой и доступной для поиска. Связь между двумя атомарными заметками — явное семантическое утверждение о том, что эти концепции связаны. Со временем сеть связей становится настоящим графом знаний.

**Вики-ссылки** (`[[Заголовок заметки]]`) соединяют атомарные заметки друг с другом и с MOC. **Smart Connections** использует локальные векторные эмбеддинги (без API ключа) для поиска связанных заметок, которые вы ещё не связали вручную.

---

## Быстрый старт

Откройте Claude Code в терминале и вводите команды по одной:

**1. Установка**

Клонируйте репозиторий и запустите установщик:

```bash
git clone https://github.com/USER/ObsidianDataWeave.git && cd ObsidianDataWeave && bash install.sh
```

Установщик:
- Проверит Python 3.10+ и rclone
- Установит python-docx
- Создаст `config.toml` с путём к вашему vault
- Зарегистрирует навык `process` в Claude Code

**2. Настройка rclone** (если ещё не сделано)

Настройте доступ к Google Drive:

```bash
rclone config
```

Создайте remote с именем `gdrive:`, указывающий на ваш Google Drive. Проверьте: `rclone listremotes`.

**3. Обработка первого документа**

Скажите Claude Code:

```
process МойДокумент.docx
```

Claude скачает файл, разобьёт на атомарные заметки, сгенерирует MOC и запишет всё в ваш vault.

---

## Что происходит под капотом

1. **Fetch** — `rclone copy` скачивает `.docx` из Google Drive во временную директорию
2. **Parse** — `scripts/parse_doc.py` извлекает заголовки, абзацы и таблицы в структурированный JSON
3. **Atomize** — Claude читает JSON и генерирует план атомизации (заголовок MOC, заголовки заметок, теги, вики-ссылки)
4. **Generate** — `scripts/generate_notes.py` создаёт файлы со staging-фронтматером v1
5. **Write** — `scripts/vault_writer.py` перемещает готовые заметки в папки вашего vault

## Шаблоны

Директория `templates/` содержит стартовую структуру vault Obsidian:

```bash
cp -r templates/. /путь/к/вашему/vault/
```

- `Notes/Atomic Note Example.md` — пример атомарной заметки со схемой фронтматера v1
- `MOCs/Topic Map - MOC.md` — пример MOC с двухуровневой иерархией и вики-ссылками
- `.smart-env/smart_env.json` — конфиг Smart Connections с моделью TaylorAI/bge-micro-v2 (бесплатная, локальная, без API ключа)

Удалите примеры после ознакомления с форматом. Pipeline заполнит vault настоящими заметками.

Чтобы включить Smart Connections с рекомендованной моделью:

```bash
cp -r templates/.smart-env /путь/к/вашему/vault/
```

## Конфигурация

Скопируйте `config.example.toml` в `config.toml` и заполните:

```toml
[vault]
vault_path = "/путь/к/вашему/vault"
notes_folder = "Research & Insights"   # куда пишутся атомарные заметки
moc_folder = "Guides & Overviews"      # куда пишутся MOC файлы
source_folder = "Sources"               # ссылки на исходные документы

[rclone]
remote = "gdrive:"                      # имя rclone remote
staging_dir = "/tmp/dw/staging"         # временная директория

[processing]
default_note_type = "atomic"
```

Ключевые поля: `vault_path` (обязательно), `remote` (должно совпадать с именем rclone remote), `notes_folder` / `moc_folder` (куда попадают заметки в vault).

## Требования

- Python 3.10+ (рекомендуется 3.11+)
- [rclone](https://rclone.org/) настроенный с доступом к Google Drive
- [Claude Code](https://claude.ai/code)
- Obsidian с плагином [Smart Connections](https://github.com/brianpetro/obsidian-smart-connections) (опционально, для векторного поиска)

## Лицензия

MIT — см. [LICENSE](LICENSE).
