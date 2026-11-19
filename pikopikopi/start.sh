#!/bin/sh
# Pikopikopi startup script.
# 1. Download coffee images to the persistent disk if they are missing.
# 2. Start the FastAPI/uvicorn server.
set -e

DATA_DIR="${DATA_DIR:-/var/data}"
IMAGES_DIR="$DATA_DIR/images"
IMAGES_READY_FLAG="$DATA_DIR/.images_downloaded"

# Download coffee images on first run (or if the flag is missing).
if [ ! -f "$IMAGES_READY_FLAG" ]; then
  echo "[start.sh] First run — downloading coffee images to $IMAGES_DIR ..."
  python scripts/download_coffee_images.py --per-class 3 --pause 0.5 || true
  touch "$IMAGES_READY_FLAG"
  echo "[start.sh] Image download complete."
else
  echo "[start.sh] Coffee images already present — skipping download."
fi

echo "[start.sh] Starting uvicorn on port ${PORT:-10000} ..."
exec uvicorn app:app --host 0.0.0.0 --port "${PORT:-10000}"
