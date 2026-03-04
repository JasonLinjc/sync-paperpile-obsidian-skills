#!/usr/bin/env python3

import argparse
import bibtexparser
import json
import os
import re
import shutil
from pathlib import Path
from slugify import slugify

"""
Sync Paperpile BibTeX export to Obsidian markdown files.
Creates a new markdown file for each paper in the Papers folder of your Obsidian vault.
This version preserves user notes when updating files.
"""

# Default configuration (can be overridden via command-line arguments)
DEFAULT_BIB_PATH = 'paperpile.bib'
DEFAULT_VAULT_PATH = os.path.expanduser('~/Documents/obsidian/Paperpile')
DEFAULT_PAPERS_FOLDER = 'Papers'


def default_archive_path(bib_path):
    """Derive archive filename from bib filename, e.g. paperpile.bib -> paperpile_archive.json"""
    bib_stem = Path(bib_path).stem
    return f"{bib_stem}_archive.json"


def clean_str(s):
    """Clean string for markdown use"""
    if not s:
        return ''
    s = re.sub(r'[^A-Za-z0-9\s&.,-;:/?()"\']+', '', s) 
    return ' '.join(s.split())


def format_authors(test_string):
    """Format authors from BibTeX format to readable format"""
    if not test_string:
        return ''
    
    authors = [a.split(',') for a in test_string.split(';')]
    formatted_authors = [] 
    for a in authors:
        if len(a) == 1:
            formatted_authors.append(a[0].strip())
        elif len(a) == 2:
            formatted_authors.append(a[1].strip() + ' ' + a[0].strip())
        else:
            formatted_authors.append(' '.join(a).strip())
    return ', '.join(formatted_authors)


def create_safe_filename(title, ref_id):
    """Create a safe filename for the markdown file"""
    # Maximum filename length for most filesystems (leaving some buffer)
    MAX_FILENAME_LENGTH = 250
    
    if title:
        # Use title with normal spaces and casing, just remove invalid filename characters
        safe_title = re.sub(r'[<>:"/\\|?*]', '', title)
        safe_title = safe_title.strip()
        
        # Calculate space needed for ref_id and file extension
        ref_id_part = f" ({ref_id}).md"
        available_space = MAX_FILENAME_LENGTH - len(ref_id_part)
        
        # Truncate title if needed
        if len(safe_title) > available_space:
            safe_title = safe_title[:available_space].rstrip()
        
        filename = f"{safe_title}{ref_id_part}"
    else:
        filename = f"{ref_id}.md"
    
    # Final safety check - if somehow still too long, truncate more aggressively
    if len(filename) > MAX_FILENAME_LENGTH:
        base_name = filename.rsplit('.', 1)[0]  # Remove .md
        truncated_base = base_name[:MAX_FILENAME_LENGTH - 3]  # Leave room for .md
        filename = f"{truncated_base}.md"
    
    return filename


def get_bib_entry(entry):
    """Extract and format data from a BibTeX entry"""
    ref_id = entry.get('ID', '')
    title = ''
    authors = ''
    year = ''
    link = None
    abstract = ''
    journal = ''
    booktitle = ''

    if 'title' in entry:
        title = entry['title']
        title = clean_str(title)

    if 'author' in entry:
        authors = entry['author']
        authors = authors.replace(' and ', '; ')
        authors = authors.replace(' And ', '; ')
        authors = clean_str(authors)
        authors = format_authors(authors)
           
    if 'year' in entry:
        year = entry['year']
        year = clean_str(year)
    elif 'date' in entry:
        # BibLaTeX format: date = {2025-04-08}
        m = re.search(r'(\d{4})', entry['date'])
        if m:
            year = m.group(1)

    if 'url' in entry:
        link = entry['url']

    if 'abstract' in entry:
        abstract = entry['abstract']
        abstract = ' '.join(abstract.split())
        abstract = clean_str(abstract)

    if 'journal' in entry:
        journal = clean_str(entry['journal'])
    elif 'journaltitle' in entry:
        journal = clean_str(entry['journaltitle'])
        
    if 'booktitle' in entry:
        booktitle = clean_str(entry['booktitle'])

    # Keywords removed - not needed
    
    formatted_entry = {
        'title': title,
        'authors': authors,
        'year': year,
        'ref_id': ref_id,
        'link': link,
        'abstract': abstract,
        'journal': journal,
        'booktitle': booktitle
    }
           
    return ref_id, formatted_entry


