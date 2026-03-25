#!/bin/sh
# Initialize data directory with seed data if empty

DATA_DIR="/data"
SEED_DIR="/app/apps/api/data"

# Copy seed data if /data is empty
if [ ! -f "$DATA_DIR/messageboard.jsonl" ] && [ -f "$SEED_DIR/messageboard.jsonl" ]; then
    echo "Initializing messageboard data..."
    cp "$SEED_DIR/messageboard.jsonl" "$DATA_DIR/"
fi

if [ ! -f "$DATA_DIR/blog_posts.jsonl" ] && [ -f "$SEED_DIR/blog_posts.jsonl" ]; then
    echo "Initializing blog posts data..."
    cp "$SEED_DIR/blog_posts.jsonl" "$DATA_DIR/"
fi

echo "Data initialization complete"
