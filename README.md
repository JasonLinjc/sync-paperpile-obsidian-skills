# Paperpile to Obsidian Sync Tool

A toolkit that synchronizes your Paperpile bibliography with your Obsidian vault and optionally organizes papers by topic using LLM-based classification.

<br>

## Features

### Core Sync (`sync_obsidian.py`)

- **Creates individual markdown files** for each paper in your Obsidian vault's "Papers" folder
- **YAML frontmatter metadata** including title, authors, year, journal/conference, abstract, URL, ref_id, and type — fully compatible with Obsidian's Dataview plugin
- **Preserves user notes** — any content you add after the YAML frontmatter is preserved during sync operations
- **Human-readable filenames** using the format `Title (ref_id).md` with proper spacing and casing
- **Automatic title change detection** — when paper titles change in Paperpile, existing files are automatically renamed while preserving your notes
- **Automatic cleanup** — papers removed from Paperpile are detected and moved to a "Removed Papers" subfolder (not deleted)
- **BibLaTeX compatible** — supports both BibTeX (`year`, `journal`) and BibLaTeX (`date`, `journaltitle`) fields
- **Archive-based sync** — uses `obsidian_archive.json` to track changes and skip unchanged papers
- **CLI arguments** — configure bib path, vault path, and more without editing the script

### LLM Topic Classification (`--classify`)

- **Two-step LLM classification** using Qwen API — proposes topic categories, then assigns each paper
- **Auto-generates tags** — 2–4 kebab-case tags per paper (e.g. `gene-regulation`, `machine-learning`)
- **Organizes into subfolders** — moves papers into topic subfolders (e.g. `Papers/Gene Regulation/`)
- **Updates frontmatter** — adds `topic:` and `tags:` to YAML frontmatter plus inline `#tag` lines
- **Incremental** — only classifies new papers; use `--reclassify` to force a full redo

### Google Drive PDF Linking (`--link-pdfs` / `link_pdfs.py`)

- **Matches Google Drive PDFs** to papers by normalized title + year
- **Adds `pdf_url` to YAML frontmatter** — Obsidian wikilinks (`[[PDFs/...]]`) or Google Drive web links
- **PDF++ integration** — with `--mount-path`, generates wikilinks that open in Obsidian's PDF++ viewer
- **Incremental** — results cached in `pdf_links.json`; only new papers are scanned
- **Two entry points:**
  - `sync_obsidian.py --link-pdfs` — link PDFs during a full bib sync
  - `link_pdfs.py <folder>` — standalone script to add PDF links to any folder of existing `.md` files (no `.bib` required)

### Google Drive PDF Organizer (`organizer.py`)

- **Organizes Paperpile PDFs** on Google Drive into topic subfolders via `rclone`
- **Dry-run by default** — preview the plan before moving anything
- **Reversible** — all moves are logged and can be undone with `--undo`

### Claude Code Skill (`.claude/`)

- **`/paperpile-to-obsidian` command** — interactive workflow that walks through bib selection, vault choice, sync, and PDF linking
- **Claude-based classification** — when `--classify` is passed, Claude classifies papers directly instead of calling the Qwen API
- **Location:** `.claude/commands/paperpile-to-obsidian.md` (command) and `.claude/skills/paperpile-to-obsidian/SKILL.md` (skill definition)
- **Usage:** In Claude Code, run `/paperpile-to-obsidian` or `/paperpile-to-obsidian path/to/file.bib`

### Bib Update Checker (`check_bib.sh`)

- **Checks if `paperpile.bib`** on Google Drive is newer than the local copy
- **Compares file sizes** via `rclone lsjson`
- **Prompts to pull** if an update is available

<br>

## Setup

### 1. Install Dependencies

```bash
conda create -n paperpile_obsidian python=3.11 -y
conda activate paperpile_obsidian
pip install -r requirements_obsidian.txt
```

Or install individually:

```bash
pip install bibtexparser python-slugify openai
```

