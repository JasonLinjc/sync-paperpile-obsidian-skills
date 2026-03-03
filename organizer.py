#!/usr/bin/env python3
"""Paperpile Google Drive Organizer — classify papers by topic using LLM."""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from openai import OpenAI

DEFAULT_CONFIG = {
    "paperpile_folder_name": "Paperpile",
    "max_categories": 15,
    "model": "qwen-plus",
    "api_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "api_key_env": "DASHSCOPE_API_KEY",
    "batch_size": 30,
    "rclone_remote": "gdrive:",
}


def load_config(path: str | None) -> dict:
    config = dict(DEFAULT_CONFIG)
    if path and Path(path).exists():
        with open(path) as f:
            config.update(json.load(f))
    elif Path("config.json").exists():
        with open("config.json") as f:
            config.update(json.load(f))
    return config


# ── rclone helpers ───────────────────────────────────────────────────────────


def _rclone(*args: str) -> subprocess.CompletedProcess:
    """Run an rclone command and return the result."""
    result = subprocess.run(
        ["rclone", *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"rclone error: {result.stderr.strip()}", file=sys.stderr)
    return result


def list_pdfs(remote: str, folder: str) -> list[str]:
    """List all PDF filenames directly in the given folder."""
    path = f"{remote}{folder}"
    result = _rclone("lsf", path, "--files-only", "--include", "*.pdf")
    if result.returncode != 0:
        sys.exit(f"Error listing files in {path}")
    return [line for line in result.stdout.strip().splitlines() if line]


def ensure_subfolder(remote: str, parent: str, name: str):
    """Create a subfolder if it doesn't exist."""
    path = f"{remote}{parent}/{name}"
    _rclone("mkdir", path)


def move_file(remote: str, folder: str, filename: str, dest_subfolder: str):
    """Move a file from folder/ to folder/dest_subfolder/."""
    src = f"{remote}{folder}/{filename}"
    dst = f"{remote}{folder}/{dest_subfolder}/{filename}"
    result = _rclone("moveto", src, dst)
    if result.returncode != 0:
        print(f"  Warning: failed to move {filename}")


def move_file_back(remote: str, folder: str, filename: str, from_subfolder: str):
    """Move a file back from folder/subfolder/ to folder/."""
    src = f"{remote}{folder}/{from_subfolder}/{filename}"
    dst = f"{remote}{folder}/{filename}"
    result = _rclone("moveto", src, dst)
    if result.returncode != 0:
        print(f"  Warning: failed to move back {filename}")


# ── Filename parsing ─────────────────────────────────────────────────────────


def parse_filename(name: str) -> dict | None:
    """Parse 'Author - Year - Title.pdf' → {author, year, title}, or None."""
    m = re.match(r"^(.+?)\s*-\s*(\d{4})\s*-\s*(.+)\.pdf$", name, re.IGNORECASE)
    if not m:
        return None
    return {"author": m.group(1).strip(), "year": m.group(2), "title": m.group(3).strip()}


# ── LLM classification ───────────────────────────────────────────────────────


def _create_llm_client(config: dict) -> OpenAI:
    """Create an OpenAI-compatible client from config."""
    api_key = os.environ.get(config["api_key_env"])
    if not api_key:
        sys.exit(
            f"Error: {config['api_key_env']} environment variable not set.\n"
            f"Export it with: export {config['api_key_env']}='your-key-here'"
        )
    return OpenAI(api_key=api_key, base_url=config["api_base_url"])


def classify_papers(titles: list[str], config: dict) -> dict[str, str]:
    """Two-step LLM classification: propose categories, then assign each paper."""
    client = _create_llm_client(config)
    model = config["model"]
    max_cats = config["max_categories"]
    batch_size = config["batch_size"]

    title_list = "\n".join(f"- {t}" for t in titles)

    # Step 1: Propose categories
    print(f"\n[LLM] Proposing topic categories for {len(titles)} papers...")
    cat_resp = client.chat.completions.create(
        model=model,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": (
                    f"I have a library of academic papers. Here are all the titles:\n\n"
                    f"{title_list}\n\n"
                    f"Propose between 3 and {max_cats} topic categories that would best "
                    f"organize this library. Each category should be a short, clear label "
                    f"(2-4 words). Return ONLY a JSON array of strings, e.g. "
                    f'["Machine Learning", "Genomics", "Neuroscience"]. '
                    f"No other text."
                ),
            }
        ],
    )
    cat_text = cat_resp.choices[0].message.content.strip()
    # Extract JSON array even if wrapped in markdown fences
    json_match = re.search(r"\[.*\]", cat_text, re.DOTALL)
    if not json_match:
        sys.exit(f"Error: Could not parse categories from LLM response:\n{cat_text}")
    categories = json.loads(json_match.group())
    print(f"[LLM] Categories: {', '.join(categories)}")

    # Step 2: Assign papers to categories in batches
    assignments: dict[str, str] = {}
    for i in range(0, len(titles), batch_size):
        batch = titles[i : i + batch_size]
        batch_list = "\n".join(f"- {t}" for t in batch)
        cat_json = json.dumps(categories)

        print(f"[LLM] Classifying batch {i // batch_size + 1} ({len(batch)} papers)...")
        assign_resp = client.chat.completions.create(
            model=model,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Assign each paper title to exactly one of these categories: {cat_json}\n\n"
                        f"Paper titles:\n{batch_list}\n\n"
                        f"Return ONLY a JSON object mapping each title (exactly as given) to its "
                        f"category. Example: {{\"Paper Title\": \"Category\"}}. No other text."
                    ),
                }
            ],
        )
        resp_text = assign_resp.choices[0].message.content.strip()
        json_match = re.search(r"\{.*\}", resp_text, re.DOTALL)
        if not json_match:
            print(f"Warning: Could not parse assignments for batch {i // batch_size + 1}, skipping")
            continue
        batch_assignments = json.loads(json_match.group())
        assignments.update(batch_assignments)

    return assignments


