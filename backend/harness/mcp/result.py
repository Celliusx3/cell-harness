"""What a tool call returns, as the model gets it."""

from __future__ import annotations

import base64
import binascii
import json
import logging
from collections.abc import Sequence

from mcp.types import CallToolResult, ContentBlock, ImageContent, TextContent
from pydantic import BaseModel, ConfigDict, ValidationError

from harness.tools import (
    EXECUTION_ERROR,
    Failure,
    Ok,
    ReturnedImage,
    ToolOutcome,
    ToolUi,
)

logger = logging.getLogger("harness.mcp")

FILES_META = "io.cell-harness/files"


class ReturnedFile(BaseModel):
    """One entry of a tool result's `_meta` under FILES_META: a file the tool hands back."""

    model_config = ConfigDict(frozen=True)

    path: str


def outcome_of(
    result: CallToolResult, *, name: str, server: str, resource_uri: str | None
) -> ToolOutcome:
    """What the model gets back."""
    rendered = render_content(result.content)
    if not rendered and result.structured_content is not None:
        rendered = json.dumps(result.structured_content)
    if result.is_error:
        return Failure(EXECUTION_ERROR, rendered or f"{name} reported an error with no message")
    ui = (
        ToolUi(server=server, resource_uri=resource_uri, data=result.structured_content)
        if resource_uri is not None
        else None
    )
    return Ok(
        content=rendered,
        data=result.structured_content,
        ui=ui,
        paths_to_send=returned_paths(result, name=name),
        images=returned_images(result.content, name=name),
    )


def returned_paths(result: CallToolResult, *, name: str) -> tuple[str, ...]:
    """The paths a result's `_meta` names under FILES_META; a malformed entry is dropped."""
    if result.meta is None or FILES_META not in result.meta:
        return ()
    entries = result.meta[FILES_META]
    if not isinstance(entries, list):
        logger.warning("dropped the files %s returned: %s is not a list", name, FILES_META)
        return ()
    paths: list[str] = []
    for entry in entries:
        try:
            paths.append(ReturnedFile.model_validate(entry).path)
        except ValidationError as err:
            logger.warning("dropped a file %s returned: %s", name, err)
    return tuple(paths)


def returned_images(blocks: Sequence[ContentBlock], *, name: str) -> tuple[ReturnedImage, ...]:
    """Each image block's bytes, decoded; one whose data is not base64 is dropped."""
    images: list[ReturnedImage] = []
    for block in blocks:
        if not isinstance(block, ImageContent):
            continue
        try:
            data = base64.b64decode(block.data, validate=True)
        except binascii.Error as err:
            logger.warning("dropped an image %s returned: its data is not base64: %s", name, err)
            continue
        images.append(ReturnedImage(media_type=block.mime_type, data=data))
    return tuple(images)


def render_content(blocks: Sequence[ContentBlock]) -> str:
    """Content blocks as the one string the model sees."""
    parts: list[str] = []
    for block in blocks:
        match block:
            case TextContent():
                parts.append(block.text)
            case ImageContent():
                parts.append(f"[image {block.mime_type}, {len(block.data)} base64 chars]")
            case _:
                parts.append(f"[{type(block).__name__}]")
    return "\n".join(parts)
