# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running scripts

Always use `conda run -n paperpile_obsidian` to run scripts:
```bash
cd ~/Documents/GitHub/sync-paperpile-obsidian-skills && conda run -n paperpile_obsidian python sync_obsidian.py
```

### Key commands
- **Basic sync:** `conda run -n paperpile_obsidian python sync_obsidian.py`
- **Sync + link PDFs:** `conda run -n paperpile_obsidian python sync_obsidian.py --link-pdfs --mount-path ~/gdrive`
- **Sync + classify:** `conda run -n paperpile_obsidian python sync_obsidian.py --classify`
- **Full sync (all features):** `conda run -n paperpile_obsidian python sync_obsidian.py --classify --link-pdfs --mount-path ~/gdrive`
- **Force reclassify:** `conda run -n paperpile_obsidian python sync_obsidian.py --classify --reclassify`
- **Force re-link PDFs:** `conda run -n paperpile_obsidian python sync_obsidian.py --link-pdfs --mount-path ~/gdrive --relink-pdfs`
- **Link PDFs to existing .md files:** `conda run -n paperpile_obsidian python link_pdfs.py ~/Documents/obsidian/MyVault/Papers --mount-path ~/gdrive`
- **Check for bib updates:** `./check_bib.sh`
- **Organize Google Drive PDFs:** `conda run -n paperpile_obsidian python organizer.py --config config.json`
- **Run tests:** `conda run -n paperpile_obsidian python test_organizer.py` (requires API key; makes live Qwen API calls)
- **Sync bib file from Google Drive:** `rclone copy gdrive:paperpile.bib .`
- **Mount Google Drive:** `rclone mount gdrive: ~/gdrive --vfs-cache-mode full --daemon`

## API Keys
- `QWEN_API_KEY` stored in `.env` (loaded automatically by sync_obsidian.py)
- `DASHSCOPE_API_KEY` used by organizer.py (same Qwen/DashScope service)
- Used for LLM-based paper classification via Qwen API (OpenAI-compatible endpoint at `dashscope.aliyuncs.com`)

## Default paths
- **Obsidian vault:** `~/Documents/obsidian/Paperpile` (1,671 papers, full library)
- **Papers folder:** `Papers/` inside the vault
- **PDF symlink:** `PDFs/` inside the vault → symlinks to `~/gdrive/Paperpile/All Papers`
- **Bib file:** `paperpile.bib` (local, synced from Google Drive)
- **Google Drive mount:** `~/gdrive` (via `rclone mount`, requires macFUSE)

## Important: do NOT touch the old vault
- `~/Documents/obsidian/Noncoding_variant_survery` is the old 97-paper survey vault
- Never point this script at that vault — it is a separate project
- If running with `--vault`, always use `~/Documents/obsidian/Paperpile`

## Architecture

### Scripts overview

**`sync_obsidian.py`** — BibTeX → Obsidian markdown sync
- Parses `paperpile.bib` with `bibtexparser`, creates/updates one `.md` file per paper in the vault
- Supports both BibTeX (`year`, `journal`) and BibLaTeX (`date`, `journaltitle`) fields
- Archive auto-derives from bib filename (e.g. `paperpile.bib` → `paperpile_archive.json`)
- User notes (anything below YAML frontmatter) are preserved across updates via `extract_user_content_from_markdown()`
- Title changes trigger file renames while preserving content
- Papers removed from BibTeX are moved to `Removed Papers/` (not deleted)
- With `--classify`: calls Qwen API to assign topic categories, moves files into subfolders, updates frontmatter tags
- With `--link-pdfs`: matches Google Drive PDFs to BibTeX entries by normalized title+year, adds `pdf_url` wikilink to frontmatter

**`link_pdfs.py`** — Standalone PDF linker for existing markdown files
- Scans a folder of `.md` files, extracts `title` and `year` from YAML frontmatter
- Matches to Google Drive PDFs by normalized title+year (imports shared functions from `sync_obsidian.py`)
- Adds `pdf_url` wikilink to frontmatter — no `.bib` file required
- Caches results in `<folder>/pdf_links.json`; `--relink` forces re-scan

**`check_bib.sh`** — Bib file update checker
- Compares local `paperpile.bib` file size against Google Drive via `rclone lsjson`
- Prompts to pull if sizes differ
- Usage: `./check_bib.sh [local_bib_path]`

**`organizer.py`** — Google Drive PDF organizer
- Lists Paperpile PDFs via `rclone`, parses `Author - Year - Title.pdf` filenames
- Classifies by topic using same two-step LLM approach, moves files into subfolders on Google Drive
- Dry-run by default; `--execute` to actually move files
- Logs all moves to `moves_TIMESTAMP.json`; reversible with `--undo`
- Configured via `config.json` (see `config.example.json` for format)

### Shared LLM classification pattern (two-step)
Both scripts use the same approach with Qwen via the OpenAI-compatible client:
1. **Step A — Propose categories:** Send all titles (+abstracts in sync_obsidian), ask LLM to propose 5–15 topic categories
2. **Step B — Assign papers:** Send titles in batches (`--batch-size`, default 30), ask LLM to assign each to a category (sync_obsidian also generates tags)

