# 01. A worker can ask the person to take control

**Status.** done

## What to build

Add `takeover` to `ReportAsk` and `TicketAsk` in `harness/session/domain/heard.py`, and to `ASK` in `harness/tools/native/tickets/models.py`.
Telegram and Discord get its line in `_question_line` (`harness/channels/service/replies.py`).
The chat's `TicketQuestionPanel.tsx` shows a new `TakeoverAnswer` from `TicketAnswers.tsx`. **Take control** opens the Computer page, and **I'm done** or **Skip** hands the screen back and answers as text. Add the kind to `TicketAsk` in `frontend/lib/tickets.ts`.

## Checks

A backend test: a worker's report with `ask: "takeover"` puts its ticket in needs-you, and answering it starts the worker's next turn with the answer. A channel test: the line asks to open the computer in the app. A browser run with a fake model shows the three buttons, and I'm done resumes the worker.

## Blocked by

none
