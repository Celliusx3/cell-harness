# 03 Prepare reports one part per worker, and parts stop chasing a page

**Status.** done

**What to build.** In `Celliusx3/skills`, `comic-translator/SKILL.md`, "Long chapters". Prepare splits the pages into one part per worker, as before, and its summary names `ticket_route`. Parts look only at the images detect and render made, leave a bubble cut by the page edge after one render, and report `ready` for a page refused after 3 renders. Parts of 8 and one page per ticket were built, run and dropped, as the spec records. Combine is started after every Part reports ready. 

The rest of the Part role is unchanged: read `names.json` before the page, render only that page, fix it until clean. Then copy the skill into the app's skills folder, as in the chapter-in-parts feature.

**Checks.** On a private copy with GLM 5.3 Flash, 3 workers, in Ask mode, translate the 142-page `ch84.zip`. Prepare reports 3 Part lines. At most 3 tickets work at once and the rest show queued. 

One approval card asks for the shell, and none after "Allow for this conversation". The zip in the chat holds 142 pages. Record input tokens, minutes and tokens per page against the last run (19.8M, about 20 minutes). 

 Every step is recorded on video.

**Blocked by.** 01, 02
