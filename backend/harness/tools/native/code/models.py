"""What the three code-mode tools are called with."""

from __future__ import annotations

from pydantic import BaseModel, Field


class NoArgs(BaseModel):
    pass


class DetailsArgs(BaseModel):
    """Arguments for `get_function_details`."""

    names: list[str] = Field(
        description="Exact function names from list_functions, e.g. ['yt__get_subtitles']."
    )


class ExecuteArgs(BaseModel):
    code: str = Field(
        description=(
            "The body of an async function. Call tools by their exact name — "
            "`await yt__get_subtitles({url})`. Use `return` for the answer and "
            "`console.log` for anything else worth seeing."
        )
    )
    description: str = Field(description="One line saying what the program does.")
