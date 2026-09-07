"""Tools, and the machinery that offers and runs them.

**Where a tool lives.** A leaf capability — one that does a thing and has nothing
behind it — goes in `native/<name>/`. A tool that is the *door* to a subsystem
goes with that subsystem: MCP's are built in `mcp/tool.py`, and code mode's live
beside the codegen they need. The registry is the one place they meet.
"""
