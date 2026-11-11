# Token usage and cache hit rate in the chat

Issue #62.

## Problem

The chat shows nothing about what a reply or a conversation cost in tokens. You cannot see when a turn is expensive, or when the prompt cache is not working. The only place to see the hit rate today is the provider's own dashboard, which is how #56 was found.

## What changes for you

1. You send a message. The bot works through its steps and answers, as today.
2. The turn ends. You move the pointer over the bot's answer. One muted line appears under it, for the whole turn. It gives input tokens, output tokens, cached tokens and the cache hit rate. For example "48.2k in · 1.9k out · 39.1k cached (81%)".
3. On a phone you tap the answer, and the same line appears.
4. The chat's header shows the whole chat's totals under the bot's name. They are input, output, cached and the overall hit rate.
5. Some providers do not report cached tokens. A turn on one shows "cache not reported" in place of the cached figures. A turn where some step reported no usage at all shows "usage not reported".
6. You reload the page. Every figure is the same as before.
7. You clear the chat. The header's totals start again from zero, with the chat.

## Decisions

- A reply's figures are the sum of its turn's steps, shown once the turn has ended. DeepSeek Harness shows one usage pill per completed turn, opened on click.
- A reply's figures are shown on hover, and on tap on touch screens. DeepSeek Harness opens its turn figures on click; the grill chose hover.
- A reply's cached tokens and hit rate show only when every step in the turn reported them. DeepSeek Harness's turn figures and Codex's `/status` both hide a cache figure that one call left out. Neither shows a partial sum.
- A reply where any step reported no usage shows no figures, only "usage not reported". DeepSeek Harness withholds the whole turn's figures when one attempt's usage is missing.
- In the chat's totals, a step with no cache figure counts as 0 cached. A step with no usage adds nothing. So the chat's hit rate can only read low, never high. DeepSeek Harness and opencode both total the chat this way. When no step in the chat reported a figure, it reads "not reported".
- The hit rate is cached input ÷ all input. OpenAI-style `prompt_tokens` already counts the cached tokens. So this equals DeepSeek Harness's and Claude Code's cache read ÷ all prompt tokens.
- Helper (`run_subagent`) tokens are not counted in a reply or in the chat. DeepSeek Harness gives each subagent its own figures on its own row. Claude Code's cache line covers the main conversation only. We have no row for a helper until #55.
- The chat's totals count what is after the last clear, as the timeline does.
- Every figure is added up in the browser from the session's logged events. The browser already receives them from the start of the log. No new route and no backend change: #63 already logs the cached tokens. **To decide at approval:** the frontend has no unit test runner today. The plan keeps the adding-up in one pure file. It is proved by driving the chat in a browser on a fake model, with no test runner added. Adding Vitest for that one file is the alternative.

## Assumptions

- Only the browser shows the figures. Telegram and Discord show nothing.
- Tokens only, no money cost: the app stores no prices.
- Large counts are shortened: 48.2k, 1.2M.

## Out of scope

- Figures for each helper, which come with #55.
- A step that failed before the model finished has no logged usage. It is not counted, though the provider may have billed it.
- Figures for each step inside a turn.
- Context window use, which compaction already tracks.

## How we will know it works

- Run a turn on a model that reports cached tokens. Hover the answer: the line shows input, output, cached and a hit rate that is cached ÷ input.
- Run a turn on a model that reports usage without cached tokens. The answer's line reads "cache not reported", and the header's hit rate does not rise.
- Run a turn where one step reported no usage. The answer's line reads "usage not reported".
- The header's totals equal the sum of every answer's figures.
- Reload: every figure is unchanged.
- Clear the chat: the header shows no totals.
- A turn that used `run_subagent` counts only the bot's own steps.
- At phone width, tap an answer: the line appears.