def extract_user_content_from_markdown(filepath):
    """Extract user-added content from existing markdown file"""
    if not filepath.exists():
        return {'notes': ''}
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        return {'notes': ''}
    
    # Extract everything after the YAML frontmatter as notes
    # Split on the closing --- of frontmatter
    notes = ''
    if '---\n\n' in content:
        parts = content.split('---\n\n', 1)
        if len(parts) > 1:
            notes_content = parts[1].strip()
            # Only keep content if it's not just the placeholder comment
            if notes_content and notes_content != '<!-- Add your notes here -->':
                notes = notes_content

    
    return {'notes': notes}


def create_markdown_content(entry, user_content=None):
    """Create markdown content for a paper with YAML frontmatter"""
    title = entry.get('title', 'Untitled')
    authors = entry.get('authors', '')
    year = entry.get('year', '')
    ref_id = entry.get('ref_id', '')
    link = entry.get('link', '')
    abstract = entry.get('abstract', '')
    journal = entry.get('journal', '')
    booktitle = entry.get('booktitle', '')
    
    # Get user content or use defaults
    if user_content is None:
        user_content = {'notes': ''}
    
    notes = user_content.get('notes', '')
    
    # Create YAML frontmatter
    content = "---\n"
    content += f"title: \"{title}\"\n"
    if authors:
        content += f"authors: \"{authors}\"\n"
    if year:
        # Ensure year is always a number in YAML (extract digits only)
        year_digits = re.sub(r'\D', '', year)
        if year_digits:
            content += f"year: {int(year_digits)}\n"
    if journal:
        content += f"journal: \"{journal}\"\n"
    if booktitle:
        content += f"conference: \"{booktitle}\"\n"
    if abstract:
        # Escape quotes in abstract for YAML
        escaped_abstract = abstract.replace('"', '\\"')
        content += f"abstract: \"{escaped_abstract}\"\n"
    if link:
        content += f"url: \"{link}\"\n"
    content += f"ref_id: \"{ref_id}\"\n"
    content += "type: paper\n"
    content += "---\n\n"
    
    # Notes section - preserve user content or use placeholder
    if notes:
        content += f"{notes}\n\n"
    else:
        content += "<!-- Add your notes here -->\n\n"
    
    return content


