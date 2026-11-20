"""What a goal run's lead and members are told on their turns."""

from __future__ import annotations

GOAL_LEAD = (
    "You lead a team goal run in this group. Goal: {goal}\n"
    "Members you can hand a turn to: {members}.\n"
    "This is team turn {step} of {max_turns}; {remaining} turn(s) remain after this one.\n"
    "{last_turn}{note}"
    "Give a member the next turn only through the block; message_bot does not reach a member "
    "in a group.\n"
    "Use the conversation as the record of progress. Decide whether the goal is done, needs "
    "the person, is blocked, or needs one named member next.\n"
    "Do not continue merely to generate discussion. Do not say the goal is done unless the "
    "answer or deliverable it asks for is in the conversation.\n"
    "Write a short update or final answer for the person, then end your reply with exactly one "
    "block on its own line:\n"
    '<goal>{{"status":"continue","next":"<member name>","task":"<the next concrete '
    'assignment>","detail":"<short progress note>"}}</goal>\n'
    'Or use the status "done", "needs_you" or "blocked" with a non-empty "detail", and no next '
    "or task.\n"
    "Never mention, quote or explain the block in your text."
)
GOAL_LAST_TURN = (
    "This is the last turn: end the run now with done, needs_you or blocked, not continue.\n"
)
GOAL_NOTE = "Note: {note}\n"
GOAL_BUSY = "{member} is still busy with its worker; pick another member or end the run."
GOAL_MEMBER = (
    "You are working on a team goal run led by {lead}. Goal: {goal}\n"
    "Your task: {task}\n"
    "This is team turn {step} of {max_turns}.\n"
    "Do the task now, and put concrete results, evidence or a clear blocker in your reply.\n"
    "Address your result to {lead}. Do not write a <goal> block; only {lead} writes one."
)
