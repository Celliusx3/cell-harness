# 04 The PC runs from inside the app

**Status.** open

**What to build.** The bundle installs the `computer` server like the others.
The app's signing keeps `msb`'s hypervisor and library-validation
permissions, through entitlements files for the app and what it contains.
The computer server's env in `desktop/config.json` points microsandbox's
folder (`MSB_HOME`) into the app's data folder and gives the PC its own
name. The server stays `required`, so a Mac that cannot run a VM gets the
existing message.

**Checks.** `codesign -d --entitlements -` on the packaged `msb` shows
`com.apple.security.hypervisor`. Open the packaged app's Computer page: the
desktop shows, and a bot opens a site in the PC. The app's microsandbox
folder is in its data folder, and `make dev`'s PC is unchanged.

**Blocked by.** 01
