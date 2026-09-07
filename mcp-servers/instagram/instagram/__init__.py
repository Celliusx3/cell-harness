"""instagram — an MCP server that reads a shared Instagram reel.

It reports observations and never conclusions: no place name, no confidence, no
lookup. Deciding which POI a reel is about is the harness model's job, using the
caption, the mentions, the on-screen text and the scene together. That boundary
is what keeps this server composable with the Places one.
"""
