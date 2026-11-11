# 08 You watch the phone on the Computer page and take control

**Status.** done

**What to build.** The phone image starts scrcpy's server half on the phone.
`mcp-servers/phone/services/live_screen.py` publishes its stream on loopback
behind a view token, and holds the bots off while you have control, as the
computer server's live screen does. A phone panel beside the PC's screen in
`frontend/components/computer/` plays it with a browser scrcpy client, and has
the same take-control button.

**Checks.** A unit test: while you hold control, a bot's `tap` returns
`error: …` saying a person has the phone. By hand, take control and tap
through an app; the panel follows. Hand it back, and a bot's next tap works.

**Blocked by.** 07
