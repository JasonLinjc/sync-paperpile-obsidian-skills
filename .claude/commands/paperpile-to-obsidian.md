Convert a Paperpile BibTeX export into an Obsidian vault. Each paper becomes a markdown file with YAML frontmatter. PDFs are linked by default.

## Mode detection

Check `$ARGUMENTS` to determine which mode to run:

- If `--link-pdfs-only` is present → run **PDF-only workflow** (skip to "PDF-Only Workflow" below)
- Otherwise → run **Full workflow** (below)

---

## Full Workflow

### Step 1: Determine the bib file

If a bib file path is provided as `$ARGUMENTS`, use it. Otherwise, ask the user:

- Provide a local `.bib` file path
- Pull the latest `paperpile.bib` from Google Drive: `rclone copy gdrive:paperpile.bib ~/Documents/GitHub/sync-paperpile-obsidian/`

### Step 2: Archive the bib file

Copy the bib file to `~/Documents/paperpile_bib_files/` with today's date appended to the filename:

```bash
mkdir -p ~/Documents/paperpile_bib_files
# Example: paperpile.bib → paperpile_2026-03-04.bib
cp "<bib_file>" ~/Documents/paperpile_bib_files/"$(basename '<bib_file>' .bib)_$(date +%Y-%m-%d).bib"
```

### Step 3: Ask which Obsidian vault to use

List existing vaults and ask the user to pick one or create a new one:

```bash
ls ~/Documents/obsidian/
```

The vault path will be `~/Documents/obsidian/<chosen_vault>` and the papers folder is `Papers` inside it.

### Step 4: Run sync

Run `sync_obsidian.py` to create/update markdown files:

```bash
cd ~/Documents/GitHub/sync-paperpile-obsidian && conda run -n paperpile_obsidian python sync_obsidian.py --bib "<bib_file>" --vault "<vault_path>" --folder Papers
```

Note the output — specifically which files were "Created" (these are the newly added papers).

### Step 5: Link PDFs (default)

Run PDF linking with mount path:

```bash
cd ~/Documents/GitHub/sync-paperpile-obsidian && conda run -n paperpile_obsidian python sync_obsidian.py --bib "<bib_file>" --vault "<vault_path>" --folder Papers --link-pdfs --mount-path ~/gdrive
```

### Step 6: Report results

Summarize what was done:

- Number of papers synced (new/updated/removed)
- Number of PDFs linked
- Any errors or unmatched papers

---

## PDF-Only Workflow

Link PDFs to existing markdown files without running a bib sync. No `.bib` file required.

### Step 1: Determine the papers folder

If a folder path is provided in `$ARGUMENTS` (after `--link-pdfs-only`), use it. Otherwise, ask the user:

- List vaults: `ls ~/Documents/obsidian/`
- The papers folder is typically `~/Documents/obsidian/<vault>/Papers`

### Step 2: Link PDFs

```bash
cd ~/Documents/GitHub/sync-paperpile-obsidian && conda run -n paperpile_obsidian python link_pdfs.py "<papers_folder>" --mount-path ~/gdrive
```

Add `--relink` if the user wants to force a re-scan (ignore cached results).

### Step 3: Report results

Summarize:
- Number of papers found
- Number of PDFs matched
- Number of papers without matching PDF
