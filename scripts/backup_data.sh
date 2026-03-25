#!/bin/bash
# Backup data from Fly.io to local CSV files

set -e

BACKUP_DIR="./backup/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "📦 Backing up data from Fly.io..."

# Download JSONL files from the persistent volume
echo "Downloading messageboard data..."
fly ssh sftp get /data/messageboard.jsonl "$BACKUP_DIR/messageboard.jsonl"

echo "Downloading blog posts data..."
fly ssh sftp get /data/blog_posts.jsonl "$BACKUP_DIR/blog_posts.jsonl"

echo "✓ JSONL files downloaded to $BACKUP_DIR"

# Convert JSONL to CSV using Python
echo "Converting JSONL to CSV..."
python3 scripts/jsonl_to_csv.py "$BACKUP_DIR"

echo "✅ Backup complete!"
echo "Files saved in: $BACKUP_DIR"
ls -lh "$BACKUP_DIR"
