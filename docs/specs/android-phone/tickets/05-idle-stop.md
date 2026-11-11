# 05 The phone stops when idle and keeps its apps

**Status.** done

**What to build.** The phone's idle stop in `mcp-servers/phone/`, ten minutes
by default, set by `PHONE_IDLE_MINUTES`. Android's data lives on a named volume,
so a stop keeps installed apps.

**Checks.** A unit test with a fake clock: no tool call for the idle time stops
the microVM, and a call in between does not. By hand, with the idle time at
one minute, wait, then ask for a screenshot. The app from ticket 04 is still
installed.

**Blocked by.** 04
