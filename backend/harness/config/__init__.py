"""Settings, loaded once at the composition root.

Committed defaults live in `backend/config.json`; secrets and local overrides in
`.env` or the environment. Nothing below the composition root reads settings — a
component is handed the values it needs, which is what keeps "which model is
actually in use?" answerable at one call site.
"""

from harness.config.sections import LLMSettings, SessionSettings
from harness.config.settings import MissingConfigError, Settings, load

__all__ = [
    "LLMSettings",
    "MissingConfigError",
    "SessionSettings",
    "Settings",
    "load",
]
