"""What the model is told about code mode — the three descriptions and the
prompt. Prompt text is code: every sentence below fixed an observed failure,
recorded beside it.
"""

from __future__ import annotations

LIST = "list_functions"
DETAILS = "get_function_details"
EXECUTE = "execute_typescript"

LIST_DESCRIPTION = (
    "List every capability available, as TypeScript function signatures grouped "
    "by the server that provides them. Argument types are omitted — call "
    f"`{DETAILS}` for the ones you intend to use."
)

# Prompt text is code. "callable directly" is the sentence that turns reading a
# schema into selecting the tool; without it the model reads the types and then
# writes a program for a single call, which is a script per step — every cost of
# code mode and none of its saving.
DETAILS_DESCRIPTION = (
    "Get full argument types for named functions. From then on those functions "
    "are in your tool list and callable directly, for the rest of this "
    "conversation. Ask for the few you need, not everything: the point of the "
    "two steps is that you never load the rest."
)

# Prompt text is code. The opening used to be "Write ONE script that does the
# whole task" — the strongest imperative in the request, six lines from the
# decision, and a 7.5B model obeyed it over the system prompt's "only when it
# saves round trips" every time. It now says what a program is *for* first.
# "ONE script" stays for the batch case, because a model given a code tool
# otherwise calls it once per tool; the return/log rule exists because keeping
# intermediate values out of the conversation is the other half of the saving.
# The `main()` sentence: a 7.5B model wrapped its steps in `async function
# main()` and ended with `main();` — the body returned at once, the shim exited,
# and the reply to the call in flight met a dead pipe. Twice in two runs.
EXECUTE_DESCRIPTION = (
    "Run one TypeScript program over the capabilities you have read. For when a "
    "program saves round trips: many calls at once, a loop over many items, or "
    "a large result to filter before you see it. A single call is a direct tool "
    "call, not a program.\n"
    "- When you do write one, write ONE script that does the whole batch. "
    "Several calls in one script cost one round-trip; several scripts cost one "
    "each.\n"
    "- Every call is async: `const r = await yt__get_subtitles({url});`. The body "
    "you write is already inside an async function, so write the steps at the top "
    "level — a `main()` you call without `await` returns before its calls do.\n"
    "- A call returns an object when the tool publishes structured data, and "
    "text otherwise. Log it before assuming its shape.\n"
    "- A failed call throws — `try`/`catch` it and carry on.\n"
    "- Only what you `return` or `console.log` comes back. Everything else stays "
    "in the sandbox, so fetch freely and extract just what you need.\n"
    "- There is no network and no filesystem. The functions are the only way out."
)

# Separate from the tool descriptions: a model decides what it is capable of
# before it reads any of them.
#
# Prompt text is code. The earlier wording made a program the only route, and
# measured against offering every tool directly it lost on every axis at 17
# tools (docs/mcp-tool-scaling.md §6): a sequential task became a script per
# step. "Call it directly" for one call and "a program" for many is Anthropic's
# own guidance for programmatic tool calling, and it is what a 7.5B model could
# do where writing a correct program was beyond it.
CODE_PROMPT = (
    "\n\nMost of your capabilities are not in your tool list yet. Discover them "
    f"with `{LIST}`, then read the ones you need with `{DETAILS}` — from then on "
    "they are in your tool list and you call them directly, like any tool. Write "
    f"a program for `{EXECUTE}` only when one would save round trips: many calls "
    "at once, or a large result you want to filter before you see it. Never tell "
    "the user you lack a capability without listing the functions first."
)
