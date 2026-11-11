# 07 The Mac app ships the phone

**Status.** open

**What to build.** `desktop/scripts/bundle.sh` adds `phone` to `SERVERS`, and
bundles the pinned kernel with it. The app's config declares the phone server.

**Checks.** Build the app. On a Mac user account with no Android tooling and
no Docker, open the app and ask a bot for a screenshot of the phone. The home
screen comes back.

**Blocked by.** 06
