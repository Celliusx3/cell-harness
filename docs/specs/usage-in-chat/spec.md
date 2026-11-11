# Token usage and cache hit rate in the chat

Issue #62.

## Problem

The chat shows nothing about what a conversation cost in tokens. You cannot see when a chat is expensive, or when the prompt cache is not working. The only place to see the hit rate today is the provider's own dashboard, which is how #56 was found.

## What changes for you

1. You chat with a bot, as today.
2. Beside the attach button in the message box, a gauge icon appears once the chat has a reply.
3. You move the pointer over the icon. A small card opens above it with the whole chat's figures. It gives input, cached and output tokens, and the cache hit rate.
4. You click the icon instead. The card stays open until you click elsewhere. On a phone you tap it.
5. Some providers do not report cached tokens. Then the card's Cached and Cache hit rate rows read "not reported".
6. You reload the page. Every figure is the same as before.
7. You clear the chat. The icon goes away until the next reply.

## Decisions

- The figures sit behind an icon beside the attach button, not in the header or under each reply. ZCode puts them beside its upload button. The grill first chose a line under each reply and totals in the header. After trying it, the person moved them to the icon (ticket 03).
- The card shows the whole chat only. DeepSeek Harness shows a turn's figures per reply as well; the person chose the chat alone.
- Counts are exact, such as 61,695. DeepSeek Harness's usage dialog shows exact counts.
- In the chat's totals, a step with no cache figure counts as 0 cached. A step with no usage adds nothing. So the chat's hit rate can only read low, never high. DeepSeek Harness and opencode both total the chat this way. A figure no step reported reads "not reported".
- The hit rate is cached input ÷ all input. OpenAI-style `prompt_tokens` already counts the cached tokens. So this equals DeepSeek Harness's and Claude Code's cache read ÷ all prompt tokens.
- Helper (`run_subagent`) tokens are not counted. DeepSeek Harness gives each subagent its own figures on its own row. Claude Code's cache line covers the main conversation only. We have no row for a helper until #55.
- The totals count what is after the last clear, as the timeline does.
- Every figure is added up in the browser from the session's logged events. The browser already receives them from the start of the log. No new route and no backend change: #63 already logs the cached tokens.
- The frontend has no unit test runner. The adding-up stays in one pure file. It is proved by driving the chat in a browser on a fake model.

## Assumptions

- Only the browser shows the figures. Telegram and Discord show nothing.
- Tokens only, no money cost: the app stores no prices.

## Out of scope

- Figures for each reply or each step.
- Figures for each helper, which come with #55.
- A step that failed before the model finished has no logged usage. It is not counted, though the provider may have billed it.
- Context window use, which compaction already tracks.

## How we will know it works

- Run turns on a model that reports cached tokens. Hover the icon: the card's figures are the sums of the logged usage, and the hit rate is cached ÷ input.
- Add a turn on a model that reports usage without cached tokens. The hit rate falls and still shows.
- Add a turn where one step reported no usage. Only the other steps are added.
- Move the pointer away: the card closes. Click the icon: it stays open.
- Reload: every figure is unchanged.
- Clear the chat, or open a chat with no reply: there is no icon.
- A turn that used `run_subagent` counts only the bot's own steps.
- On a touch screen, tap the icon: the card opens.
