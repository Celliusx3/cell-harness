# 04 The Mac app finds commands through your Terminal's PATH

**Status.** done

**What to build.** At start, the Mac app runs your login shell once
(`$SHELL -l -i -c`, with markers so profile output is skipped, and a time
limit) to read its PATH, and gives the harness that PATH after the app's own
`bin`. If the shell fails or is slow, the app keeps the PATH it has and logs
why. Unit tests in the desktop suite.

**Checks.** Desktop tests cover the parse, the markers, a failing shell and
the time limit. Opened from Finder, the packaged app starts a server whose
command is Homebrew's `npx`.

**Blocked by.** none