def classify_papers(entries, model="qwen-plus", max_categories=15, batch_size=30):
    """Classify papers into topics and generate tags using Qwen API.

    Two-step process:
      Step A — Propose 5-max_categories topic categories from all paper titles+abstracts.
      Step B — Assign each paper to a category + generate tags (batched).

    Args:
        entries: list of dicts with keys 'ref_id', 'title', 'abstract'
        model: Qwen model ID (e.g. qwen-plus, qwen-max, qwen-turbo)
        max_categories: upper bound on number of categories
        batch_size: papers per API call in step B

    Returns:
        dict mapping ref_id -> {'topic': str, 'tags': [str]}
    """
    from openai import OpenAI

    # Load API key from .env file if not already in environment
    api_key = os.environ.get("QWEN_API_KEY")
    if not api_key:
        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().strip().splitlines():
                if line.startswith("QWEN_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
    if not api_key:
        raise RuntimeError("QWEN_API_KEY not found in environment or .env file")

    client = OpenAI(
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    # Build a compact summary of all papers for step A
    paper_lines = []
    for e in entries:
        abstract_snippet = (e.get("abstract") or "")[:300]
        paper_lines.append(f"- [{e['ref_id']}] {e['title']}\n  Abstract: {abstract_snippet}")
    papers_block = "\n".join(paper_lines)

    # --- Step A: propose categories ---
    step_a_prompt = (
        f"You are an expert research librarian. Below is a list of {len(entries)} academic papers "
        f"(title + abstract snippet). Propose between 5 and {max_categories} broad topic categories "
        "that cover all of these papers. Categories should be descriptive but concise (2-5 words each).\n\n"
        "Return ONLY a JSON array of category name strings. No explanation.\n\n"
        f"Papers:\n{papers_block}"
    )

    print(f"  Step A: Proposing topic categories for {len(entries)} papers...")
    resp_a = client.chat.completions.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": step_a_prompt}],
    )
    categories_text = resp_a.choices[0].message.content.strip()
    # Parse JSON — handle markdown code fences
    categories_text = re.sub(r"^```json\s*", "", categories_text)
    categories_text = re.sub(r"\s*```$", "", categories_text)
    categories = json.loads(categories_text)
    print(f"  Proposed {len(categories)} categories: {categories}")

    # --- Step B: assign papers to categories + generate tags (batched) ---
    classifications = {}
    for i in range(0, len(entries), batch_size):
        batch = entries[i : i + batch_size]
        batch_lines = []
        for e in batch:
            abstract_snippet = (e.get("abstract") or "")[:300]
            batch_lines.append(f"- [{e['ref_id']}] {e['title']}\n  Abstract: {abstract_snippet}")
        batch_block = "\n".join(batch_lines)

        step_b_prompt = (
            "You are an expert research librarian. Assign each paper below to exactly ONE of these categories:\n"
            f"{json.dumps(categories)}\n\n"
            "For each paper, also suggest 2-4 short lowercase kebab-case tags (e.g. 'gene-regulation', "
            "'machine-learning', 'CRISPR', 'enhancer'). Tags should capture specific methods, topics, "
            "or concepts.\n\n"
            "Return ONLY a JSON object mapping each ref_id to an object with 'topic' (string) and 'tags' (array of strings). "
            "No explanation.\n\n"
            f"Papers:\n{batch_block}"
        )

        batch_num = i // batch_size + 1
        total_batches = (len(entries) + batch_size - 1) // batch_size
        print(f"  Step B: Classifying batch {batch_num}/{total_batches} ({len(batch)} papers)...")

        resp_b = client.chat.completions.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": step_b_prompt}],
        )
        result_text = resp_b.choices[0].message.content.strip()
        result_text = re.sub(r"^```json\s*", "", result_text)
        result_text = re.sub(r"\s*```$", "", result_text)
        batch_result = json.loads(result_text)
        classifications.update(batch_result)

    return classifications


def organize_by_topic(papers_folder, classifications):
    """Move paper markdown files into topic subfolders.

    Args:
        papers_folder: Path to the Papers/ directory
        classifications: dict mapping ref_id -> {'topic': str, 'tags': [str]}

    Returns:
        number of files moved
    """
    moved = 0
    for ref_id, info in classifications.items():
        topic = info["topic"]
        # Create topic subfolder
        topic_folder = papers_folder / topic
        topic_folder.mkdir(exist_ok=True)

        # Find the file for this ref_id (could be in papers_folder or a subfolder)
        pattern = f"**/*({ref_id}).md"
        matching = list(papers_folder.glob(pattern))
        if not matching:
            continue

        filepath = matching[0]
        target = topic_folder / filepath.name

        # Skip if already in correct folder
        if filepath.parent == topic_folder:
            continue

        # Handle name collision in target folder
        if target.exists():
            print(f"  Warning: {filepath.name} already exists in {topic}/, skipping move")
            continue

        shutil.move(str(filepath), str(target))
        moved += 1
        print(f"  Moved: {filepath.name} → {topic}/")

    return moved