### PDF linking
- `list_drive_pdfs()` calls `rclone lsjson` to scan `gdrive:Paperpile/All Papers/` recursively
- `match_pdfs_to_entries()` matches by `(normalized_title, year)` key — normalizes by stripping LaTeX braces, lowercasing, removing punctuation
- PDF filename format on Google Drive: `Author et al. YEAR - Title.pdf` (regex differs from organizer.py's `Author - Year - Title.pdf`)
- With `--mount-path`: generates Obsidian wikilinks `[[PDFs/2025/Author et al. 2025 - Title.pdf]]` for PDF++ integration
- Without `--mount-path`: generates Google Drive web links `https://drive.google.com/file/d/{ID}/view`
- **Auto-creates `PDFs/` symlink** in the vault when `--mount-path` is used and the symlink doesn't exist yet (points to `<mount_path>/Paperpile/All Papers`)
- Results cached in `pdf_links.json`; `--relink-pdfs` forces full re-scan

### Key data flow
```
paperpile.bib → bibtexparser → archive diff → create/update .md files
                                                    ↓ (--classify)
                                           Qwen API → topics + tags → organize into subfolders
                                                    ↓ (--link-pdfs)
                                           rclone lsjson → match by title+year → add pdf_url to frontmatter
```

### Archive format (`paperpile_archive.json`)
Maps `ref_id` → `{ entry: {title, authors, year, ...}, notes: "user content" }`. Used for change detection — if entry fields match the archive, the file is skipped. Auto-named from bib filename.

### Classification cache (`classification.json`)
Maps `ref_id` → `{ topic: str, tags: [str] }`. Persists LLM results so only new papers are classified on subsequent runs. Use `--reclassify` to force a full redo.

### PDF links cache (`pdf_links.json`)
Maps `ref_id` → `{ pdf_url: str, drive_id: str, pdf_name: str }`. Persists rclone scan results so only new papers are matched on subsequent runs. Use `--relink-pdfs` to force a full redo.

### File naming
Format: `{Title} ({ref_id}).md` — the `ref_id` (e.g. `Smith2023-ab`) is the stable identifier used to match files across renames. `find_existing_file_by_ref_id()` searches recursively through topic subfolders.

### CLI options (sync_obsidian.py)
All configuration is via CLI arguments with sensible defaults:
- `-b/--bib` — BibTeX file (default: `paperpile.bib`)
- `-v/--vault` — Obsidian vault path (default: `~/Documents/obsidian/Paperpile`)
- `-f/--folder` — Papers folder name (default: `Papers`)
- `-a/--archive` — Archive JSON path (default: derived from bib filename)
- `--classify` — Enable LLM classification after sync
- `--reclassify` — Force re-classification of all papers
- `--model` — Qwen model ID (default: `qwen-plus`)
- `--max-categories` — Upper bound on topic categories (default: 15)
- `--batch-size` — Papers per LLM batch call (default: 30)
- `--link-pdfs` — Match Google Drive PDFs and add pdf_url to frontmatter
- `--relink-pdfs` — Force re-scan of Google Drive PDFs
- `--mount-path` — Local Google Drive mount path (e.g. `~/gdrive`); generates Obsidian wikilinks instead of web URLs

## Claude Code skill (`.claude/`)

- **Command:** `.claude/commands/paperpile-to-obsidian.md` — run via `/paperpile-to-obsidian` in Claude Code
- **Skill:** `.claude/skills/paperpile-to-obsidian/SKILL.md` — interactive workflow with two modes:
  - **Full workflow** (default): bib selection → archive → vault choice → sync → PDF linking → optional classification
  - **PDF-only** (`--link-pdfs-only`): link PDFs to existing markdown files without a bib sync
- Each step explains its goal to the user and reports progress before moving on
- When `--classify` is used via the skill, Claude classifies papers directly instead of calling the Qwen API
- PDF linking auto-creates the `PDFs/` symlink if missing in the target vault
- Usage examples:
  - `/paperpile-to-obsidian path/to/file.bib` — full sync + PDF linking
  - `/paperpile-to-obsidian --link-pdfs-only ~/Documents/obsidian/MyVault/Papers` — PDF linking only
  - `/paperpile-to-obsidian --classify` — full sync with Claude-based classification

## Dependencies

`requirements_obsidian.txt`: `bibtexparser`, `python-slugify`, `openai` (used as client for Qwen/DashScope API)

## Local setup notes
- Google Drive mounted at `~/gdrive` via `rclone mount gdrive: ~/gdrive --vfs-cache-mode full --daemon`
- macFUSE installed (required for rclone mount on macOS, kernel extensions enabled via Startup Security Utility)
- `PDFs/` in the vault is a symlink → `~/gdrive/Paperpile/All Papers` (for PDF++ integration; auto-created by `--link-pdfs` when missing)
- After creating a new `PDFs/` symlink, Obsidian must be restarted to index it
- Git remote is SSH: `git@github.com:JasonLinjc/sync-paperpile-obsidian.git`
