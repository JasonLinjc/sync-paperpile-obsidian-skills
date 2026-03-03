#!/usr/bin/env python3
"""Quick test: filename parsing + Claude classification on a few sample papers."""

from organizer import parse_filename, classify_papers, load_config

# ── Test 1: Filename parsing ────────────────────────────────────────────────

sample_files = [
    "Smith - 2021 - Deep Learning for Protein Folding.pdf",
    "Chen - 2019 - Attention Mechanisms in Neural Machine Translation.pdf",
    "Garcia - 2022 - CRISPR-Cas9 Gene Editing in Cancer Therapy.pdf",
    "Wang - 2020 - Reinforcement Learning for Robotic Control.pdf",
    "Johnson - 2023 - Single-Cell RNA Sequencing of Tumor Microenvironment.pdf",
    "Lee - 2018 - Quantum Computing Algorithms for Optimization.pdf",
    "Patel - 2021 - Transformer Models for Drug Discovery.pdf",
    "bad-filename.pdf",
    "no_dashes_here.pdf",
]

print("=" * 60)
print("TEST 1: Filename parsing")
print("=" * 60)

parsed = {}
for f in sample_files:
    result = parse_filename(f)
    if result:
        parsed[f] = result
        print(f"  OK  {result['author']} | {result['year']} | {result['title']}")
    else:
        print(f"  SKIP  {f}")

assert len(parsed) == 7, f"Expected 7 parsed, got {len(parsed)}"
assert parse_filename("bad-filename.pdf") is None
print(f"\nParsing: {len(parsed)} parsed, {len(sample_files) - len(parsed)} skipped ✓")

# ── Test 2: Claude classification ────────────────────────────────────────────

print(f"\n{'=' * 60}")
print("TEST 2: Claude classification (API call)")
print("=" * 60)

titles = [parsed[f]["title"] for f in parsed]
config = load_config(None)

assignments = classify_papers(titles, config)

print(f"\nResults:")
for title, category in sorted(assignments.items(), key=lambda x: x[1]):
    print(f"  [{category}] {title}")

assert len(assignments) > 0, "No assignments returned"
print(f"\nClassification: {len(assignments)}/{len(titles)} titles assigned ✓")
print("\nAll tests passed!")
