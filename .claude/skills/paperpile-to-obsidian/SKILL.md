---
name: paperpile-to-obsidian
description: Convert a Paperpile .bib file into an Obsidian vault with markdown files per paper, PDF links, and optional Claude-powered classification.
---

# Paperpile to Obsidian

Convert a Paperpile BibTeX export into an Obsidian vault. Each paper becomes a markdown file with YAML frontmatter. PDFs are linked by default. Classification is optional.

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

Copy the bib file to `~/Documents/paperpile_bib_files/` for archival:

```bash
mkdir -p ~/Documents/paperpile_bib_files
cp "<bib_file>" ~/Documents/paperpile_bib_files/
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

### Step 6: Classify papers (optional)

Only if `--classify` or `--reclassify` is in `$ARGUMENTS`.

**Do NOT use the Qwen API.** Claude performs classification directly:

1. Read the markdown files that need classification:
   - `--classify`: only the newly created files from Step 4
   - `--reclassify`: all `.md` files in the Papers folder

2. For each paper, read its `title` and `abstract` from the YAML frontmatter.

3. First, propose 5-15 topic categories based on all the paper titles and abstracts. Present these to the user for approval.

4. Then for each paper, assign:
   - A `topic` (one of the approved categories)
   - 2-4 `tags` in kebab-case (e.g., `gene-regulation`, `machine-learning`)

5. Update each markdown file:
   - Add/update `topic:` and `tags:` in the YAML frontmatter
   - Add inline `#tag` lines after the frontmatter
   - Move the file into a subfolder matching its topic: `Papers/<Topic>/`

### Step 7: Report results

Summarize what was done:
- Number of papers synced (new/updated/removed)
- Number of PDFs linked
- Number of papers classified (if applicable)
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
