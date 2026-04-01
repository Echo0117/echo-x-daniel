#!/bin/sh
set -eu

DATA_DIR="${RAILWAY_VOLUME_MOUNT_PATH:-/app/data}"
SEED_DIR="${SEED_DIR:-/seed-data}"

mkdir -p "$DATA_DIR"

copy_seed_if_missing() {
    filename="$1"
    if [ ! -f "$DATA_DIR/$filename" ] && [ -f "$SEED_DIR/$filename" ]; then
        echo "Initializing $filename in $DATA_DIR"
        cp "$SEED_DIR/$filename" "$DATA_DIR/$filename"
    fi
}

copy_seed_if_missing "messageboard.csv"
copy_seed_if_missing "blog.csv"
copy_seed_if_missing "messageboard.jsonl"
copy_seed_if_missing "blog_posts.jsonl"

echo "Data initialization complete (target: $DATA_DIR)"
