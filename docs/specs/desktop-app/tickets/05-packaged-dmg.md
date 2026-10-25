# 05 Packaged dmg

**Status:** open

**What to build.**

- `desktop/scripts/bundle.sh` fills `desktop/build/` with a uv-managed Python 3.13 and the harness's locked packages for it.
- It adds a pinned Deno release, `backend/harness`, `desktop/config.json`, only the `create-skill` skill, and the built pages.
- `paths.ts` gains the packaged layout under the app's Resources folder, with Deno on the children's PATH.
- The `build` section of `desktop/package.json` makes an arm64 dmg with identity `-` and hardened runtime off.
- The app gets an icon and a location usage string.
- The root `Makefile` gains `app:`.

**Checks.**

- `make app` writes `desktop/dist/Cell Harness-0.1.0-arm64.dmg`.
- `codesign --verify --deep --strict` passes on the app and shows an ad-hoc signature.
- Run the app binary with `HOME` set to a temp folder and `PATH=/usr/bin:/bin`. The setup window appears.
- A key saves, and "hi" gets a reply. Only create-skill is listed on the Skills page.

**Blocked by.** 03, 04
