# A worker asks the person to take control

## Problem

When a page needs a person, such as a human check, a login or a captcha, a worker cannot hand the screen over. The orchestrator change (#104) took `hand_over` away from every bot, and a worker's report has no way to ask for the screen. In one run a worker spent 33 steps trying to get round a check on its own (#119).

## What changes for you

1. You ask a bot for something on a website, and the bot starts a worker.
2. The worker opens the page, and the page shows a human check.
3. The worker reports that it is blocked and asks you to take control. Its turn ends.
4. The ticket moves to **Needs you**. In the chat, its question shows **Take control**, **I'm done** and **Skip**.
5. You press **Take control**, and the Computer page opens with the screen yours.
6. You pass the check, then press **I'm done**. The screen goes back to the bots.
7. The worker resumes, reads the page and carries on.
8. If you press **Skip**, the worker carries on without that step.
9. On Telegram or Discord, the chat gets the question and a note to open the computer in the app.

## Decisions

- A worker asks through its report, as it asks for a key or a location today. The main bot stays a router, as #104 made it. To decide at approval.
- The report calls the new way to answer `takeover`, beside `text`, `choice`, `secret` and `location`. To decide at approval.
- The answer reaches the worker as text, as a shared location does: "done" or "skipped". To decide at approval.
- The worker's own prompt says when to ask this way. The computer server keeps its general "ask the person", because it does not know the app's report tool. To decide at approval.
- `hand_over` stays registered for old chats, as #104 left it.

## Out of scope

- Giving the main bot back any asking tool.
- A reminder or an expiry for a question nobody answers.
- A bot solving a captcha or a check by itself.

## How we will know it works

- A worker reports blocked with the takeover ask. Its ticket shows in **Needs you**, and the chat shows the three buttons.
- You press **I'm done**. The worker's next turn starts with your answer.
- You press **Skip**. The worker's next turn starts with "skipped".
- On Telegram, the line asks you to open the computer in the app.
- The backend suite stays green, with a test for each check above.
