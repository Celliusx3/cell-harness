# A bot asks the person to take control

## Problem

When a page needs a person, such as a human check, a login or a captcha, a bot cannot hand the screen over. It can only write in the chat, and the person must know to open the Computer page. A bot that is not told to stop tries to get round the check on its own (#119).

## What changes for you

1. You ask a bot for something on a website.
2. The bot opens the page, and the page shows a human check.
3. The bot asks you to take control, and its turn ends.
4. A card appears in the chat: the bot's name, its reason, and a **Take control** button.
5. You press **Take control**. The computer docks beside the chat, and you hold its screen.
6. You pass the check, then press **Hand back**.
7. The bot starts its next turn, reads the page and carries on.
8. If you type a message instead, the bot skips the request and reads your message.
9. If you never answer, the card stays in the chat. Nothing runs, and the bot does not remind you.
10. If a worker asks, its ticket moves to **Needs you** with the same **Take control** button.
11. On Telegram or Discord, the chat gets the reason and a link to the page that answers it.

## Decisions

- The request waits the way `get_location` waits. The turn ends at the ask, with no timer and no expiry, and handing back starts the next turn. Rakazo pauses its run the same way. To decide at approval.
- A tool from any MCP server can declare that it waits for the person. Today only the app's own tools can wait, and the rule names no tool. To decide at approval.
- The computer server holds the tool, named `request_takeover` as in Rakazo, with one field, the reason. To decide at approval.
- No code spots a check, as in Rakazo. The tool's description lists when to call it: passwords, 2FA, captchas, human checks, payments and passkeys. To decide at approval.
- A failed browser step tells the bot to call `request_takeover`, as Rakazo's browser tools do. To decide at approval.
- The wording from #128, "ask the person to do that step on the Computer page", becomes "call request_takeover". To decide at approval.

## Out of scope

- A bot solving a captcha or a check by itself.
- Opening a page another way to pass a check.
- Asking for a takeover on the phone. The phone can follow later with the same tool.
- A reminder or an expiry for a request nobody answers.

## How we will know it works

- A bot calls `request_takeover`. Its turn ends, and the chat shows the card with the reason and **Take control**.
- You press **Take control**, then **Hand back**. The bot's next turn reads the page.
- You type a message instead. The bot reads it, and the request shows as skipped.
- A worker calls it. Its ticket shows in **Needs you** with **Take control**.
- On Telegram, the chat gets the reason and a link that answers the request.
- The backend and computer server suites stay green, with a test for each check above.
