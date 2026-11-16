"""The skills a ticket's task names, each written as `<name> skill`."""

from __future__ import annotations

import re
from collections.abc import Sequence


def named_skills(task: str, names: Sequence[str]) -> tuple[str, ...]:
    """Each of `names` that `task` writes as `<name> skill`, in the order of `names`."""
    return tuple(name for name in names if re.search(rf"(?<![\w-]){re.escape(name)} skill\b", task))
