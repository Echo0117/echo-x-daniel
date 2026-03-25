#!/usr/bin/env python3
"""Convert JSONL files to CSV format"""
import json
import csv
import sys
from pathlib import Path

def jsonl_to_csv(jsonl_path: Path, csv_path: Path, fieldnames: list):
    """Convert a JSONL file to CSV format"""
    with open(jsonl_path, 'r', encoding='utf-8') as jsonl_file:
        with open(csv_path, 'w', encoding='utf-8', newline='') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()

            for line in jsonl_file:
                if line.strip():
                    item = json.loads(line)
                    # Convert None to empty string for CSV
                    row = {k: (item.get(k) if item.get(k) is not None else '') for k in fieldnames}
                    writer.writerow(row)

    print(f"✓ Converted {jsonl_path.name} -> {csv_path.name}")

def main():
    if len(sys.argv) < 2:
        print("Usage: jsonl_to_csv.py <backup_directory>")
        sys.exit(1)

    backup_dir = Path(sys.argv[1])

    # Convert messageboard
    messageboard_jsonl = backup_dir / "messageboard.jsonl"
    if messageboard_jsonl.exists():
        jsonl_to_csv(
            messageboard_jsonl,
            backup_dir / "messageboard.csv",
            ["id", "author", "content", "created_at", "title"]
        )

    # Convert blog posts
    blog_jsonl = backup_dir / "blog_posts.jsonl"
    if blog_jsonl.exists():
        jsonl_to_csv(
            blog_jsonl,
            backup_dir / "blog_posts.csv",
            ["id", "author", "body", "cover_url", "created_at", "slug", "tags", "title", "updated_at"]
        )

    print("\n✅ All conversions complete!")

if __name__ == "__main__":
    main()