### 2. Set up Paperpile BibTeX Export

1. In Paperpile, click the gear icon (Settings) in the top-right
2. Go to "Workflows and Integrations"
3. Add a new "BibTeX Export" workflow:
   - Repository: Your GitHub repository (or local folder)
   - Export path: `paperpile.bib`
   - Set up automatic sync if desired

### 3. (Optional) Set up LLM Classification

Create a `.env` file in the project directory:

```
QWEN_API_KEY=your-api-key-here
```

For the Google Drive organizer, export the key instead:

```bash
export DASHSCOPE_API_KEY=your-api-key-here
```

### 4. (Optional) Set up rclone for Google Drive

Required for PDF linking, `organizer.py`, and syncing the bib file from Google Drive:

```bash
rclone config  # follow prompts to set up a "gdrive" remote
```

### 5. (Optional) Mount Google Drive Locally for PDF++ Integration

To open PDFs directly in Obsidian's PDF++ viewer, mount Google Drive locally:

```bash
# Install macFUSE (macOS — requires enabling kernel extensions via Startup Security Utility)
brew install --cask macfuse

# Mount Google Drive
mkdir -p ~/gdrive
rclone mount gdrive: ~/gdrive --vfs-cache-mode full --daemon

# Create symlink in your Obsidian vault
ln -s ~/gdrive/Paperpile/All\ Papers ~/Documents/obsidian/Paperpile/PDFs
```

Then use `--mount-path ~/gdrive` when linking PDFs to generate Obsidian wikilinks.

### 6. Turn On Dataview Plugin in Obsidian

1. Open Obsidian → Settings → Community plugins
2. Browse and search for "Dataview"
3. Install and enable the plugin

<br>

## Usage

### Basic Sync

```bash
# Sync bib file from Google Drive (if using rclone)
rclone copy gdrive:paperpile.bib .

# Sync to Obsidian (uses defaults)
python sync_obsidian.py
```

### Sync with Classification

```bash
# Sync + classify papers into topic folders
python sync_obsidian.py --classify

# Force re-classification of all papers
python sync_obsidian.py --classify --reclassify
```

### Link PDFs

```bash
# Link PDFs during a full bib sync (Google Drive web links)
python sync_obsidian.py --link-pdfs

# Link PDFs with Obsidian wikilinks (requires mounted Google Drive + PDFs symlink)
python sync_obsidian.py --link-pdfs --mount-path ~/gdrive

# Force re-scan of Google Drive PDFs
python sync_obsidian.py --link-pdfs --mount-path ~/gdrive --relink-pdfs
```

### Link PDFs to Existing Markdown (Standalone)

```bash
# Add PDF links to any folder of .md files (no .bib required)
python link_pdfs.py ~/Documents/obsidian/MyVault/Papers --mount-path ~/gdrive

# Force re-scan
python link_pdfs.py ~/Documents/obsidian/MyVault/Papers --mount-path ~/gdrive --relink
```

### Check for Bib Updates

```bash
# Check if paperpile.bib on Google Drive is newer than local copy
./check_bib.sh

# Check a specific local bib file
./check_bib.sh paperpile_bib/Paperpile_noncoding.bib
```

### Organize Google Drive PDFs

```bash
# Preview what would be moved (dry-run)
python organizer.py --config config.json

# Actually move the files
python organizer.py --config config.json --execute

# Undo a previous move
python organizer.py --undo moves_20240301_120000.json
```

### CLI Options

