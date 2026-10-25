#!/bin/sh
# Builds the chat pages into desktop/build/pages from a copy of frontend/.
set -eu

cd "$(dirname "$0")/.."
FRONTEND="$(cd ../frontend && pwd)"
WORK="$(pwd)/build/frontend"
PAGES="$(pwd)/build/pages"

rm -rf "$WORK" "$PAGES"
mkdir -p "$WORK"
rsync -a --exclude node_modules --exclude .next --exclude tsconfig.tsbuildinfo "$FRONTEND/" "$WORK/"

cd "$WORK"
npm ci
BACKEND_PORT=4886 npx next build

cp -R .next/standalone "$PAGES"
cp -R .next/static "$PAGES/.next/static"
if [ -d public ]; then
    cp -R public "$PAGES/public"
fi
test -f "$PAGES/server.js"
echo "pages built: $PAGES/server.js"
