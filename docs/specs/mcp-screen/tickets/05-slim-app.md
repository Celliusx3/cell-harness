# 05 The Mac app is slimmer

**Status.** open

**What to build.** The bundle drops test folders inside Python libraries,
Python's Tk, IDLE and ensurepip, and precompiled files for the computer
server. Electron keeps only English. The dmg uses LZFSE compression.

**Checks.** `make app` writes a dmg, and its size is reported against
436 MB. The packaged app still starts, and its PC boots.

**Blocked by.** 03