#### `sync_obsidian.py`

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--bib` | `-b` | `paperpile.bib` | Path to BibTeX file |
| `--vault` | `-v` | `~/Documents/obsidian/Paperpile` | Path to Obsidian vault |
| `--folder` | `-f` | `Papers` | Papers folder name inside the vault |
| `--archive` | `-a` | derived from bib name | Path to archive JSON file |
| `--classify` | | off | Run LLM-based topic classification after sync |
| `--reclassify` | | off | Force re-classification of all papers |
| `--link-pdfs` | | off | Match Google Drive PDFs and add `pdf_url` to frontmatter |
| `--relink-pdfs` | | off | Force re-scan of Google Drive PDFs |
| `--mount-path` | | none | Local Google Drive mount path (generates Obsidian wikilinks) |
| `--model` | | `qwen-plus` | Qwen model ID for classification |
| `--max-categories` | | `15` | Maximum number of topic categories |
| `--batch-size` | | `30` | Papers per LLM batch call |

#### `link_pdfs.py`

| Flag | Default | Description |
|------|---------|-------------|
| `path` (positional) | required | Folder containing `.md` files to link |
| `--mount-path` | none | Local Google Drive mount path (generates Obsidian wikilinks) |
| `--pdf-folder` | `PDFs` | PDF folder name in vault for wikilinks |
| `--relink` | off | Force re-scan (ignore cached `pdf_links.json`) |

<br>

## What Gets Created

For each paper, a markdown file is created:

```markdown
---
title: "Understanding BERT: A Comprehensive Analysis"
authors: "John Smith, Jane Doe"
year: 2023
journal: "Nature Machine Intelligence"
abstract: "This paper provides a comprehensive analysis..."
url: "https://example.com/paper"
pdf_url: "[[PDFs/2023/Smith et al. 2023 - Understanding BERT.pdf]]"
tags:
  - machine-learning
  - transformers
topic: "Natural Language Processing"
ref_id: "Smith2023-ab"
type: paper
---

#machine-learning #transformers

<!-- Add your notes here -->
```

The `tags:`, `topic:`, and inline `#tags` are added only when using `--classify`. The `pdf_url:` is added when using `--link-pdfs` or `link_pdfs.py`.

<br>

## File Management

- Paper files live in `Papers/` within your Obsidian vault (organized into topic subfolders when classified)
- Archive JSON (e.g. `paperpile_archive.json`) tracks the last-synced state for change detection — auto-named from bib filename
- `classification.json` caches LLM results so only new papers are classified on re-runs
- `pdf_links.json` caches PDF-to-paper matches so only new papers are scanned on re-runs
- Removed papers are moved to `Papers/Removed Papers/`, not deleted
- Filename format: `{Title} ({ref_id}).md`

<br>

## Troubleshooting

### Common Issues

1. **"Obsidian vault path does not exist"**
   - Pass `--vault /path/to/your/vault` or update `DEFAULT_VAULT_PATH` in the script

2. **"BibTeX file not found"**
   - Pass `--bib /path/to/your/file.bib` or ensure `paperpile.bib` is in the script directory

3. **Import errors**
   - Install dependencies: `pip install -r requirements_obsidian.txt`

4. **Need to start over?**
   - Delete all files in `Papers/` and delete `obsidian_archive.json`
   - To redo classification, also delete `classification.json` or use `--reclassify`

<br>

## Acknowledgments

This repo is forked from [sync-paperpile-obsidian](https://github.com/maria-antoniak/sync-paperpile-obsidian) by [Maria Antoniak](https://github.com/maria-antoniak), which provided the core BibTeX-to-Obsidian sync functionality.

### What's new in this version

- **Obsidian as the target** — generates local markdown files instead of Notion database entries
- **BibLaTeX support** — handles both BibTeX and BibLaTeX field formats
- **LLM-based topic classification** — automatically categorizes papers into topic folders using Qwen API
- **Google Drive PDF linking** — matches PDFs on Google Drive to papers and adds wikilinks for Obsidian's PDF++ viewer
- **Google Drive PDF organizer** — organizes Paperpile PDFs into topic subfolders on Google Drive
- **Claude Code skill** — interactive `/paperpile-to-obsidian` command with Claude-based classification
- **Standalone PDF linker** — `link_pdfs.py` adds PDF links to any existing markdown files without a `.bib` file
- **Bib update checker** — `check_bib.sh` detects when the Google Drive bib file has changed
