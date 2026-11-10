# Chat modes: choose how much a bot may do without asking

Issue #54. Plan mode is #60 and is not part of this spec.

## Problem

A person cannot choose, per chat, how far a bot goes without them. Every chat follows one fixed rule from the config file: some tools ask, and the rest run. To loosen control for a trusted task, or tighten it for a risky one, the person must edit the config and restart. They also cannot see which rule a chat follows.

## What changes for you

1. You open a chat. The message box shows "Ask", the mode every new chat starts in.
2. The bot calls a tool that changes something. An approval card appears, as today.
3. You pick "Auto" in the message box. A dialog asks "Let this bot act without asking in this chat?" You confirm.
4. The timeline shows a line, "Mode: Auto".
5. The bot calls a tool that changes something. It runs, and no card appears.
6. You pick "Ask" again. No dialog appears, and the timeline shows "Mode: Ask".
7. In Telegram or Discord you type `/mode auto`. The chat answers that it is now in Auto. `/mode` alone answers with the current mode.
8. You switch modes while the bot is working. Its next tool call follows the new mode, and the bot is told that you changed it.
9. An approval card is waiting when you switch to Auto. The card stays until you answer it.

## Decisions

- There are two modes. Ask is today's rule, and Auto shows no approval card. A question to the person, such as a request for a location, still waits in both. Claude Code, ZCode and OpenMaus each have an ask mode and a mode that runs everything.
- Auto runs every call. DeepSeek Harness's `never` refuses a call that would ask, and its calls run freely only because its file sandbox is open. This project has no such sandbox, so Auto runs the call.
- The mode is saved in the chat's history, and the latest switch wins. A chat with no switch uses the default from the config file. DeepSeek Harness and ZCode do this.
- The default for new chats is Ask, set by one config setting. DeepSeek Harness and Claude Code both read a default from config.
- One mode per chat. Every bot in a group chat follows it. DeepSeek Harness keeps the mode per session, and a group chat is one session here.
- A picker in the message box and a `/mode` command. DeepSeek Harness has `/permission`, ZCode has `/mode`, and Claude Code, ZCode and OpenMaus have a picker.
- Picking Auto in the browser asks to confirm first. DeepSeek Harness asks "Enable Full access?" Typing `/mode auto` is already a clear choice, so it does not ask.
- A switch takes effect from the next tool call, and the bot is told at its next step, with a note saved in the history. DeepSeek Harness does this.
- Every step, the bot is told the current mode in one line after the history. So a switch does not change the start of the request. DeepSeek Harness places it there for the same reason.
- Scripts the bot writes follow the chat's mode, as its own calls do.
- A subagent takes the chat's mode when it starts. DeepSeek Harness also fixes the mode when a subagent starts. The grill said "at each call", and this is a little narrower. To decide at approval.
- Each switch shows as one line in the timeline. Tool cards do not change. None of the six sources marks each card.

## Out of scope

- Plan mode, in #60.
- A mode per bot inside a group chat.
- A mode set for one message only.
- A setting on the bot page for the mode a new chat starts in.
- Changing which tools ask in Ask. That stays the config list, the read-word rule for server tools, and the person's saved approvals.

## How we will know it works

- Open a new chat. The message box shows "Ask". Ask the bot to write a memory note. An approval card appears.
- Pick Auto and confirm. Ask the bot to write another note. It is written with no card, and the timeline shows "Mode: Auto".
- Reload the page. The chat still shows Auto. Open a different chat. It shows Ask.
- Ask the bot, in Auto, to write a note from inside a script. The script writes it.
- In Telegram, type `/mode`. The reply names the mode. Type `/mode ask`, then ask for a note. The approval buttons appear.
- Start a long task in Auto, and switch to Ask while it runs. The next protected call shows a card.
- Switch to Auto while a card is waiting. The card stays, and Allow still runs the call.
- `make lint` and `make test` stay green.
