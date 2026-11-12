# 06 — A scheduled message is drawn as one

**Status.** open

**What to build.** The browser draws a `schedule/reminder` event as a
scheduled-message bubble with the schedule's title and due time, not as the
person's own message. `frontend/components/conversation/buildTimeline.ts`, the
event type in `frontend/lib/`, and the bubble component.

**Checks.** A frontend test: a timeline with a `schedule/reminder` event
renders the scheduled bubble with its title. Driven in the chat with
`drive-cell-harness`: a run fired from a test schedule shows the bubble.

**Blocked by.** 03
