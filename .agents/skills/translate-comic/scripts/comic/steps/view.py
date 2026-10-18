"""Pages as JPEG files a model can be shown, cut by the page's part areas: original and English."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from comic.chapter.pages import Page
from comic.chapter.work import WorkFolder, rgb_image

JPEG_QUALITY = 88
MAX_IMAGE_BYTES = 5 * 1024 * 1024
SHRINK = 0.75


def jpeg_of(image: Image.Image) -> bytes:
    """`image` as a JPEG, downscaled until it is no larger than MAX_IMAGE_BYTES."""
    scaled = image
    while True:
        buffer = io.BytesIO()
        scaled.save(buffer, format="JPEG", quality=JPEG_QUALITY)
        if buffer.tell() <= MAX_IMAGE_BYTES:
            return buffer.getvalue()
        size = (max(1, round(scaled.width * SHRINK)), max(1, round(scaled.height * SHRINK)))
        scaled = image.resize(size)


def save_view(image: Image.Image, path: Path) -> str:
    """`image` saved at `path` as a JPEG; the path, as the command prints it."""
    path.write_bytes(jpeg_of(image))
    return str(path)


def page_views(work: WorkFolder, page: Page) -> list[str]:
    """Each part of the original page as a JPEG under views/, saved once, top to bottom."""
    paths = [work.page_view(page.page, n) for n in range(1, len(page.parts) + 1)]
    if all(path.is_file() for path in paths):
        return [str(path) for path in paths]
    work.views_folder().mkdir(exist_ok=True)
    image = rgb_image(work.page_file(page.page))
    return [
        save_view(image.crop(part.corners()), path)
        for part, path in zip(page.parts, paths, strict=True)
    ]


def english_views(work: WorkFolder, page: Page) -> list[str]:
    """Each part of the English page as a JPEG under views/, cut as the original is."""
    work.views_folder().mkdir(exist_ok=True)
    image = rgb_image(work.english_png(page.page))
    return [
        save_view(image.crop(part.corners()), work.english_view(page.page, n))
        for n, part in enumerate(page.parts, start=1)
    ]
