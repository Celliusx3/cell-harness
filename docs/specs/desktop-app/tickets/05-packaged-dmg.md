# 05 Packaged dmg

**Status:** done

**What to build.**

- `desktop/scripts/bundle.sh` fills `desktop/build/bundle/` with Python 3.13.6 and the harness's locked packages for it.
- uv installs that Python into the build folder, never into the person's own uv folder.
- It adds Deno 2.8.3 from its GitHub release, checked against the release's SHA-256.
- It adds `backend/harness`, `desktop/config.json`, only the `create-skill` skill, and the built pages.
- The app icon is rendered from `frontend/app/icon.svg` with macOS's Quick Look, so no image file is committed.
- `paths.ts` gains the packaged layout under the app's Resources folder, with Deno on the children's PATH.
- The `build` section of `desktop/package.json` makes an arm64 dmg with identity `-` and hardened runtime off.
- The app ships `src/setup.html`, which the setup window loads.
- The app gets an icon.
- The root `Makefile` gains `app:`.

**Checks.**

- `make app` writes `desktop/dist-app/Cell Harness-0.1.0-arm64.dmg`.
- `codesign --verify --deep --strict` passes on the app and shows an ad-hoc signature.
- Run the app binary with `HOME` set to a temp folder and `PATH=/usr/bin:/bin`. The setup window appears.
- A key saves, and "hi" gets a reply. Only create-skill is listed on the Skills page.

**Blocked by.** 03, 04
