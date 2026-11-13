# 04. A worker's request moves its ticket to Needs you

**Status.** open

## What to build

When a worker's turn ends waiting on the person, its ticket shows in **Needs you** with the waiting call's card.
`harness/tickets/service/ticket_service.py` reports the waiting call, and `frontend/app/(chat)/needs-you/page.tsx` shows the card under the ticket. The change names no tool.

## Checks

A backend test: a worker that ends waiting puts its ticket in the needs-you list, and an answer takes it out. A browser run: the worker's ticket shows **Take control** on the Needs you page.

## Blocked by

01, 03
