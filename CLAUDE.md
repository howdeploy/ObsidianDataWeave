# ObsidianDataWeave — Project Rules

## Disabled Features

- **Plan mode disabled.** Never use `EnterPlanMode` in this project — it causes hangs. Start implementing directly.

## Architecture

- All vault paths come from `config.toml` (git-ignored, never commit)
- Global skill registered at `~/.claude/skills/obsidian-dataweave/` by `install.sh`
- References in the global skill are symlinks to repo files — `git pull` auto-updates them
- No personal data (notes, .docx, vault paths) should ever be committed
