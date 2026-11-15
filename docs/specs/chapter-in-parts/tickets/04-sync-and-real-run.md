# 04 Sync the skill and prove it on a real chapter

**Status.** open

**What to build.** In `Celliusx3/skills`, a short `scripts/sync-to-cell-harness.sh` copies `comic-translator/` into `~/Library/Application Support/Cell Harness/skills/comic-translator/`. It leaves out `.venv`, caches and coverage files, and prints what changed. Run it once, then record the real runs the spec's checks describe.

**Checks.**

- After the sync, the two folders differ only in caches.
- A private copy runs NVIDIA Nemotron with 3 workers on a 32-page chapter. It goes through prepare, three parts at once, and combine. The CBZ reaches the chat.
- The reading time is about a third of today's, and names match across parts.
- An early combine names the missing pages. A 6-page chapter uses one worker.
- Each run is on video, before and after, for the PRs in both repos.

**Blocked by.** 03