# ── Undo ─────────────────────────────────────────────────────────────────────


def undo_moves(remote: str, folder: str, moves_file: str):
    """Reverse moves recorded in a moves JSON file."""
    with open(moves_file) as f:
        moves = json.load(f)
    print(f"Undoing {len(moves)} moves from {moves_file}...")
    for entry in moves:
        print(f"  Moving back: {entry['filename']}")
        move_file_back(remote, folder, entry["filename"], entry["category"])
    print("Done. All files moved back to original location.")


# ── Main ─────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Organize Paperpile PDFs by topic using LLM")
    parser.add_argument("--execute", action="store_true", help="Actually move files (default is dry-run)")
    parser.add_argument("--config", type=str, default=None, help="Path to config JSON file")
    parser.add_argument("--undo", type=str, default=None, help="Undo moves from a moves JSON log file")
    args = parser.parse_args()

    config = load_config(args.config)
    remote = config["rclone_remote"]
    folder = config["paperpile_folder_name"]

    # Handle undo
    if args.undo:
        undo_moves(remote, folder, args.undo)
        return

    # List PDFs
    print(f"Listing PDFs in {remote}{folder}/ ...")
    pdf_names = list_pdfs(remote, folder)
    if not pdf_names:
        print("No PDF files found in the Paperpile folder. Nothing to do.")
        return
    print(f"Found {len(pdf_names)} PDFs")

    # Parse filenames
    parsed = {}
    skipped = []
    for name in pdf_names:
        info = parse_filename(name)
        if info:
            parsed[name] = info
        else:
            skipped.append(name)

    if skipped:
        print(f"\nSkipping {len(skipped)} files with unrecognized format:")
        for s in skipped:
            print(f"  - {s}")

    if not parsed:
        print("No parseable papers found. Nothing to classify.")
        return

    titles = [parsed[name]["title"] for name in parsed]
    print(f"\nClassifying {len(titles)} papers...")

    # Classify
    assignments = classify_papers(titles, config)

    # Build move plan: filename → category
    move_plan = []
    title_to_filename = {parsed[name]["title"]: name for name in parsed}
    unmatched = []
    for title, category in assignments.items():
        filename = title_to_filename.get(title)
        if filename:
            move_plan.append({"filename": filename, "category": category})
        else:
            unmatched.append(title)

    if unmatched:
        print(f"\nWarning: {len(unmatched)} titles from LLM didn't match any filename.")

    # Print plan
    categories_used = sorted(set(m["category"] for m in move_plan))
    print(f"\n{'=' * 60}")
    print(f"ORGANIZATION PLAN — {len(move_plan)} papers → {len(categories_used)} categories")
    print(f"{'=' * 60}")
    for cat in categories_used:
        papers = [m for m in move_plan if m["category"] == cat]
        print(f"\n  {cat}/ ({len(papers)} papers)")
        for p in papers:
            print(f"   {p['filename']}")

    if not args.execute:
        print(f"\n{'=' * 60}")
        print("DRY RUN — no files were moved.")
        print("Run with --execute to apply these changes.")
        print(f"{'=' * 60}")
        return

    # Execute moves
    print(f"\nMoving files...")
    created_folders: set[str] = set()
    moves_log = []

    for entry in move_plan:
        cat = entry["category"]
        if cat not in created_folders:
            ensure_subfolder(remote, folder, cat)
            created_folders.add(cat)

        print(f"  Moving '{entry['filename']}' → {cat}/")
        move_file(remote, folder, entry["filename"], cat)
        moves_log.append({
            "filename": entry["filename"],
            "category": cat,
        })

    # Write undo log
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"moves_{timestamp}.json"
    with open(log_file, "w") as f:
        json.dump(moves_log, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"Done! Moved {len(moves_log)} papers into {len(created_folders)} topic folders.")
    print(f"Undo log saved to: {log_file}")
    print(f"To undo: python organizer.py --undo {log_file}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
