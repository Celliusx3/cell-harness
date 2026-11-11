# 04 A bot installs an APK from the chat, opens it, taps and types

**Status.** done

**What to build.** Tools `install_app` (an APK from the chat's files),
`open_app`, `tap`, `swipe`, `type_text` and `press_key` in `mcp-servers/phone/`. Each
ends with a screenshot. A failure is an `error: …` result, never a raise. A
skill under `.agents/skills/` tells the bot how to use them.

**Checks.** Unit tests for each tool's command and its failure text. By hand,
attach the sample APK and ask a bot to install it, open it and type a word.
The last screenshot shows the word.

**Blocked by.** 03
