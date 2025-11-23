#!/usr/bin/env bash
set -euo pipefail

# One-shot aggressive Docker cleanup script.
# WARNING: This will remove unused images, containers, volumes, networks and builder caches.
# Use --yes or -y to skip interactive confirmation.

YES=0
if [[ "${1:-}" == "--yes" || "${1:-}" == "-y" ]]; then
  YES=1
fi

cat <<'MSG'
************************************************************
WARNING: This script will aggressively delete Docker data:
 - docker buildx/builder cache
 - unused containers, images, networks and volumes
This may remove images you still want. Proceed only if you understand.
************************************************************
MSG

if [[ $YES -ne 1 ]]; then
  read -p "Proceed? (y/N) " yn
  if [[ ! $yn =~ ^[Yy]$ ]]; then
    echo "Aborted by user"
    exit 0
  fi
fi

echo "==> Docker root dir:"
docker info --format '{{.DockerRootDir}}' || true

echo "\n==> Disk usage BEFORE cleanup:"
docker system df || true

echo "\n==> Pruning buildx / buildkit caches..."
# prune buildx builder caches
docker buildx prune --all --force || true
# older docker versions may not have separate buildx prune; also prune builder
docker builder prune --all --force || true

echo "\n==> Pruning unused containers, images, networks, volumes..."
# prune everything unused
docker system prune -a --volumes --force || true

echo "\n==> Disk usage AFTER cleanup:"
docker system df || true

echo "\nCleanup completed."
