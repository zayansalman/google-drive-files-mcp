#!/usr/bin/env bash
# Move a file into a YYYY-MM folder (created if missing) under a parent folder.
# Handy for filing exports/reports into month buckets.
#
# Usage:
#   ./file-into-dated-folder.sh <file-url-or-id> [parent-folder-name-or-id]
#
# Assumes google-drive-files-mcp is installed and `setup` has been run once.

set -euo pipefail

FILE="${1:?usage: file-into-dated-folder.sh <file-url-or-id> [parent]}"
PARENT="${2:-root}"
MONTH="$(date +%Y-%m)"

# Create (or reuse) the YYYY-MM folder under PARENT, capture its id.
FOLDER_ID="$(
  google-drive-files-mcp mkdir "${MONTH}" --parent "${PARENT}" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])'
)"

google-drive-files-mcp move "${FILE}" "${FOLDER_ID}"
echo "filed ${FILE} into ${MONTH} (folder ${FOLDER_ID})"
