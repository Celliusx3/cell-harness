# A phone for the bots

Tracked in [#65](https://github.com/Celliusx3/cell-harness/issues/65).

## Problem

A bot can use websites but not native Android apps, because its only computer
is the Ubuntu PC. Cell Harness is sold as a Mac app. So a phone has to ship
inside it, and run on the customer's Mac with nothing extra to install. Android
cannot boot in the PC's microVM today: its kernel has no binder, the driver
every Android service talks through.

## What changes for you

1. You ask a bot to do something in an Android app. The phone was off, so it
   starts. The bot's first phone step waits for Android to finish booting.
2. You give the bot an APK in the chat. It installs it, and the app shows up on
   the phone.
3. The bot opens the app, takes a screenshot, taps a button and types into a
   field. Each step answers with what the phone now shows.
4. You open the Computer page and see the phone's screen beside the PC's. You
   take control and tap through an app yourself. The bots wait until you hand
   it back.
5. Nobody uses the phone for ten minutes. It stops, and its memory comes back
   to the Mac. Installed apps and their data are still there next time.
6. Nothing in the chat ever uses the phone. It never starts, and costs nothing.

## Decisions

1. **Prove it first.** Tickets 01 and 02 boot Android in a microVM, install an
   APK, screenshot, tap and type, and measure memory. Nothing after them is
   built until you have seen that evidence and said go.
2. **Redroid on arm64, in a microsandbox microVM, on Apple Silicon only.**
   Redroid is Android built to run in a container (Apache-2.0, ~7k stars).
   kindling boots it in a microVM on Apple Silicon. xenoid runs it in a Linux
   VM on the Mac. microsandbox is what the PC already runs on.
3. **A kernel of our own, with binder built in.** microsandbox's kernel has
   binder off and module loading off, so binder cannot be added at boot.
   microsandbox documents rebuilding its libkrunfw fork at the pinned revision
   and pointing `MSB_LIBKRUNFW_PATH` at it. kindling adds binder and binderfs
   the same way, as a config fragment.
4. **The phone is its own MCP server, built the way the computer server is.**
   It has the same engine interface, services, tools and models, and the same
   lifecycle. microsandbox loads one kernel per process. A phone in the PC's
   server would put the PC on the Android kernel too. A separate server also
   follows the repo's rule that a capability is an MCP server.
5. **The phone runs an image we publish, pinned by digest, like the PC.**
   GitHub builds it from Redroid's arm64 image. The config names the exact
   version, so an upstream change never reaches a customer unseen.
6. **One phone, shared by every bot, off until needed, stopped when idle.** The
   same lifecycle as the PC. Agreed in the grill.
7. **The bot drives the phone with Android's own commands, run inside the
   microVM:** `screencap`, `input tap`, `input text`, `pm install`. The PC's
   tools work the same way, through the engine's run. So no adb ships on the
   Mac. mobile-mcp (Apache-2.0, ~10k stars) wraps the same commands over adb.
   It was declined, because adb cannot ship under Google's SDK licence.

   Ticket 01 showed the commands reach Android's services from microsandbox's
   exec, so no adb is needed.
8. **No Google Play. Apps come from APK files.** Google's SDK licence forbids
   redistributing any part of the SDK, including its Play images. Genymotion,
   Anbox Cloud and Waydroid all ship without Play. Their customers add it
   under their own licence, or at their own risk.

   The grill asked for Play to be researched first, and the research says it
   cannot ship. A way for customers to add Play is out of scope. To decide at
   approval.
9. **The kernel ships with its source.** libkrunfw is GPL-2.0. A binary copy has
   to come with the kernel source it was built from, so GitHub publishes both
   together. The app pins the kernel by digest, as it pins the PC image.
10. **You can watch the phone and take control, like the PC.** Taking control
    holds the bots off for fifteen minutes, as the PC's hold does. scrcpy
    (Apache-2.0, ~155k stars) streams the screen and takes input. Its server
    half runs on the phone, so nothing extra runs on the Mac. A browser client
    such as ya-webadb's (MIT, ~3k stars) plays it on the Computer page.
    To decide at approval.

## Out of scope

- Google Play Store and Play services, including letting the customer add them.
- A phone per bot. Revisited only with ticket 02's memory figures.
- Intel Macs, Windows and Linux hosts.
- Reading an app's screen as text (the accessibility tree). Screenshots only.

## How we will know it works

1. Run the experiment script on an Apple Silicon Mac. Android reaches
   `sys.boot_completed`, and a screenshot of the home screen is saved.
2. Install a sample APK and open it. A screenshot shows the app. Tap a button
   and type into a field, and the next screenshot shows the change.
3. Read the memory figures, idle and with the app open, in docs/rakazo.md §5
   beside the PC's 0.6 GB.
4. In the chat, ask a bot to install an APK you attach and open it. The reply
   carries a screenshot of the app.
5. Leave the phone unused for ten minutes. Its microVM is stopped, and the
   apps are still installed when a bot next uses it.
6. Start the app on a Mac with no Android tooling installed. The phone works.
7. Open the GitHub release for the kernel. The kernel source is attached to it.
