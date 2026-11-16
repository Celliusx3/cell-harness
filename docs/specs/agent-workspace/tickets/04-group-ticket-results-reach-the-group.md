# 04 A ticket from a group hands its result over in the group

**Status.** open

**What to build.**

- `Ticket` gains `chat_id: str`, the chat it came from. A ticket stored before this change reads as its bot's chat.
- `ticket_route` records `CallOrigin.conversation_id` as the ticket's `chat_id`.
- The worker still runs in its bot's chat, so its shell starts in the bot's workspace.
- Its files-folder line and the check on its result files name the workspace of the ticket's chat.
- `worker_chat_id` uses `ticket.chat_id`. If Decision 9 passes, the report's delivery uses it too.

**Checks.**

- An integration test has a member of a group route a ticket. The worker's shell calls carry the bot's workspace.
- The worker's task names the group's workspace.
- A ready report naming `<group workspace>/hello.txt` reaches the group's chat with a hand-over note.
- The ticket file route serves `hello.txt`.
- A ticket stored without `chat_id` still loads and reports to its bot's chat.
- `make test` passes at 80%.

**Blocked by.** 02
