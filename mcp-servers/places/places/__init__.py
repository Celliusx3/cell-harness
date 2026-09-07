"""places — resolve a described place to a real POI.

Owned rather than borrowed, for four reasons, each measured:

1. **The maintained third-party server declares no `outputSchema`**, so it cannot
   emit `structuredContent` and a code-mode script reading its result gets
   `undefined`. `docs/mcp-tool-scaling.md` §6 finding 4 records what that costs:
   *"five failing scripts and a cancelled turn."*
2. **Its field masks are hardcoded** to Enterprise and Atmosphere tier fields, so
   it bills at 1,000 free calls/month where a Pro-only mask gets 5,000.
3. **Those masks pull reviews and ratings back on every search**, and a tool
   result is retained forever in the session log — against Google's
   resolve-on-read storage guidance.
4. It is a pre-1.0, single-maintainer dependency in the path of a capability we
   care about, and it cannot be shaped: no mask control, no candidate count.

The capability itself is *one documented HTTP endpoint*, which is what makes
owning it cheaper than depending on it.
"""
