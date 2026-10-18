"""Every prompt the harness writes to the model, but a tool's own description."""

from __future__ import annotations

ASSISTANT_INSTRUCTIONS = "You are a helpful assistant."
BUILDER_INSTRUCTIONS = (
    "You are Bot builder. You help the user make a new bot. Find out what it is for, then ask "
    "at most two more questions, each with ask_user, never as a list in your reply. Then call "
    'bot_create once. Its instructions speak to the bot as "you" and carry every answer the '
    "user gave, in their words. If the user denies it, ask what to change."
)

NO_RESPONSE = "NO_RESPONSE"
SPEAKER_TAG = '<speaker name="{name}" />\n{text}'

ATTACHED_FILE = 'The person attached "{name}" ({media_type}, {size} bytes), saved at {path}.'
HANDED_OVER = "Handed over to the person: {path}"
NOT_HANDED_OVER = "Not handed over, because it is not a file in this chat's folder: {path}"

GROUP_NOTE = (
    'You are {name}, one of the bots in the group chat "{group}", '
    "talking with the person and {others}. "
    "A message from another bot starts with a speaker tag naming who wrote it; "
    "the person's messages have no tag. "
    "To ask another bot in this group to respond, write @ followed by its name. "
    "When a message is not addressed to you and you have nothing useful to add, "
    f"reply with exactly {NO_RESPONSE} and nothing else; it is not shown to anyone."
)

BOT_MESSAGE_REQUEST = (
    '<message from="{name}">\n{text}\n</message>\n'
    "{name} is another of the user's bots, not the user. Do what it asks. Your final reply "
    "is sent back to {name} on its own, so write it for {name}."
)
BOT_MESSAGE_RESULT = (
    '<message from="{name}">\n{text}\n</message>\n'
    "This is {name}'s answer to the message you sent it with message_bot. Tell the user what "
    "it means for them. Your reply is not sent back to {name}."
)
BOT_WAITING_ON_USER = "{name} is waiting for the user to answer it in its own chat."
BOT_DID_NOT_FINISH = "{name} stopped before it finished, and has no answer."

CODE_PROMPT = (
    "\n\nMost of your capabilities are not in your tool list yet. Discover them "
    "with `list_functions`, then read the ones you need with `get_function_details` — from then on "
    "they are in your tool list and you call them directly, like any tool. Write "
    "a program for `execute_typescript` only when one would save round trips: many calls "
    "at once, or a large result you want to filter before you see it. Never tell "
    "the user you lack a capability without listing the functions first."
)

GUIDANCE = (
    "When a tool can answer the user's question, "
    "call it instead of guessing. You have a long-term memory in the memory "
    "functions: search it before answering about anything the user told you in "
    "an earlier conversation, and save what they ask you to remember."
) + CODE_PROMPT

SUBAGENT_INTRO = (
    "You are a helper named {name}, started by the main assistant to do one task as part "
    "of its answer to the user. Nobody will read your questions, so do not ask any: do the "
    "task with your tools, then reply with a short result. That reply is all the main "
    "assistant receives."
)

EMPTY_REPLY_NOTE = (
    "Your last reply was empty: no text and no tool call. Answer the user's last "
    "message now, in words, or call the tool you need."
)

NEXT_STEP = "Change the arguments, use another tool, or tell the user what is blocking you."

EXACT_FAILURE_WARNING = (
    "Note: {name} has now failed {n} times in this turn with these same arguments. "
    "Repeating it unchanged will not help. " + NEXT_STEP
)
EXACT_FAILURE_REFUSAL = (
    "{name} has already failed {n} times in this turn with these same arguments, "
    "most recently: {last}. This call was not run. " + NEXT_STEP
)

SAME_TOOL_FAILURE_WARNING = (
    "Note: {name} has now failed {n} times in this turn across different arguments. "
    "It may not be able to do what you are asking. " + NEXT_STEP
)
SAME_TOOL_FAILURE_REFUSAL = (
    "{name} has already failed {n} times in this turn across different arguments, "
    "most recently: {last}. This call was not run. " + NEXT_STEP
)

NO_PROGRESS_WARNING = (
    "Note: this is the same call to {name} as before, and the result is identical — "
    "{n} times now. Calling it again will not answer differently. "
    "Use the result you already have, or do something else."
)
NO_PROGRESS_REFUSAL = (
    "{name} has returned this identical result for these same arguments {n} times "
    "in this turn, so this call was not run. Use the result you already have, "
    "or do something else."
)

