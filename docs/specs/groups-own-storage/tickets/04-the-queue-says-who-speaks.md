# 04. The queue says who speaks, and the group names stop repeating

**Status.** open

## What to build

`GroupRepository.groups()` and `GroupService.groups()` become `all()`.
Delete `MentionTurnOrder` and `MENTION_TURN_ORDER`. Their two functions go on `SpeakerQueue`, the model they are about: `SpeakerQueue.after_message(text, members)` is the queue a person's message starts, and `SpeakerQueue.next_in(events, members)` is the member who speaks once the log's last turn ended complete.
`after_turn` reads the cap from `MAX_TURNS_FROM_MENTIONS`. Rename `turn_order.py` to `speaker_queue.py`, and its test file with it.
No behaviour changes.

## Checks

`make lint` and `make test` are green before and after. `grep -rnE "MentionTurnOrder|MENTION_TURN_ORDER|turn_order" backend/harness backend/tests` finds nothing. Breaking each moved function fails a test.

## Blocked by

03
