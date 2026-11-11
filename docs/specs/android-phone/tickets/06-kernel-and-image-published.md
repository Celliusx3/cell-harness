# 06 GitHub builds the phone's kernel and image, and publishes the kernel's source

**Status.** done

**What to build.** `.github/workflows/phone.yml` runs
`mcp-servers/phone/kernel/build` on a macOS arm64 runner, and publishes the
dylib with the kernel source it was built from to one GitHub release. It also
builds `mcp-servers/phone/image/Dockerfile` from Redroid's arm64 image, and
pushes it to `ghcr.io/celliusx3/cell-harness/phone`, like the PC's workflow.
The phone server's config pins both by digest, and refuses a dylib that does
not match.

**Checks.** Push the branch. The release has the dylib and the source archive,
and the image lists `linux/arm64`. The server starts with both digests in its
config, and refuses a dylib with one byte changed.

**Blocked by.** 05
