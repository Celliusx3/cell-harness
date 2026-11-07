# 01 The PC image boots in microsandbox, built by GitHub

**Status.** open

**What to build.** `mcp-servers/computer/image/Dockerfile` on a
`debian:bookworm-slim` pinned by digest. It installs Xvfb, fluxbox, Chromium,
x11vnc, websockify, noVNC, xdotool, python3, bash, procps, flock and xdpyinfo,
and adds a user `pc` (uid 1000) with home `/home/pc`. `image/start` is the
image's command: Xvfb on `:1` at 1280x800, then fluxbox, and it exits when Xvfb
dies. `.github/workflows/pc-image.yml` builds amd64 on `ubuntu-latest` and
arm64 on `ubuntu-24.04-arm`, pushes each by digest, joins them into one image
at `ghcr.io/celliusx3/cell-harness/pc`, and prints the joined digest.

**Checks.** Push the branch. The workflow passes, and `docker buildx
imagetools inspect` on the image lists `linux/amd64` and `linux/arm64`. On this
Mac, `msb run` the image by digest and run its command. `xdpyinfo -display :1`
inside it answers, and `chromium --version` prints a version. One manual step:
set the package to public in GitHub's package settings.

**Blocked by.** none
