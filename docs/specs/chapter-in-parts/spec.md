# A chapter translated in parts

## Problem

A comic chapter is read and translated by one worker, one page at a time, while the bot's other workers sit idle. A 32-page chapter spent about 65 to 70 minutes on reading alone (#138). The person wants the pages split across several workers that run at the same time, then joined into one translated chapter.

## What changes for you

1. You attach a chapter, for example `jewel-witch-46.cbz`, and write "Translate this chapter to English".
2. The bot starts one worker, **Prepare chapter**. You see it working in the chat.
3. Prepare chapter reports the page count and how to split it, for example "32 pages: pages 1–11, 12–22, 23–32".
4. The bot starts one worker per part, all at once: **Part 1**, **Part 2**, **Part 3**. You see three tickets working.
5. The parts finish one by one. The bot does nothing until every part has said done.
6. The bot starts **Combine chapter**. It checks that every page is translated, renders the chapter once, and packs the CBZ.
7. The bot hands you `jewel-witch-46-english.cbz` in the chat.
8. If a part fails, only that part is tried again. The pages the other parts finished are kept.
9. If Combine chapter starts too early, it finds untranslated pages, renders nothing, and says which pages are missing. Nothing half-translated reaches you.
10. A short chapter, under about 3 pages for each worker, is done by one worker, as today.

## Decisions

- **Separate workers the bot starts, not helpers inside one worker.** The person chose to see each part as its own ticket. Research found no source that joins separate workers. Anthropic's research system, DeepSeek's superagent prototype, LangGraph and manga-image-translator all join helpers inside one coordinator. The safety check below covers the gap.
- **The bot decides when every part is done, by reading its own chat.** The harness has no join across tickets (#102 left it out). No source does this.
- **Combine chapter refuses to render while any page is untranslated.** This is the check the person asked for. LangGraph and manga-image-translator also keep finished parts and redo only the missing ones.
- **The number of parts is the bot's own worker limit, 3 by default.** The prepare worker is told its bot's limit in its first message. Anthropic's lead agent also sizes its fan-out from a rule.
- **One names file that every part reads before each page and adds to, rather than a full list written first.** Approved at stop 2. The grill had agreed that Prepare chapter writes the list. Writing it needs the pages read, which is the slow work the split exists to share. TranslateImage and manga-translator-ui grow a shared glossary as pages are translated instead.
- **The skill changes go in its own repo, `Celliusx3/skills`, and are synced into the app's skills folder.** The person chose this.

## Out of scope

- A harness feature that groups tickets or waits for several of them. The bot and the safety check do this job.
- Splitting jobs other than comic chapters.
- A progress view for a group of parts. Each part shows as its own ticket.
- Changing how a failed ticket is retried. The existing retry is enough, because notes are saved per page.

## How we will know it works

- Attach a 32-page chapter on a private copy with NVIDIA Nemotron and 3 workers, and ask for an English translation. You see Prepare chapter, then three parts at once, then Combine chapter, then the CBZ in the chat.
- Compare the time from the first part starting to the last part finishing with today's single worker. It is about a third of today's 65 to 70 minutes.
- Open the CBZ. A character's name reads the same on pages 1, 12 and 23.
- Run Combine chapter while one part is still working. It renders nothing and names the pages still missing.
- Attach a 6-page chapter. One worker does it, as today.
- Every step above is recorded on video, before and after.
