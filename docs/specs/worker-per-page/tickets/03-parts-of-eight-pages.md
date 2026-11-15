# 03 Prepare reports one ticket per 8 pages with text

**Status.** done

**What to build.** In `Celliusx3/skills`, `comic-translator/SKILL.md`, "Long chapters". Prepare splits `detect`'s `text_pages` in order into parts of 8 pages, whatever the bot's worker limit, and reports one Part line for each, then one Combine line. A Part's task names its pages one by one. Combine is started after every Part reports ready. 

The rest of the Part role is unchanged: read `names.json` before the page, render only that page, fix it until clean. Then copy the skill into the app's skills folder, as in the chapter-in-parts feature.

**Checks.** On a private copy with GLM 5.3 Flash, 3 workers, in Ask mode, translate the 142-page `ch84.zip`. Prepare reports 17 Part lines. At most 3 tickets work at once and the rest show queued. 

One approval card asks for the shell, and none after "Allow for this conversation". The zip in the chat holds 142 pages. Record input tokens, minutes and tokens per page against the last run (19.8M, about 20 minutes). 

Stop one ticket: Combine names its pages as missing. Every step is recorded on video.

**Blocked by.** 01, 02
