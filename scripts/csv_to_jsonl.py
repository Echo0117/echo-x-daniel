#!/usr/bin/env python3
"""Convert CSV files to JSONL format for local storage"""
import csv
import json
from pathlib import Path

def csv_to_jsonl(csv_path: Path, jsonl_path: Path):
    """Convert a CSV file to JSONL format"""
    with open(csv_path, 'r', encoding='utf-8') as csv_file:
        reader = csv.DictReader(csv_file)

        with open(jsonl_path, 'w', encoding='utf-8') as jsonl_file:
            for row in reader:
                # Convert 'null' strings to actual None
                item = {k: (None if v == 'null' else v) for k, v in row.items()}
                jsonl_file.write(json.dumps(item, ensure_ascii=False) + '\n')

    print(f"✓ Converted {csv_path.name} -> {jsonl_path.name}")

if __name__ == "__main__":
    data_dir = Path(__file__).parent.parent / "apps" / "api" / "data"

    # Convert blog CSV
    csv_to_jsonl(
        data_dir / "blog.csv",
        data_dir / "blog_posts.jsonl"
    )

    # Convert messageboard CSV
    csv_to_jsonl(
        data_dir / "messageboard.csv",
        data_dir / "messageboard.jsonl"
    )

    print("\n✓ All conversions complete!")
