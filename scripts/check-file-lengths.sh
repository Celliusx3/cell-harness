#!/bin/sh
# Every source file under 300 lines — backend, its tests, the MCP servers, and
# the frontend. Part of `make lint`, so it is the gate that runs after every
# change, not a review comment.
#
# 300 is the number the repo was refactored to (commit 9c9cb0f) and the size at
# which a module still reads top to bottom in one sitting. A file that needs
# more has two responsibilities; split on the seam rather than raising the cap.
set -eu

MAX=300
cd "$(dirname "$0")/.."

over=$(find backend/harness backend/tests mcp-servers frontend/app frontend/components frontend/lib \
        -type f \( -name '*.py' -o -name '*.ts' -o -name '*.tsx' \) \
        -not -path '*/node_modules/*' -not -path '*/.venv/*' -not -path '*/__pycache__/*' \
        -not -path '*/.next/*' \
    | xargs wc -l \
    | awk -v max="$MAX" '$2 != "total" && $1 > max { printf "%5d  %s\n", $1, $2 }' \
    | sort -rn)

if [ -n "$over" ]; then
    echo "files over $MAX lines:"
    echo "$over"
    exit 1
fi
echo "every file is under $MAX lines"
