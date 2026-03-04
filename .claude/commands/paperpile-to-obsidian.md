Convert a Paperpile BibTeX export into an Obsidian vault. Each paper becomes a markdown file with YAML frontmatter. PDFs are linked by default.

## Mode detection

Check `$ARGUMENTS` to determine which mode to run:

- If `--link-pdfs-only` is present → run **PDF-only workflow** (skip to "PDF-Only Workflow" below)
- Otherwise → run **Full workflow** (below)

---

## Full Workflow

### Step 1: Determine the bib file

**Goal:** Locate the BibTeX file exported from Paperpile that contains all paper metadata.

If a bib file path is provided as `$ARGUMENTS`, use it. Otherwise, ask the user:

- Provide a local `.bib` file path
- Pull the latest `paperpile.bib` from Google Drive: `rclone copy gdrive:paperpile.bib ~/Documents/GitHub/sync-paperpile-obsidian-skills/`

Tell the user which bib file will be used.

### Step 2: Archive the bib file

**Goal:** Save a backup copy of the bib file with today's date, so previous exports are preserved.

Copy the bib file to `~/Documents/paperpile_bib_files/` with today's date appended to the filename:

```bash
mkdir -p ~/Documents/paperpile_bib_files
# Example: paperpile.bib → paperpile_2026-03-04.bib
cp "<bib_file>" ~/Documents/paperpile_bib_files/"$(basename '<bib_file>' .bib)_$(date +%Y-%m-%d).bib"
```

Tell the user the archive location.

### Step 3: Ask which Obsidian vault to use

**Goal:** Choose the target Obsidian vault where paper markdown files will be created or updated.

List existing vaults and ask the user to pick one or create a new one:

```bash
ls ~/Documents/obsidian/
```

The vault path will be `~/Documents/obsidian/<chosen_vault>` and the papers folder is `Papers` inside it.

### Step 4: Run sync

**Goal:** Parse the bib file and create/update one markdown file per paper. New papers get created, changed papers get updated (preserving user notes), and papers removed from the bib are moved to a `Removed Papers/` subfolder.

```bash
cd ~/Documents/GitHub/sync-paperpile-obsidian-skills && conda run -n paperpile_obsidian python sync_obsidian.py --bib "<bib_file>" --vault "<vault_path>" --folder Papers
```

Tell the user how many papers were created, updated, and removed.

### Step 5: Link PDFs (default)

**Goal:** Match each paper to its PDF on Google Drive by title+year, then add an Obsidian wikilink (`pdf_url`) to the frontmatter so the PDF opens directly in Obsidian's PDF++ viewer. A `PDFs/` symlink is auto-created in the vault if missing.

```bash
cd ~/Documents/GitHub/sync-paperpile-obsidian-skills && conda run -n paperpile_obsidian python sync_obsidian.py --bib "<bib_file>" --vault "<vault_path>" --folder Papers --link-pdfs --mount-path ~/gdrive
```

Tell the user how many PDFs were matched and how many papers have no matching PDF.

### Step 6: Report results

**Goal:** Give the user a clear summary of everything that happened.

Summarize:

- Number of papers synced (new/updated/removed)
- Number of PDFs linked
- Any errors or unmatched papers

---

## PDF-Only Workflow

**Goal:** Link PDFs to existing markdown files without running a bib sync. Useful when papers already exist in the vault but don't have PDF links yet. No `.bib` file required.

### Step 1: Determine the papers folder

**Goal:** Locate the folder containing the `.md` paper files to link.

If a folder path is provided in `$ARGUMENTS` (after `--link-pdfs-only`), use it. Otherwise, ask the user:

- List vaults: `ls ~/Documents/obsidian/`
- The papers folder is typically `~/Documents/obsidian/<vault>/Papers`

Tell the user which folder will be scanned.

### Step 2: Link PDFs

**Goal:** Scan Google Drive for PDFs, match them to papers by title+year, and add `pdf_url` wikilinks to frontmatter. Only new/unlinked papers are processed (cached results are reused). A `PDFs/` symlink is auto-created in the vault if missing.

```bash
cd ~/Documents/GitHub/sync-paperpile-obsidian-skills && conda run -n paperpile_obsidian python link_pdfs.py "<papers_folder>" --mount-path ~/gdrive
```

Add `--relink` if the user wants to force a re-scan (ignore cached results).

### Step 3: Report results

**Goal:** Tell the user what happened.

Summarize:
- Number of papers found
- Number of PDFs matched
- Number of papers without matching PDF
