"""What the file tools are called with."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from harness.tools.native.files import _descriptions

MAX_ASKED_IMAGES = 12


class SendFileArgs(BaseModel):
    """What the model passes to `send_file`."""

    model_config = ConfigDict(frozen=True)

    paths: list[str] = Field(min_length=1, description=_descriptions.PATHS)


class ExtractArchiveArgs(BaseModel):
    """What the model passes to `extract_archive`."""

    model_config = ConfigDict(frozen=True)

    path: str = Field(description=_descriptions.ARCHIVE_PATH)


class MakeArchiveArgs(BaseModel):
    """What the model passes to `make_archive`."""

    model_config = ConfigDict(frozen=True)

    paths: list[str] = Field(min_length=1, description=_descriptions.ARCHIVE_PATHS)
    name: str = Field(description=_descriptions.ARCHIVE_NAME)


class ViewImageArgs(BaseModel):
    """What the model passes to `view_image`."""

    model_config = ConfigDict(frozen=True)

    path: str = Field(description=_descriptions.IMAGE_PATH)


class AskAboutImagesArgs(BaseModel):
    """What the model passes to `ask_about_images`."""

    model_config = ConfigDict(frozen=True)

    paths: list[str] = Field(
        min_length=1, max_length=MAX_ASKED_IMAGES, description=_descriptions.ASK_PATHS
    )
    instructions: str = Field(pattern=r"\S", description=_descriptions.ASK_INSTRUCTIONS)
    save_to: str | None = Field(default=None, description=_descriptions.ASK_SAVE_TO)


class AskAboutImageJobsArgs(BaseModel):
    """What the model passes to `ask_about_image_jobs`."""

    model_config = ConfigDict(frozen=True)

    jobs_path: str = Field(description=_descriptions.JOBS_PATH)
