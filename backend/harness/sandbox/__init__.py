"""Running an untrusted script and letting it call back.

`Runner` is the seam; `DenoRunner` is the only implementation today. Deliberately
knows nothing about tools, MCP, or the model — it takes code, a list of names to
expose, and a callback. `tests/unit/test_layering.py` enforces that.
"""

from harness.sandbox.deno import DenoRunner, DenoUnavailableError
from harness.sandbox.runner import Bridge, BridgeError, Runner, Script

__all__ = ["Bridge", "BridgeError", "DenoRunner", "DenoUnavailableError", "Runner", "Script"]
