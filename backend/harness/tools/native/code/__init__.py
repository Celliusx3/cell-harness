"""Code mode: the model writes one program instead of calling tools one at a time.

Three tools — discover, type, run — over a sandbox that knows nothing about any
of them. `docs/mcp-tool-scaling.md` §6 has the reasoning.
"""

from harness.tools.native.code.prompts import CODE_PROMPT, DETAILS, EXECUTE, LIST
from harness.tools.native.code.tools import RESERVED, code_mode_tools

__all__ = ["CODE_PROMPT", "DETAILS", "EXECUTE", "LIST", "RESERVED", "code_mode_tools"]
