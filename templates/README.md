# Templates

This directory contains a starter Obsidian vault structure for use with ObsidianDataWeave.

## How to use

1. Copy the contents of this directory into the root of your Obsidian vault:
   ```
   cp -r templates/. /path/to/your/vault/
   ```

2. Review the example files to understand the expected frontmatter schema:
   - `Notes/Atomic Note Example.md` — shows the v1 frontmatter fields (`tags`, `date`, `source_doc`, `note_type: atomic`)
   - `MOCs/Topic Map - MOC.md` — shows the MOC format with two-level structure and wikilinks

3. Delete the example files after reviewing them. The pipeline will populate your vault with real notes from your documents.

4. Copy `.smart-env/` to your vault root to enable Smart Connections with the recommended local model (TaylorAI/bge-micro-v2, no API key required):
   ```
   cp -r templates/.smart-env /path/to/your/vault/
   ```

## Folder structure

After running the pipeline, your vault will have:
- `Research & Insights/` — atomic notes generated from your documents
- `Guides & Overviews/` — MOC files (one per processed document)
- `Sources/` — source document reference files

These folder names are configurable in `config.toml`.
