# Requirements: ObsidianDataWeave

**Defined:** 2026-02-25
**Core Value:** Одна команда превращает любой ресерч-документ в набор правильно структурированных, связанных между собой атомарных заметок внутри Obsidian

## v1 Requirements

### Document Processing (DOCX)

- [ ] **DOCX-01**: Скилл скачивает .docx файл с Google Drive по имени через rclone
- [ ] **DOCX-02**: Парсер извлекает текст с сохранением иерархии заголовков (H1/H2/H3), списков и таблиц
- [ ] **DOCX-03**: Документ разбивается на секции по заголовкам как входные единицы для атомизации
- [ ] **DOCX-04**: Claude анализирует каждую секцию и решает — одна заметка или несколько атомарных идей (LLM-атомизация)
- [ ] **DOCX-05**: Каждая атомарная заметка содержит одну идею (150-600 слов), с осмысленным заголовком

### Frontmatter & Tags (META)

- [ ] **META-01**: Каждая заметка имеет YAML frontmatter с полями: tags, date, source_doc, note_type
- [ ] **META-02**: Теги назначаются из каноничной таксономии (tags.yaml в конфиге), а не придумываются произвольно
- [ ] **META-03**: Claude выводит 3-5 тегов из содержания заметки, ограничиваясь таксономией
- [ ] **META-04**: note_type различает типы: atomic, moc, source (для фильтрации в Obsidian)

### Links & Structure (LINK)

- [ ] **LINK-01**: Wikilinks [[]] автоматически вставляются когда заголовок заметки упоминается в тексте другой
- [ ] **LINK-02**: Claude предлагает семантические связи между заметками, даже если заголовок не упоминается буквально
- [ ] **LINK-03**: MOC-файл генерируется для каждого обработанного документа со ссылками на все атомарные заметки
- [ ] **LINK-04**: MOC зеркалит структуру документа — секции H1 как кластеры, H2-заметки внутри

### Vault Management (VAULT)

- [ ] **VAULT-01**: Заметки сохраняются в Obsidian волт по конфигурируемому пути
- [ ] **VAULT-02**: Папки роутятся по типу: MOC в одну папку, атомарные в другую, исходники в третью
- [ ] **VAULT-03**: При повторном запуске — не создаёт дубликаты (идемпотентность по source_doc + title)
- [ ] **VAULT-04**: Staging директория (/tmp) используется для промежуточных файлов — волт получает только финальный результат

### Rules System (RULE)

- [ ] **RULE-01**: Правила архитектуры заметок загружаются из rules/*.md файлов (дистиллированные из reference .docx)
- [ ] **RULE-02**: Claude следует загруженным правилам при атомизации, тегировании и создании связей
- [ ] **RULE-03**: Два reference .docx файла обработаны и сконвертированы в правила при настройке проекта

### Configuration (CONF)

- [ ] **CONF-01**: config.toml содержит: vault_path, папки для типов заметок, путь к rclone remote
- [ ] **CONF-02**: tags.yaml содержит каноничную таксономию тегов
- [ ] **CONF-03**: config.example.toml поставляется как шаблон для других пользователей

### Distribution (DIST)

- [ ] **DIST-01**: README содержит copy-paste команды, которые пользователь отправляет Claude для установки
- [ ] **DIST-02**: Claude по командам из README: клонирует репо, ставит зависимости, создаёт конфиг, регистрирует скилл
- [ ] **DIST-03**: README включает шаблоны Obsidian: структура папок, стартовые MOC-хабы, примеры атомарных заметок
- [ ] **DIST-04**: Рекомендованный конфиг Smart Connections поставляется вместе с шаблонами

## v2 Requirements

### Enhanced Processing

- **DOCX-V2-01**: Dry-run режим — превью без записи в волт
- **DOCX-V2-02**: Batch processing — обработка папки .docx файлов за раз
- **DOCX-V2-03**: Zettelkasten ID в frontmatter (timestamp-based UID)

### Enhanced Links

- **LINK-V2-01**: Обновление MOC при повторной обработке (не перезапись, а дополнение)
- **LINK-V2-02**: Кросс-документные связи (заметки из разных документов связываются)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Obsidian JS плагин | Другая экосистема, Claude Code скиллы мощнее |
| Редактирование существующих заметок | Риск потери данных, append-only безопаснее |
| Real-time мониторинг Drive | Daemon-сложность, ручной запуск надёжнее для v1 |
| Multi-vault поддержка | Одна конфигурация на волт, запускать отдельно |
| GUI/TUI интерфейс | Целевая аудитория — Claude Code пользователи (CLI) |
| Обратная синхронизация Obsidian → NotebookLM | Однонаправленный поток |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DOCX-01 | Phase 1 | Pending |
| DOCX-02 | Phase 1 | Pending |
| DOCX-03 | Phase 1 | Pending |
| DOCX-04 | Phase 2 | Pending |
| DOCX-05 | Phase 2 | Pending |
| META-01 | Phase 2 | Pending |
| META-02 | Phase 2 | Pending |
| META-03 | Phase 2 | Pending |
| META-04 | Phase 2 | Pending |
| LINK-01 | Phase 2 | Pending |
| LINK-02 | Phase 2 | Pending |
| LINK-03 | Phase 2 | Pending |
| LINK-04 | Phase 2 | Pending |
| VAULT-01 | Phase 3 | Pending |
| VAULT-02 | Phase 3 | Pending |
| VAULT-03 | Phase 3 | Pending |
| VAULT-04 | Phase 3 | Pending |
| RULE-01 | Phase 1 | Pending |
| RULE-02 | Phase 1 | Pending |
| RULE-03 | Phase 1 | Pending |
| CONF-01 | Phase 1 | Pending |
| CONF-02 | Phase 1 | Pending |
| CONF-03 | Phase 1 | Pending |
| DIST-01 | Phase 5 (gap closure) | Pending |
| DIST-02 | Phase 5 (gap closure) | Pending |
| DIST-03 | Phase 4 | Pending |
| DIST-04 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 27 total
- Mapped to phases: 27
- Unmapped: 0

---
*Requirements defined: 2026-02-25*
*Last updated: 2026-02-25 after roadmap creation*
