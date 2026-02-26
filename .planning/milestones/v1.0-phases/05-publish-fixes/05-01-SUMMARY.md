---
phase: 05-publish-fixes
plan: 01
subsystem: infra
tags: [python, pyyaml, requirements, install, readme, config]

# Dependency graph
requires:
  - phase: 04-publish
    provides: install.sh, requirements.txt, README.md, config.example.toml
provides:
  - requirements.txt declaring PyYAML>=6.0 alongside python-docx
  - install.sh installing pyyaml for all package managers
  - README.md with correct parse_docx.py script name in EN and RU sections
  - config.example.toml without dead [processing] section
affects: [new-user-onboarding, pip-install-flow, readme-docs]

# Tech tracking
tech-stack:
  added: [PyYAML>=6.0]
  patterns: []

key-files:
  created: []
  modified:
    - requirements.txt
    - install.sh
    - README.md
    - config.example.toml

key-decisions:
  - "PyYAML declared as explicit dependency (>=6.0) — previously used via string interpolation without declaring the dep, causing clean-venv failures"
  - "Dead [processing] config key removed from config.example.toml — default_note_type was never read by any script"

patterns-established: []

requirements-completed: [DIST-01, DIST-02]

# Metrics
duration: 1min
completed: 2026-02-26
---

# Phase 5 Plan 01: Publish Fixes Summary

**PyYAML declared as pip dependency and installed by install.sh; README parse_docx.py typo fixed in EN+RU; dead [processing] config key removed from example config**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-26T08:39:23Z
- **Completed:** 2026-02-26T08:40:37Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- requirements.txt now declares PyYAML>=6.0 — clean virtualenv installs will get both python-docx and PyYAML
- install.sh installs pyyaml alongside python-docx for both pacman (Arch/Manjaro) and all other package managers
- README.md references the correct script name `parse_docx.py` in both EN and RU "What happens under the hood" sections
- config.example.toml cleaned of dead `[processing]` section that was never consumed by any script

## Task Commits

Each task was committed atomically:

1. **Task 1: Add PyYAML dependency to requirements.txt and install.sh** - `45310cd` (feat)
2. **Task 2: Fix README typo and remove dead config key** - `eb575f6` (fix)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `requirements.txt` - Added PyYAML>=6.0 on second line
- `install.sh` - Both pip3 install calls now include pyyaml
- `README.md` - Fixed parse_doc.py -> parse_docx.py in lines 62 and 182
- `config.example.toml` - Removed [processing] section and trailing blank line

## Decisions Made

- PyYAML declared as explicit dependency (>=6.0) — previously generate_notes.py used string interpolation over PyYAML without declaring it, causing clean-venv failures for new users
- Dead [processing] config key removed from config.example.toml — default_note_type was never read by any script (Phase 03 decision: string interpolation over PyYAML for frontmatter)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All v1.0 milestone audit gaps are now closed
- New-user E2E flow works on clean systems without pre-installed PyYAML
- No further phases planned

## Self-Check: PASSED

All files confirmed present:
- requirements.txt: FOUND
- install.sh: FOUND
- README.md: FOUND
- config.example.toml: FOUND
- 05-01-SUMMARY.md: FOUND

All commits confirmed:
- 45310cd (Task 1: PyYAML dependency): FOUND
- eb575f6 (Task 2: README typo + dead config): FOUND

---
*Phase: 05-publish-fixes*
*Completed: 2026-02-26*
