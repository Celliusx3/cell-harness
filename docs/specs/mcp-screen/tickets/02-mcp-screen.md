# 02 The MCP servers screen

**Status.** open

**What to build.** A Settings page "MCP servers" beside Credentials. It lists
the built-in PC and the person's servers, each with its state and error,
asking again while one is starting. Add server and Edit open a form: name,
command, arguments one per line, settings as `NAME=value` rows, and the
names of keys it needs. Remove asks first. Restart shows on a failed
server. A server waiting for a key links to Credentials. The sidebar's
Computer link is unaffected.

**Checks.** On a private copy of the app: add `npx -y exa-mcp-server`; it
shows running and a bot searches with it. Add one needing a key; it waits;
the key added on Credentials starts it. A bad command shows failed with its
error; Edit fixes it. Remove stops it. The frontend's typecheck and build
are green.

**Blocked by.** 01
