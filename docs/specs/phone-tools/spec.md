# More phone tools, like mobile-mcp's

Tracked in [#65](https://github.com/Celliusx3/cell-harness/issues/65).

## Problem

Asked to share a Pinduoduo listing and copy its link, a bot tapped Share and
Copy Link, then could not get the link out. It had no long-press for Android's
Paste menu, no paste key, and no way to read the screen as text. It reads
every price and title from screenshots, which costs a screenshot per step.
mobile-mcp (Apache-2.0, ~10k stars) offers 34 tools; ours offers 7.

## What changes for you

1. A bot long-presses or double-taps where a tap is not enough.
2. A bot opens a link you give it straight into the app that handles it.
3. A bot presses paste, tab, search and the volume keys.
4. A bot lists the phone's apps, sees which one is open, closes a stuck app,
   removes one, or clears an app's data.
5. A bot lists what is on screen as text: each element's words, description
   and centre, so it reads prices and links and taps exact targets.

## Decisions

1. **The same tools mobile-mcp offers for one phone, through Android's own
   commands.** Long-press is a swipe that stays put, double-tap two taps
   100 ms apart, open-URL a VIEW intent, the elements Android's
   `uiautomator dump`. mobile-mcp does each the same way.
2. **Commands run with Android's own environment.** The `android` helper takes
   it from zygote, so Java tools such as `uiautomator` start; before, they
   exited silently.
3. **Elements are a short list, not the XML.** Each has its text, its
   description, whether it is clickable, and the centre to tap, in screenshot
   pixels. mobile-mcp formats its list the same way.
4. **No device lists, cloud devices, orientation, location, recording or
   crash logs.** One phone, ours; those serve developers, not a bot's task.

## Out of scope

- Reading and setting the clipboard, and typing beyond ASCII. Android 13 has
  no shell command for the clipboard; mobile-mcp uses a helper app. A
  follow-up builds our own.
- Several actions in one call.

## How we will know it works

1. Ask a bot to share a Pinduoduo listing and paste the link into a note. It
   long-presses, pastes, and the note shows the link.
2. Ask a bot to open a Pinduoduo link. It opens in the browser, since
   Pinduoduo does not claim its links, on a page offering to open the app.
3. Ask a bot to list the phone's apps and close Pinduoduo. It names them, and
   Pinduoduo is gone from recent apps.
4. Ask a bot for the prices on a results page without a screenshot. It reads
   them from the element list.
