#!/bin/sh
# Fills desktop/build/bundle with what the packaged app runs, laid out the way packagedLayout reads it.
set -eu

cd "$(dirname "$0")/.."
PYTHON_VERSION=3.13.6
DENO_VERSION=2.8.3
DENO_ZIP=deno-aarch64-apple-darwin.zip
DENO_SHA256=88b350be928fdba0e5d8142ff7c101a17133426371e3cf5ed0e0f74e62476f6c
DENO_RELEASE="https://github.com/denoland/deno/releases/download/v$DENO_VERSION"
NODE_VERSION=24.22.1
NODE_TARBALL="node-v$NODE_VERSION-darwin-arm64.tar.gz"
NODE_SHA256=89c682593d76cd44233fa53b1563264e7de9cbb189cad169135c5b4fadfbc0a7
UV_VERSION=0.13.5
UV_TARBALL=uv-aarch64-apple-darwin.tar.gz
UV_SHA256=743f85035a1996ecb350659e01cd9faea9709829be09b1b4b03c73eaf3c9cd73
SERVERS="instagram places markets computer"
BUILD="$(pwd)/build"
BUNDLE="$(pwd)/build/bundle"
UV_PYTHON="$BUILD/uv-python"
REQUIREMENTS="$BUILD/requirements.txt"

rm -rf "$BUNDLE"
mkdir -p "$BUNDLE"

uv python install "$PYTHON_VERSION" --install-dir "$UV_PYTHON" --no-bin
INTERPRETER="$(UV_PYTHON_INSTALL_DIR="$UV_PYTHON" uv python find --managed-python "$PYTHON_VERSION")"
PYTHON_HOME="$(cd "$("$INTERPRETER" -c 'import sys; print(sys.prefix)')" && pwd -P)"
cp -R "$PYTHON_HOME" "$BUNDLE/python"
test "$("$BUNDLE/python/bin/python3" -c 'import sys; print(sys.prefix)')" = "$BUNDLE/python"

(cd ../backend && uv export --frozen --no-dev --no-emit-project --no-hashes) > "$REQUIREMENTS"
uv pip install --python "$BUNDLE/python/bin/python3" --target "$BUNDLE/site-packages" -r "$REQUIREMENTS"

curl -fsSL -o "$BUILD/$DENO_ZIP" "$DENO_RELEASE/$DENO_ZIP"
curl -fsSL -o "$BUILD/$DENO_ZIP.sha256sum" "$DENO_RELEASE/$DENO_ZIP.sha256sum"
grep -q "^$DENO_SHA256 " "$BUILD/$DENO_ZIP.sha256sum"
(cd "$BUILD" && shasum -a 256 -c "$DENO_ZIP.sha256sum")
mkdir -p "$BUNDLE/bin"
unzip -q "$BUILD/$DENO_ZIP" deno -d "$BUNDLE/bin"

curl -fsSL -o "$BUILD/$NODE_TARBALL" "https://nodejs.org/dist/v$NODE_VERSION/$NODE_TARBALL"
echo "$NODE_SHA256  $BUILD/$NODE_TARBALL" | shasum -a 256 -c -
mkdir -p "$BUNDLE/node"
tar -xzf "$BUILD/$NODE_TARBALL" -C "$BUNDLE/node" --strip-components 1

curl -fsSL -o "$BUILD/$UV_TARBALL" "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/$UV_TARBALL"
echo "$UV_SHA256  $BUILD/$UV_TARBALL" | shasum -a 256 -c -
tar -xzf "$BUILD/$UV_TARBALL" -C "$BUNDLE/bin" --strip-components 1

write_launcher() {
    printf '#!/bin/sh\nexec "$(dirname "$0")/%s" "$@"\n' "$2" > "$BUNDLE/bin/$1"
    chmod 755 "$BUNDLE/bin/$1"
}
write_launcher python3 ../python/bin/python3
write_launcher node ../node/bin/node
write_launcher npx ../node/bin/npx

for server in $SERVERS; do
    (cd "../mcp-servers/$server" && uv export --frozen --no-dev --no-emit-project --no-hashes) > "$BUILD/$server.txt"
    uv pip install --python "$BUNDLE/python/bin/python3" --target "$BUNDLE/servers/$server" -r "$BUILD/$server.txt"
    uv pip install --python "$BUNDLE/python/bin/python3" --target "$BUNDLE/servers/$server" --no-deps "../mcp-servers/$server"
done

mkdir -p "$BUNDLE/app/backend" "$BUNDLE/app/desktop" "$BUNDLE/app/.agents/skills"
rsync -a --exclude __pycache__ ../backend/harness/ "$BUNDLE/app/backend/harness/"
cp config.json "$BUNDLE/app/desktop/config.json"
cp -R ../.agents/skills/create-skill "$BUNDLE/app/.agents/skills/create-skill"

if [ ! -f build/pages/server.js ]; then
    ./scripts/build-pages.sh
fi
cp -R build/pages "$BUNDLE/pages"

"$BUNDLE/python/bin/python3" -m compileall --invalidation-mode unchecked-hash -q \
    "$BUNDLE/python/lib" "$BUNDLE/site-packages" "$BUNDLE/app/backend" "$BUNDLE/servers"

rm -f build/icon.svg.png
qlmanage -t -s 1024 -o build ../frontend/app/icon.svg
test -f build/icon.svg.png

(cd "$BUNDLE/app/backend" && env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="$BUNDLE/app/backend:$BUNDLE/site-packages" "$BUNDLE/python/bin/python3" -c "import harness.web.server")
"$BUNDLE/bin/deno" --version
for server in $SERVERS; do
    env -i PATH="$BUNDLE/bin:/usr/bin:/bin" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$BUNDLE/servers/$server" \
        "$BUNDLE/bin/python3" -c "import $server.server"
done
env -i PATH="$BUNDLE/bin:/usr/bin:/bin" "$BUNDLE/bin/npx" --version
env -i PATH="$BUNDLE/bin:/usr/bin:/bin" "$BUNDLE/bin/uvx" --version
echo "bundle filled: $BUNDLE"