REPEATED_CALL_NOTE = (
    "Note: this is call number {n} in a row to {name} with these same arguments. "
    "If you are waiting for something to change, say so; otherwise use what you have."
)

SUMMARY_OPEN, SUMMARY_CLOSE = "<compacted-summary>", "</compacted-summary>"

COMPACTION_PREAMBLE = (
    "This conversation was compacted to free up context. What came before is "
    "summarized below. Treat it as established background: build on it without "
    "restating it, and continue directly from the most recent messages without "
    "mentioning that a compaction happened."
)

_COMPACTION_INSTRUCTION_LINES = (
    "You are now acting as a compaction engine for this assistant. Condense the "
    "conversation ABOVE into a structured checkpoint that lets another model "
    "continue it with no loss of essential context.",
    "",
    "Output EXACTLY the Markdown structure below: keep every section, in order. "
    'Use terse bullets, not prose. Write "(none)" for an empty section — never '
    "drop a section.",
    "",
    "## Primary request and intent",
    "- [what the person wanted, originally and as it evolved; quote verbatim "
    "where the exact wording matters]",
    "",
    "## Key facts",
    "- [names, places, addresses, ids, numbers, dates, links and quotes — the "
    "person's or a tool's — exactly as given]",
    "",
    "## Skills loaded",
    "- [each skill the conversation loaded, by name]",
    "",
    "## Tools used and what they returned",
    "- [tool: the result in one line — what was found, not how]",
    "",
    "## Pending",
    "- [explicitly requested work not yet done, and questions the person has not answered]",
    "",
    "## Current work",
    "- [precisely what was in progress at this checkpoint]",
    "",
    "## Next step",
    '- [the single next action, in line with the most recent request, or "(none)"]',
    "",
    "## Critical context",
    "- [decisions and their reasons, the person's preferences and corrections, "
    "constraints, open questions]",
    "",
    "Rules:",
    "- Preserve exact names, identifiers, numbers, addresses, links and quoted "
    "wording. Never invent a detail that is not above.",
    "- Capture the person's corrections and explicit instructions faithfully.",
    "- Do NOT mention this summarization request or that the context was compacted.",
    "- Output only the checkpoint text: do not call any tool or take any other action.",
    f"- If the conversation already contains a {SUMMARY_OPEN} block, it is a PRIOR "
    "checkpoint. Do not copy it forward verbatim: keep what is still true, drop "
    "what is stale, and merge newer information into one consolidated checkpoint "
    "with the same structure.",
)

COMPACTION_INSTRUCTION = "\n".join(_COMPACTION_INSTRUCTION_LINES)

PRUNED = "[old tool result cleared to save context; call the tool again if you still need it]"

IMAGE_NOT_SHOWN = "[an earlier image, no longer shown: only the newest images are kept]"

IMAGES_FOLLOW = "[images from this result: {count}, shown in the message after the tool results]"

TOOL_IMAGES = "The images the tool results above returned, in the order of those results."

IMAGE_TOO_LARGE = (
    "[an image of {size:,} bytes was not shown: only images up to {limit:,} bytes are sent]"
)

CUT_NOTE = (
    "\n\n[cut: this result was {total:,} characters and only the first {limit:,} are shown. "
    "If you need what was cut, ask for a smaller part, such as a narrower query or fewer rows.]"
)

REFERENCES_NOTE = (
    "Now in your tool list, callable directly: {names}. Call each as a tool for "
    "one step at a time; write a program only to batch many calls or to filter a "
    "large result before you see it."
)

ERROR_PREFIX = "error: "

TOOL_OUTCOME_UNKNOWN = (
    f"{ERROR_PREFIX}this tool call was interrupted and its outcome is unknown. It may have "
    "completed. Retry only read-only or idempotent work; otherwise verify whether "
    "it took effect, or ask the user."
)

SKIPPED_RESULT = (
    f"{ERROR_PREFIX}the user continued without answering this; do not ask again "
    "unless they return to it, and do not wait for it."
)

DENIED_RESULT = (
    "the user pressed Deny, so this call did not run and nothing changed. This is their "
    "decision, not a fault: do not retry it or work around it. Tell them you did not do it "
    "because they denied it."
)

NOTHING_CAME_BACK = (
    "The script ran but returned nothing and printed nothing, so nothing came "
    "back to you — no data has been fetched."
)
