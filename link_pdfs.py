#!/usr/bin/env python3
"""Add Google Drive PDF links to existing Obsidian markdown files.

Scans a folder of .md files, matches them to Google Drive PDFs by title+year,
and adds pdf_url to YAML frontmatter. Works with any Obsidian vault — no .bib required.
"""

import argparse
import json
import os
import re
from pathlib import Path

from sync_obsidian import (
    list_drive_pdfs,
    match_pdfs_to_entries,
    normalize_title,
    update_frontmatter_pdf_url,
)


def extract_entries_from_folder(papers_folder):
    """Scan .md files and extract ref_id, title, year from YAML frontmatter.

    Returns list of (ref_id, {"title": ..., "year": ...}) tuples.
    """
    entries = []
    for md_file in sorted(Path(papers_folder).glob("**/*.md")):
        content = md_file.read_text(encoding="utf-8")
        if not content.startswith("---\n"):
            continue

        # Extract frontmatter block
        end_idx = content.find("\n---", 1)
        if end_idx == -1:
            continue
        fm = content[4:end_idx]

        # Parse fields with regex
        title_m = re.search(r'^title:\s*"(.+?)"', fm, re.MULTILINE)
        year_m = re.search(r'^year:\s*(\d+)', fm, re.MULTILINE)
        ref_id_m = re.search(r'^ref_id:\s*"(.+?)"', fm, re.MULTILINE)

        if not title_m:
            continue

        title = title_m.group(1)
        year = year_m.group(1) if year_m else ""

        # Get ref_id from frontmatter, or fallback to filename pattern (ref_id).md
        if ref_id_m:
            ref_id = ref_id_m.group(1)
        else:
            fn_match = re.search(r'\(([^)]+)\)\.md$', md_file.name)
            ref_id = fn_match.group(1) if fn_match else md_file.stem

        entries.append((ref_id, {"title": title, "year": year}))

    return entries


def main():
    parser = argparse.ArgumentParser(
        description="Add Google Drive PDF links to existing Obsidian markdown files."
    )
    parser.add_argument(
        "path",
        help="Folder containing .md files to link"
    )
    parser.add_argument(
        "--mount-path",
        default=None,
        help="Local Google Drive mount path (e.g. ~/gdrive). Generates Obsidian wikilinks."
    )
    parser.add_argument(
        "--pdf-folder",
        default="PDFs",
        help="PDF folder name in vault for wikilinks (default: PDFs)"
    )
    parser.add_argument(
        "--relink",
        action="store_true",
        help="Force re-scan (ignore cached pdf_links.json)"
    )
    args = parser.parse_args()

    papers_folder = Path(os.path.expanduser(args.path))
    if not papers_folder.exists():
        print(f"Error: folder not found: {papers_folder}")
        return

    mount_path = os.path.expanduser(args.mount_path) if args.mount_path else None

    # Ensure PDFs symlink exists in the vault when using mount_path
    if mount_path:
        vault_path = papers_folder.parent
        pdfs_symlink = vault_path / args.pdf_folder
        drive_papers_dir = Path(mount_path) / "Paperpile" / "All Papers"
        if not pdfs_symlink.exists():
            if drive_papers_dir.exists():
                pdfs_symlink.symlink_to(drive_papers_dir)
                print(f"Created symlink: {pdfs_symlink} -> {drive_papers_dir}")
            else:
                print(f"Warning: Google Drive papers folder not found at {drive_papers_dir}")
                print(f"  PDFs symlink not created — wikilinks may not work in Obsidian.")

    cache_path = papers_folder / "pdf_links.json"

    # Load cache
    existing_links = {}
    if cache_path.exists() and not args.relink:
        with open(cache_path, "r", encoding="utf-8") as f:
            existing_links = json.load(f)
        print(f"Loaded cached links for {len(existing_links)} papers.")

    # Extract entries from .md files
    print(f"Scanning {papers_folder} for markdown files...")
    all_entries = extract_entries_from_folder(papers_folder)
    print(f"  Found {len(all_entries)} papers.")

    if args.relink or not existing_links:
        entries_to_link = all_entries
    else:
        entries_to_link = [(rid, e) for rid, e in all_entries if rid not in existing_links]

    if entries_to_link:
        print(f"\nScanning Google Drive for PDFs...")
        pdfs = list_drive_pdfs(mount_path=mount_path, pdf_folder=args.pdf_folder)
        print(f"  Found {len(pdfs)} PDFs.")
        if mount_path:
            print(f"  Using local mount: {mount_path}")

        print(f"  Matching {len(entries_to_link)} papers...")
        new_links, unmatched = match_pdfs_to_entries(pdfs, entries_to_link)

        if args.relink:
            existing_links = new_links
        else:
            existing_links.update(new_links)

        # Save cache
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(existing_links, f, indent=2, ensure_ascii=False)
        print(f"  Matched {len(new_links)} papers to PDFs.")
        if unmatched:
            print(f"  {len(unmatched)} papers without matching PDF.")
    else:
        print("\nAll papers already linked. Use --relink to force re-scan.")

    # Update frontmatter
    print("\nUpdating frontmatter with PDF URLs...")
    updated = 0
    for ref_id, info in existing_links.items():
        pattern = f"**/*({ref_id}).md"
        matching = list(papers_folder.glob(pattern))
        if matching:
            update_frontmatter_pdf_url(matching[0], info["pdf_url"])
            updated += 1
    print(f"  Updated {updated} papers.")
    print("\nDone!")


if __name__ == "__main__":
    main()
