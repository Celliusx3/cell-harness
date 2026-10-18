"""What the model is told about code mode — the three tool names and their descriptions."""

from __future__ import annotations

LIST = "list_functions"
DETAILS = "get_function_details"
EXECUTE = "execute_typescript"

LIST_DESCRIPTION = (
    "List every capability available, as TypeScript function signatures grouped "
    "by the server that provides them. Argument types are omitted — call "
    f"`{DETAILS}` for the ones you intend to use."
)

DETAILS_DESCRIPTION = (
    "Get full argument types for named functions. From then on those functions "
    "are in your tool list and callable directly, for the rest of this "
    "conversation. Ask for the few you need, not everything: the point of the "
    "two steps is that you never load the rest."
)

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
    "- There is no network and no filesystem. The functions are the only way out.\n"
    "- A function that returns images cannot be called from a script, which cannot pass "
    "them on to you. Call it directly as a tool."
)

IMAGES_STAY_OUT = (
    "{name} returns images, which a script cannot pass on to you. Call it directly as a tool "
    "to see them."
)