def update_frontmatter_tags(filepath, tags, topic):
    """Add/merge tags and topic into a paper's YAML frontmatter.

    Preserves any existing manually-added tags. Writes inline #tag lines
    after frontmatter.

    Args:
        filepath: Path to the markdown file
        tags: list of tag strings from LLM
        topic: topic category string
    """
    content = filepath.read_text(encoding="utf-8")

    # Split frontmatter from body
    if not content.startswith("---\n"):
        return
    end_idx = content.index("\n---", 1)
    fm_block = content[4:end_idx]  # between opening --- and closing ---
    body = content[end_idx + 4:]   # after closing ---\n

    # Parse existing tags from frontmatter
    existing_tags = []
    fm_lines = fm_block.split("\n")
    new_fm_lines = []
    in_tags_list = False
    has_topic = False
    for line in fm_lines:
        if line.startswith("tags:"):
            in_tags_list = True
            continue  # we'll re-add the tags block
        if in_tags_list:
            m = re.match(r"\s+-\s+(.*)", line)
            if m:
                existing_tags.append(m.group(1).strip())
                continue
            else:
                in_tags_list = False
        if line.startswith("topic:"):
            has_topic = True
            new_fm_lines.append(f'topic: "{topic}"')
            continue
        new_fm_lines.append(line)

    if not has_topic:
        # Insert topic before ref_id line if possible
        insert_idx = None
        for j, l in enumerate(new_fm_lines):
            if l.startswith("ref_id:"):
                insert_idx = j
                break
        if insert_idx is not None:
            new_fm_lines.insert(insert_idx, f'topic: "{topic}"')
        else:
            new_fm_lines.append(f'topic: "{topic}"')

    # Merge tags: existing + new, deduplicated, preserving order
    merged = list(dict.fromkeys(existing_tags + tags))

    # Add tags block before ref_id (or at end)
    insert_idx = None
    for j, l in enumerate(new_fm_lines):
        if l.startswith("topic:"):
            insert_idx = j
            break
    tags_yaml = "tags:\n" + "\n".join(f"  - {t}" for t in merged)
    if insert_idx is not None:
        new_fm_lines.insert(insert_idx, tags_yaml)
    else:
        new_fm_lines.append(tags_yaml)

    new_fm = "\n".join(new_fm_lines)

    # Build inline tag line
    tag_line = " ".join(f"#{t}" for t in merged)

    # Remove any existing inline tag lines from body (lines that are only #tags)
    body_lines = body.split("\n")
    cleaned_body_lines = []
    for bl in body_lines:
        if bl.strip() and all(tok.startswith("#") for tok in bl.strip().split()):
            continue  # skip existing inline tag lines
        cleaned_body_lines.append(bl)
    body = "\n".join(cleaned_body_lines)

    # Ensure body starts with newlines then tag line
    body = body.lstrip("\n")
    body = f"\n{tag_line}\n\n{body}" if body else f"\n{tag_line}\n"

    filepath.write_text(f"---\n{new_fm}\n---{body}", encoding="utf-8")


def parse_pdf_filename(name):
    """Parse Paperpile PDF filename: 'Author et al. YEAR - Title.pdf' -> dict or None."""
    m = re.match(r"^(.+?)\s+(\d{4})\s*-\s*(.+)\.pdf$", name, re.IGNORECASE)
    if not m:
        return None
    return {"author": m.group(1).strip(), "year": m.group(2), "title": m.group(3).strip()}


def normalize_title(title):
    """Normalize a title for fuzzy matching between BibTeX and PDF filenames."""
    t = re.sub(r'[{}]', '', title)       # Remove LaTeX braces
    t = re.sub(r'\s+', ' ', t)           # Collapse whitespace
    t = t.lower()
    t = re.sub(r'[^a-z0-9 ]', '', t)    # Remove all punctuation
    return ' '.join(t.split())


