# A worker per page, tried and measured

## Problem

A long chapter is split into one part per worker, so each part carries many pages (Celliusx3/skills#3). A slow part holds up the whole chapter while the other workers sit idle, and each part sends its whole history again on every step. A 142-page Korean webtoon chapter on GLM 5.3 Flash with 3 workers used 19.8M input tokens and about 20 minutes. In Ask mode it also showed 7 approval cards for one shell tool, because "Allow for this conversation" does not reach the chat's workers.

## What changes for you

1. You ask the bot to translate `ch84.zip`, a 142-page chapter, in Ask mode.
2. The bot starts **Prepare**. Prepare finds the text on every page. 132 pages have text, and Prepare reports them in parts of 8.
3. The bot starts one ticket for every 8 pages with text, 17 here. Three work at once, and the rest show as queued. When a ticket finishes, the next queued one starts.
4. The first ticket asks to run the shell. You choose "Allow for this conversation".
5. No other ticket asks for the shell again, in this chapter or the next one in this chat.
6. A slow or stuck ticket holds up only its 8 pages. The other workers keep taking tickets.
7. When every page reports ready, the bot starts **Combine**. It packs all 142 pages. The 10 pages with no text go in as they are, without a ticket.
8. The bot hands you `ch84-english.zip` in the chat.

## Decisions

- **One part per worker, as before.** The grill chose one page per ticket, and the person later chose parts of 8. Both were built and run on the same chapter, and both were slower than one part per worker on GLM 5.3 Flash with 3 workers. Each ticket pays its own start, and the model's time per step sets the clock. The person then chose to go back to one part per worker. Codex's `spawn_agents_on_csv` and the harness queue (#102) would carry many small tickets when a model is faster.
- **Combine packs a page with no text unchanged.** The person chose this. `detect` now tells which pages have text.
- **"Allow for this conversation" covers the chat and every worker it starts, including a grant given on a worker's card.** The person chose that a chat's grant reaches its workers. Claude Code does the same: a session grant made on a sub-agent's prompt "applies your answer to the whole session, including your main conversation". Codex keeps a separate list for each sub-agent, which is what we do today. Approved: a grant on a worker's card is recorded in the chat, so it covers the other workers too.
- **Names stay in the shared names file, read before each page.** TranslateImage does the same and accepts that two pages writing at once can lose a term (one source). This feature does not fix that the file stayed empty in the last run.
- **The skill changes go in `Celliusx3/skills`, the grant change in cell-harness.** As in the chapter-in-parts feature.

## Out of scope

- A grouped view of a chapter's tickets in the chat. Each part shows as its own ticket.
- Boxing a whole bubble instead of each line.
- A bubble cut by the strip boundary (Celliusx3/skills#9).
- Making workers add names to the names file.
- "Always allow", which already reaches every worker.

## How we will know it works

- Translate the 142-page `ch84.zip` on a private copy with GLM 5.3 Flash, 3 workers, in Ask mode. You see Prepare, then one ticket per 8 pages with text, at most 3 working at once, then Combine, then the zip in the chat.
- Count the approval cards. There is one for the shell, and none after "Allow for this conversation".
- Open the zip. It holds 142 pages, and a page with no text is the original page.
- Compare against the last run: 19.8M input tokens and about 20 minutes. The chapter takes less time and fewer input tokens than the 3-part run.
- Stop one ticket on purpose. The other tickets still finish, and Combine names its pages as missing.
- Allow the shell on a worker's card. A ticket started after that runs the shell without asking.
- Every step above is recorded on video.

## What the runs measured

The 142-page `ch84.zip` on GLM 5.3 Flash, 3 workers, Ask mode:

| Split | Minutes | Input tokens | Approval cards |
|---|---|---|---|
| 3 parts, before this feature | 20 | 19.8M | 7 |
| One page per ticket, stopped at 10 pages | about 100, projected | 2.3M for 10 pages | 1 |
| Parts of 8, before the render limit | 45.5 | 31.5M | 1 |
| Parts of 8, with the render limit | 30.4 | 12.8M | 1 |
| Parts of 8, all of a part's images in one step | about 33 | 10.0M | 1 |
| One part per worker, with every fix | 25.3 | 20.4M | 1 |

In the last run, one part translated only pages 95 to 99 of 95 to 142, and the bot sent 100 to 142 out again. Without that, the run would have taken about 19 minutes.
