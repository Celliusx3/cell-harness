"""Our messages and tools in the Chat Completions shape."""

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

REFERENCES_NOTE = (
    "Now in your tool list, callable directly: {names}. Call each as a tool for "
    "one step at a time; write a program only to batch many calls or to filter a "
    "large result before you see it."
)


def wire_message(message: Message) -> dict:
    """One message in the provider's shape."""
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
        # Some providers treat `tool_calls: []` differently from the key being absent.
        return {"role": "assistant", "content": message.content}
    if isinstance(message, ToolMessage):
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id,
            "content": _tool_content(message.content),
        }
    return message.model_dump()


def _wire_arguments(arguments: str) -> str:
    """The model's raw arguments, unless the provider cannot carry them."""
    try:
        json.loads(arguments)
    except json.JSONDecodeError:
        return "{}"
    return arguments


def _tool_content(blocks: tuple[Block, ...]) -> str:
    """A result's blocks as the one string this wire carries."""
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
