"""One chapter's work folder: where each step reads and writes, and its parsed JSON."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from comic.chapter.pages import PAGES, TRANSLATIONS, Page, Translation


def rgb_image(path: Path) -> Image.Image:
    """The image at `path`, read in full and converted to RGB."""
    with Image.open(path) as image:
        return image.convert("RGB")


@dataclass(frozen=True)
class WorkFolder:
    root: Path

    def pages_folder(self) -> Path:
        return self.root / "pages"

    def page_file(self, name: str) -> Path:
        return self.pages_folder() / name

    def _stem(self, name: str) -> str:
        return Path(name).stem

    def clean_folder(self) -> Path:
        return self.root / "clean"

    def clean_png(self, name: str) -> Path:
        return self.clean_folder() / f"{self._stem(name)}.png"

    def english_folder(self) -> Path:
        return self.root / "english"

    def english_png(self, name: str) -> Path:
        return self.english_folder() / f"{self._stem(name)}.png"

    def views_folder(self) -> Path:
        return self.root / "views"

    def page_view(self, name: str, part: int) -> Path:
        return self.views_folder() / f"{self._stem(name)}-part{part}.jpg"

    def english_view(self, name: str, part: int) -> Path:
        return self.views_folder() / f"{self._stem(name)}-english-part{part}.jpg"

    def is_unpacked(self) -> bool:
        return self.pages_json().is_file()

    def pages_json(self) -> Path:
        return self.root / "pages.json"

    def translations_json(self) -> Path:
        return self.root / "translations.json"

    def pages(self) -> list[Page]:
        return PAGES.validate_json(self.pages_json().read_bytes())

    def translations(self) -> dict[str, Translation]:
        return TRANSLATIONS.validate_json(self.translations_json().read_bytes())
