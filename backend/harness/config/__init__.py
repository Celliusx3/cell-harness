"""Settings, read from the environment at the composition root — phase 1.

Nothing below the composition root reads settings: a component is handed the
values it needs. That is what keeps "which model is actually in use?" answerable
by looking at one call site rather than tracing a settings object through the
graph.
"""

from harness.config.settings import LLMSettings

__all__ = ["LLMSettings"]
