"""MCP servers as a source of tools.

A capability is a separate process with its own README and tests, not backend
growth. This package connects to those processes, relays their tools into the
registry, and disconnects without leaving one behind.

The package is named `mcp` and so is the SDK it imports. That is safe: Python 3
has no implicit relative imports, so `import mcp` inside `harness.mcp` reaches
the SDK, never here.
"""
