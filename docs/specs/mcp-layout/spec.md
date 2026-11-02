# Spec: the mcp package, laid out like the rest

## Problem

The mcp package took its shape before the house layout settled, and it kept the
older one. One file promises tools but also holds the sorting of tools and the
rendering of tool results. A reader who knows the session, secrets, files and
images packages re-learns the conventions here. Two different names travel as
one: the name a server knows a tool by, and the name the model calls the tool
by. One function is named for what it takes, not for what the caller gets
back. A yes-or-no helper does not say yes-or-no in its name. The flattening of
an exception group into one log line has no test.

## What changes for you

Nothing you see changes. Routes, responses and events are what they were.

1. You chat, add a server and open an app exactly as before.
2. You open the mcp package and find one file per job: the service, the
   connection loop, the client boundary, the errors, the tools, and a new file
   for what a tool result becomes for the model.
3. Names say what they hold. A function that returns a tool is named for the
   tool. A yes-or-no helper starts with is. The server-side tool name and the
   model-facing tool name are two different names everywhere they travel.
4. The exception-group flattening has a test that guards it.

## Decisions

- The client boundary keeps its name. It holds a live session to a server
  process, not storage, and the model boundary is named client the same way.
  (to decide at approval)
- No shared shapes file. The status shape stays beside the connection that
  produces it. The relay and result shapes are their own subject's data. (to
  decide at approval)
- The relay module stays one file. The relay table and the meta rewrite are one
  flow with no import line between them. (to decide at approval)

## Out of scope

- The service keeps building its connections over the injected client factory.
  A second factory with one implementation is a layer, not a cleanup.
- The package keeps importing per module. Callers already import the module
  they need, and package re-exports would be new surface with no reader.
- Stale build output under the package stays untouched.
- Test helper locals keep their names. Only imports and names the change
  touches move.

## How we will know it works

1. Run the unit suite. 1325 tests pass before the change and after it.
2. Run the integration suite. 186 tests pass before and after, including the
   real stdio server run.
3. Run lint. Check, format and the line and complexity caps pass before and
   after.
4. Run the new error test. It passes on the code as it stands, before any
   rename.
