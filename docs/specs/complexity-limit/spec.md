# Every function under a complexity of 10

## Problem

A function's length says little about how hard it is to follow; how many ways it can go does. Nothing in the backend limits that today, and eight functions are past the usual limit of 10: the turn loop and its reply reader, the channel delivery loop, the TypeScript printer, and four route builders. The route builders are past it mostly because 33 of the 44 error blocks across the route files repeat one pattern, "this domain error becomes this HTTP status", inside every handler; each handler nested in a builder also counts toward it, so the two largest builders also register their routes in named groups.

## What changes for you

Nothing a person sees changes, with one edge: a route that today lets a known domain error escape, so the person sees a server error, answers with that error's usual status instead.

How the code reads after it:

1. `make lint` refuses a function past a complexity of 10, as it refuses a file past 300 lines, and the project's rules say so.
2. The turn loop reads as its steps: ask the model, decide whether the step ends the turn, run the tools; each decision has a name.
3. Each domain error is turned into its HTTP status in one place in the web layer. A route handler calls its service and returns; it catches an error only where that route gives it a different meaning, such as a group naming a bot that does not exist (422 instead of 404).

## Decisions

- Complexity, not lines, is limited: ruff's mccabe check at 10, the common default, enforced by `make lint` beside the file-length cap.
- Domain errors map to HTTP once, as FastAPI's custom exception handlers do, chosen over splitting each route builder into groups because it gives a handler one job and lets a new error be added in one line.
- A route that gives an error its own status or its own message keeps its own `except`, which wins over the map.
- The MCP servers and the skill scripts are separate projects with their own lint, and stay out of this change.

## Out of scope

- The four functions past the limit in the MCP servers and skill scripts.
- Any other reshaping of the turn loop.

## How we will know it works

- The 1463 backend tests pass, and lint passes, after every ticket.
- After the last ticket, `make lint` runs the complexity check and the backend passes it; a function made past 10 on purpose fails it.
- A test pins every mapped error to its status and its body, and an error a route lets escape answers its mapped status.