def list_drive_pdfs(rclone_remote="gdrive:", paperpile_folder="Paperpile", mount_path=None, pdf_folder="PDFs"):
    """List all PDFs from Google Drive Paperpile/All Papers/ using rclone.

    Args:
        rclone_remote: rclone remote name (e.g. "gdrive:")
        paperpile_folder: folder name on Google Drive
        mount_path: if set, generate Obsidian wikilinks using pdf_folder
                    (e.g. [[PDFs/2025/Author et al. 2025 - Title.pdf]])
        pdf_folder: name of the PDF symlink folder inside the vault (default: "PDFs")

    Returns list of dicts with keys: name, path, drive_id, pdf_url, author, year, title.
    """
    import subprocess

    scan_path = f"{rclone_remote}{paperpile_folder}/All Papers"
    result = subprocess.run(
        ["rclone", "lsjson", scan_path, "--files-only", "--include", "*.pdf", "--recursive", "--no-modtime", "--no-mimetype"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  Warning: rclone error: {result.stderr.strip()}")
        return []

    raw_entries = json.loads(result.stdout)
    pdfs = []
    for entry in raw_entries:
        parsed = parse_pdf_filename(entry["Name"])
        if parsed:
            rel_path = entry.get("Path", entry["Name"])
            if mount_path:
                # Obsidian wikilink: [[PDFs/2025/Author et al. 2025 - Title.pdf]]
                pdf_url = f"[[{pdf_folder}/{rel_path}]]"
            else:
                pdf_url = f"https://drive.google.com/file/d/{entry['ID']}/view"
            pdfs.append({
                "name": entry["Name"],
                "path": rel_path,
                "drive_id": entry["ID"],
                "pdf_url": pdf_url,
                "author": parsed["author"],
                "year": parsed["year"],
                "title": parsed["title"],
            })
    return pdfs


def match_pdfs_to_entries(pdfs, bib_entries):
    """Match Google Drive PDFs to BibTeX entries by normalized title + year.

    Args:
        pdfs: list of dicts from list_drive_pdfs()
        bib_entries: list of (ref_id, formatted_entry) tuples

    Returns:
        (matched, unmatched_entries)
        matched: dict mapping ref_id -> {pdf_url, drive_id, pdf_name}
    """
    # Build lookup: (normalized_title, year) -> list of PDFs
    pdf_lookup = {}
    for pdf in pdfs:
        key = (normalize_title(pdf["title"]), pdf["year"])
        pdf_lookup.setdefault(key, []).append(pdf)

    matched = {}
    unmatched_entries = []
    used_pdfs = set()

    for ref_id, entry in bib_entries:
        norm_title = normalize_title(entry["title"])
        year = entry.get("year", "")
        key = (norm_title, year)

        if key in pdf_lookup:
            for pdf in pdf_lookup[key]:
                if pdf["drive_id"] not in used_pdfs:
                    matched[ref_id] = {
                        "pdf_url": pdf["pdf_url"],
                        "drive_id": pdf["drive_id"],
                        "pdf_name": pdf["name"],
                    }
                    used_pdfs.add(pdf["drive_id"])
                    break
            else:
                unmatched_entries.append(ref_id)
        else:
            unmatched_entries.append(ref_id)

    return matched, unmatched_entries


def update_frontmatter_pdf_url(filepath, pdf_url):
    """Add or update pdf_url in a paper's YAML frontmatter."""
    content = filepath.read_text(encoding="utf-8")

    if not content.startswith("---\n"):
        return
    end_idx = content.index("\n---", 1)
    fm_block = content[4:end_idx]
    body = content[end_idx + 4:]

    fm_lines = fm_block.split("\n")
    new_fm_lines = []
    has_pdf_url = False

    for line in fm_lines:
        if line.startswith("pdf_url:"):
            has_pdf_url = True
            new_fm_lines.append(f'pdf_url: "{pdf_url}"')
        else:
            new_fm_lines.append(line)

    if not has_pdf_url:
        # Insert before ref_id line, or at end
        insert_idx = None
        for j, l in enumerate(new_fm_lines):
            if l.startswith("ref_id:"):
                insert_idx = j
                break
        if insert_idx is not None:
            new_fm_lines.insert(insert_idx, f'pdf_url: "{pdf_url}"')
        else:
            new_fm_lines.append(f'pdf_url: "{pdf_url}"')

    new_fm = "\n".join(new_fm_lines)
    filepath.write_text(f"---\n{new_fm}\n---{body}", encoding="utf-8")


def find_existing_file_by_ref_id(papers_folder, ref_id):
    """Find existing file for a given ref_id, even if filename differs.
    Searches papers_folder and all subfolders (topic directories)."""
    # Search recursively to find files in topic subfolders too
    pattern = f"**/*({ref_id}).md"
    matching_files = list(papers_folder.glob(pattern))

    if matching_files:
        return matching_files[0]
    return None


def create_obsidian_file(entry, papers_folder, user_content=None):
    """Create or update an Obsidian markdown file for a paper"""
    ref_id = entry.get('ref_id', '')
    new_filename = create_safe_filename(entry.get('title', ''), ref_id)
    new_filepath = papers_folder / new_filename
    
    # Check if a file with this ref_id already exists (possibly with different title)
    existing_file = find_existing_file_by_ref_id(papers_folder, ref_id)
    
    # Extract existing user content
    if user_content is None:
        if existing_file:
            # Extract from existing file (even if it has a different name)
            user_content = extract_user_content_from_markdown(existing_file)
        else:
            user_content = extract_user_content_from_markdown(new_filepath)
    
    # Handle file renaming if title changed
    if existing_file and existing_file.name != new_filename:
        print(f"Title changed - renaming: {existing_file.name} → {new_filename}")
        try:
            # If target filename already exists, we need to handle the conflict
            if new_filepath.exists():
                # This shouldn't happen normally, but let's be safe
                print(f"Warning: Target file {new_filename} already exists. Backing up existing file.")
                backup_name = f"{new_filepath.stem}_backup_{ref_id}{new_filepath.suffix}"
                new_filepath.rename(papers_folder / backup_name)
            
            # Rename the existing file to match new title
            existing_file.rename(new_filepath)
            
        except Exception as e:
            print(f"Error renaming file {existing_file.name}: {e}")
            # Continue with the existing file path if rename failed
            new_filepath = existing_file
    
    content = create_markdown_content(entry, user_content)
    
    # Write the file
    with open(new_filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return new_filepath, user_content


def load_archive(archive_path):
    """Load the archive of previously processed entries"""
    if os.path.exists(archive_path):
        with open(archive_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_archive(archive, archive_path):
    """Save the archive of processed entries"""
    with open(archive_path, 'w', encoding='utf-8') as f:
        json.dump(archive, f, indent=2, ensure_ascii=False)


def entries_are_equal(archive_entry, bib_entry):
    """Compare archive entry with bib entry to detect changes"""
    if isinstance(archive_entry, dict) and 'entry' in archive_entry:
        # New format archive entry
        return archive_entry['entry'] == bib_entry
    else:
        # Old format archive entry - treat as different to force update
        return False


def cleanup_removed_papers(papers_folder, current_ref_ids, archive):
    """Move papers that are no longer in Paperpile to Removed Papers folder"""
    removed_folder = papers_folder / "Removed Papers"
    removed_folder.mkdir(exist_ok=True)
    
    moved_count = 0
    
    # Find papers in archive that are no longer in current BibTeX
    for ref_id in list(archive.keys()):
        if ref_id not in current_ref_ids:
            # Find the file for this ref_id (search recursively for topic subfolders)
            pattern = f"**/*({ref_id}).md"
            matching_files = list(papers_folder.glob(pattern))

            for file_path in matching_files:
                # Skip files already in Removed Papers
                if file_path.parent == removed_folder:
                    continue
                new_path = removed_folder / file_path.name
                try:
                    file_path.rename(new_path)
                    print(f"Moved to Removed Papers: {file_path.name}")
                    moved_count += 1
                except Exception as e:
                    print(f"Error moving {file_path.name}: {e}")
            
            # Remove from archive
            del archive[ref_id]
    
    return moved_count


def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description='Sync Paperpile BibTeX export to Obsidian markdown files.'
    )
    parser.add_argument(
        '-b', '--bib',
        default=DEFAULT_BIB_PATH,
        help=f'Path to BibTeX file (default: {DEFAULT_BIB_PATH})'
    )
    parser.add_argument(
        '-v', '--vault',
        default=DEFAULT_VAULT_PATH,
        help=f'Path to Obsidian vault (default: {DEFAULT_VAULT_PATH})'
    )
    parser.add_argument(
        '-f', '--folder',
        default=DEFAULT_PAPERS_FOLDER,
        help=f'Papers folder name inside the vault (default: {DEFAULT_PAPERS_FOLDER})'
    )
    parser.add_argument(
        '-a', '--archive',
        default=None,
        help='Path to archive JSON file (default: derived from bib filename, e.g. paperpile_archive.json)'
    )
    parser.add_argument(
        '--classify',
        action='store_true',
        help='Run LLM-based topic classification after sync'
    )
    parser.add_argument(
        '--model',
        default='qwen-plus',
        help='Qwen model to use for classification (default: qwen-plus)'
    )
    parser.add_argument(
        '--max-categories',
        type=int,
        default=15,
        help='Maximum number of topic categories (default: 15)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=30,
        help='Number of papers per Claude batch call (default: 30)'
    )
    parser.add_argument(
        '--reclassify',
        action='store_true',
        help='Force re-classification even if classification.json exists'
    )
    parser.add_argument(
        '--link-pdfs',
        action='store_true',
        help='Match Google Drive PDFs to papers and add pdf_url to frontmatter'
    )
    parser.add_argument(
        '--relink-pdfs',
        action='store_true',
        help='Force re-scan of Google Drive PDFs (ignore pdf_links.json cache)'
    )
    parser.add_argument(
        '--mount-path',
        default=None,
        help='Local mount path for Google Drive (e.g. ~/gdrive). Uses file:// URLs instead of web links.'
    )
    return parser.parse_args()


def main():
    """Main function to sync BibTeX to Obsidian"""
    args = parse_args()

    bib_path = args.bib
    vault_path = Path(os.path.expanduser(args.vault))
    papers_folder_name = args.folder
    archive_path = args.archive if args.archive else default_archive_path(bib_path)

    # Check if Obsidian vault path exists
    if not vault_path.exists():
        print(f"Error: Obsidian vault path does not exist: {vault_path}")
        print("Use --vault to specify your Obsidian vault path.")
        return

    # Create Papers folder if it doesn't exist
    papers_folder = vault_path / papers_folder_name
    papers_folder.mkdir(exist_ok=True)

    # Load the BibTeX file
    if not os.path.exists(bib_path):
        print(f"Error: BibTeX file not found: {bib_path}")
        return

    print(f"Loading BibTeX file: {bib_path}")

    # Use older bibtexparser API
    parser = bibtexparser.bparser.BibTexParser()
    parser.ignore_nonstandard_types = True
    parser.homogenize_fields = False
    parser.interpolate_strings = False

    with open(bib_path) as bib_file:
        bibliography = bibtexparser.load(bib_file, parser=parser)

    # Load archive of previously processed entries
    archive = load_archive(archive_path)

    # Collect current ref_ids for cleanup
    current_ref_ids = set()

    # Process entries
    processed_count = 0
    new_count = 0
    updated_count = 0

    for entry in bibliography.entries:
        ref_id, formatted_entry = get_bib_entry(entry)
        current_ref_ids.add(ref_id)

        # Check if this entry has changed since last processing
        if ref_id in archive and entries_are_equal(archive[ref_id], formatted_entry):
            continue  # No changes, skip

        # Create or update the Obsidian file
        try:
            filepath, user_content = create_obsidian_file(
                formatted_entry,
                papers_folder
            )

            if ref_id in archive:
                updated_count += 1
                print(f"Updated: {filepath.name}")
            else:
                new_count += 1
                print(f"Created: {filepath.name}")

            # Update archive with formatted entry and user content
            archive[ref_id] = {
                'entry': formatted_entry,
                'notes': user_content.get('notes', '')
            }
            processed_count += 1

        except Exception as e:
            print(f"Error processing {ref_id}: {e}")

    # Clean up removed papers
    moved_count = cleanup_removed_papers(papers_folder, current_ref_ids, archive)

    # Save updated archive
    save_archive(archive, archive_path)

    # Print summary
    print(f"\nSync complete!")
    print(f"Total entries in BibTeX: {len(bibliography.entries)}")
    print(f"New files created: {new_count}")
    print(f"Files updated: {updated_count}")
    print(f"Files processed this run: {processed_count}")
    if moved_count > 0:
        print(f"Files moved to Removed Papers: {moved_count}")
    print(f"Papers folder: {papers_folder}")

    # --- LLM Classification ---
    if args.classify:
        classification_path = Path(archive_path).parent / "classification.json"

        # Load existing classifications if available
        existing_classifications = {}
        if classification_path.exists() and not args.reclassify:
            with open(classification_path, "r", encoding="utf-8") as f:
                existing_classifications = json.load(f)
            print(f"\nLoaded existing classification for {len(existing_classifications)} papers.")

        # Determine which papers need classification
        all_entries = []
        for entry in bibliography.entries:
            ref_id, formatted_entry = get_bib_entry(entry)
            all_entries.append({
                "ref_id": ref_id,
                "title": formatted_entry["title"],
                "abstract": formatted_entry.get("abstract", ""),
            })

        if args.reclassify or not existing_classifications:
            # Classify all papers
            entries_to_classify = all_entries
        else:
            # Only classify papers not yet classified
            entries_to_classify = [
                e for e in all_entries if e["ref_id"] not in existing_classifications
            ]

        if entries_to_classify:
            print(f"\nClassifying {len(entries_to_classify)} papers with {args.model}...")
            new_classifications = classify_papers(
                entries_to_classify,
                model=args.model,
                max_categories=args.max_categories,
                batch_size=args.batch_size,
            )
            if args.reclassify:
                existing_classifications = new_classifications
            else:
                existing_classifications.update(new_classifications)

            # Save classifications
            with open(classification_path, "w", encoding="utf-8") as f:
                json.dump(existing_classifications, f, indent=2, ensure_ascii=False)
            print(f"  Saved classifications to {classification_path}")
        else:
            print("\nAll papers already classified. Use --reclassify to force re-classification.")

        # Organize files into topic subfolders
        print("\nOrganizing papers into topic folders...")
        moved = organize_by_topic(papers_folder, existing_classifications)
        print(f"  {moved} file(s) moved into topic folders.")

        # Update frontmatter tags
        print("\nUpdating frontmatter tags and topic...")
        updated = 0
        for ref_id, info in existing_classifications.items():
            pattern = f"**/*({ref_id}).md"
            matching = list(papers_folder.glob(pattern))
            if matching:
                update_frontmatter_tags(matching[0], info["tags"], info["topic"])
                updated += 1
        print(f"  Updated frontmatter for {updated} papers.")
        print("\nClassification complete!")

    # --- PDF Linking ---
    if args.link_pdfs:
        mount_path = os.path.expanduser(args.mount_path) if args.mount_path else None

        # Ensure PDFs symlink exists in the vault when using mount_path
        if mount_path:
            pdfs_symlink = vault_path / "PDFs"
            drive_papers_dir = Path(os.path.expanduser(mount_path)) / "Paperpile" / "All Papers"
            if not pdfs_symlink.exists():
                if drive_papers_dir.exists():
                    pdfs_symlink.symlink_to(drive_papers_dir)
                    print(f"\nCreated symlink: {pdfs_symlink} -> {drive_papers_dir}")
                else:
                    print(f"\n  Warning: Google Drive papers folder not found at {drive_papers_dir}")
                    print(f"  PDFs symlink not created — wikilinks may not work in Obsidian.")

        pdf_links_path = Path(archive_path).parent / "pdf_links.json"

        # Load existing links if available
        existing_links = {}
        if pdf_links_path.exists() and not args.relink_pdfs:
            with open(pdf_links_path, "r", encoding="utf-8") as f:
                existing_links = json.load(f)
            print(f"\nLoaded existing PDF links for {len(existing_links)} papers.")

        # Determine which papers need linking
        all_bib_entries = []
        for entry in bibliography.entries:
            ref_id, formatted_entry = get_bib_entry(entry)
            all_bib_entries.append((ref_id, formatted_entry))

        if args.relink_pdfs or not existing_links:
            entries_to_link = all_bib_entries
        else:
            entries_to_link = [
                (rid, e) for rid, e in all_bib_entries if rid not in existing_links
            ]

        if entries_to_link:
            print(f"\nScanning Google Drive for PDFs...")
            pdfs = list_drive_pdfs(mount_path=mount_path)
            print(f"  Found {len(pdfs)} PDFs on Google Drive.")
            if mount_path:
                print(f"  Using local mount: {mount_path}")

            print(f"  Matching {len(entries_to_link)} papers...")
            new_links, unmatched_entries = match_pdfs_to_entries(pdfs, entries_to_link)

            if args.relink_pdfs:
                existing_links = new_links
            else:
                existing_links.update(new_links)

            # Save cache
            with open(pdf_links_path, "w", encoding="utf-8") as f:
                json.dump(existing_links, f, indent=2, ensure_ascii=False)
            print(f"  Matched {len(new_links)} papers to PDFs.")
            if unmatched_entries:
                print(f"  {len(unmatched_entries)} papers without matching PDF.")
        else:
            print("\nAll papers already linked. Use --relink-pdfs to force re-scan.")

        # Update frontmatter with PDF URLs
        print("\nUpdating frontmatter with PDF URLs...")
        updated = 0
        for ref_id, info in existing_links.items():
            pattern = f"**/*({ref_id}).md"
            matching = list(papers_folder.glob(pattern))
            if matching:
                update_frontmatter_pdf_url(matching[0], info["pdf_url"])
                updated += 1
        print(f"  Updated frontmatter for {updated} papers.")
        print("\nPDF linking complete!")


if __name__ == "__main__":
    main()
