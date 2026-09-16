"""Our messages and tools in the Chat Completions shape.

Outbound only: the translation from `llm.messages` to what this endpoint
accepts. It lives here rather than on the models because it is this
provider's dialect, not something the loop or the log should know. The
inbound direction — SSE frames back into stream events — is `openai.py`.
"""

from __future__ import annotations

import json

from harness.llm.messages import (
    AssistantMessage,
    Block,
    Message,
    Text,
    ToolMessage,
    ToolReference,
    ToolSpec,
    render_text,
)

# How a `tool_reference` block reads on a wire that has no such block. Anthropic's
# API expands references into the tool list itself; this endpoint cannot, so the
# pipeline does the list and this sentence does the telling. Prompt text is
# code: without it a 7.5B model handed four TypeScript declarations wrote a
# program to call them, three runs out of three, while the four tools sat in its
# list unused — nothing had said the list changed.
REFERENCES_NOTE = (
    "Now in your tool list, callable directly: {names}. Call each as a tool for "
    "one step at a time; write a program only to batch many calls or to filter a "
    "large result before you see it."
)


def wire_message(message: Message) -> dict:
    """One message in the provider's shape.

    Our `AssistantMessage.tool_calls` is flat (`id`, `name`, `arguments`); the
    wire nests the last two under `function` and adds a redundant `type`. The
    translation lives here rather than on the model because it is this
    provider's dialect, not something the loop or the log should know.
    """
    if isinstance(message, AssistantMessage) and message.tool_calls:
        return {
            "role": "assistant",
            "content": message.content,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": _wire_arguments(call.arguments)},
                }
                for call in message.tool_calls
            ],
        }
    if isinstance(message, AssistantMessage):
        # `tool_calls: []` is not the same as absent to every provider, and an
        # assistant message without calls should not claim to have an empty set.
        return {"role": "assistant", "content": message.content}
    if isinstance(message, ToolMessage):
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id,
            "content": _tool_content(message.content),
        }
    return message.model_dump()


def _wire_arguments(arguments: str) -> str:
    """The model's raw arguments, unless the provider cannot carry them.

    Kept byte-for-byte when they parse. When they do not — a truncated call, or
    the `""` a small model emits for a parameterless tool — LM Studio answers
    every request that replays the message with a 500, which is a conversation
    that can never recover. The log still holds the call as emitted, and the
    model already saw the `INVALID_ARGUMENTS` result; only the wire is repaired.
    Same repair as hermes-agent's `sanitize_tool_call_arguments` and kimi-cli #1171.
    """
    try:
        json.loads(arguments)
    except json.JSONDecodeError:
        return "{}"
    return arguments


def _tool_content(blocks: tuple[Block, ...]) -> str:
    """A result's blocks as the one string this wire carries.

    Text is joined; references become the sentence above. The block *is* the
    fact and lives in the log; this is only how it is spelled to a model that
    cannot read blocks.
    """
    parts = [render_text(blocks)] if any(isinstance(b, Text) for b in blocks) else []
    referenced = sorted(b.tool_name for b in blocks if isinstance(b, ToolReference))
    if referenced:
        parts.append(REFERENCES_NOTE.format(names=", ".join(referenced)))
    return "\n\n".join(parts)


def wire_tool(spec: ToolSpec) -> dict:
    """One tool declaration in the provider's shape."""
    return {
        "type": "function",
        "function": {
            "name": spec.name,
            "description": spec.description,
            "parameters": spec.input_schema,
        },
    }
