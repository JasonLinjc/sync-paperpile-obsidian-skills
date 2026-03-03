#!/bin/bash
# Check if paperpile.bib on Google Drive is newer than the local copy.
# Usage: ./check_bib.sh [local_bib_path]

LOCAL_BIB="${1:-paperpile.bib}"
REMOTE_BIB="gdrive:paperpile.bib"

if [ ! -f "$LOCAL_BIB" ]; then
    echo "No local bib found. Pulling from Google Drive..."
    rclone copy "$REMOTE_BIB" .
    echo "Downloaded $LOCAL_BIB"
    exit 0
fi

LOCAL_SIZE=$(stat -f%z "$LOCAL_BIB" 2>/dev/null || stat -c%s "$LOCAL_BIB" 2>/dev/null)
REMOTE_INFO=$(rclone lsjson "$REMOTE_BIB" 2>/dev/null)

if [ -z "$REMOTE_INFO" ]; then
    echo "Error: cannot reach $REMOTE_BIB"
    exit 1
fi

REMOTE_SIZE=$(echo "$REMOTE_INFO" | python3 -c "import json,sys; print(json.load(sys.stdin)[0]['Size'])")

if [ "$LOCAL_SIZE" = "$REMOTE_SIZE" ]; then
    echo "Up to date (local=$LOCAL_SIZE bytes, remote=$REMOTE_SIZE bytes)"
else
    echo "Update available! (local=$LOCAL_SIZE bytes, remote=$REMOTE_SIZE bytes)"
    read -p "Pull latest? [y/N] " answer
    if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
        rclone copy "$REMOTE_BIB" .
        echo "Updated $LOCAL_BIB"
    fi
fi
