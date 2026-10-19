# The tools package gets a service, its one way in

## Problem

The tools folder shows five files side by side, and nothing says which one to start from, while every other backend package starts from its service file. The registry and the dispatcher always arrive together: the dispatcher holds nothing but the registry and the gate, and the pair is threaded through the code-mode tools, two startup helpers and both tool lists. A tool list built over one registry with a dispatcher over another would show the model tools it cannot run.

## What changes for you

Nothing a person sees changes. Every call runs as before, in the same order, and the model is shown the same schemas.

How the code reads after it, with one example: a script calls the clock tool.

1. The startup builds one tool service from the tools and the gate, in the tools folder's service file, as the bots service sits in the bots folder's.
2. The code-mode tools and each tool list are handed the service alone.
3. The script's call goes to the service, which asks the gate, finds the tool and runs it, in one file.

## Decisions

- The registry and the dispatcher become one tool service, as the person chose, matching the bots, skills and MCP services.
- The tool list stays its own file, the turn's way in, one for the main agent and one for subagents over the same service.
- The gate stays its own file, used by the Approvals page and the client tools.
- The service keeps the method names the two parts had, so the rule that every call goes through the one dispatch keeps its meaning.
- A variable holding the service is named for it, tool service, because the startup already calls the session service plain service.

## Out of scope

- The runtime builder's thirteen parameters.
- The Telegram channel's check on one tool's name.
- The web server reaching the service through the main tool list.

## How we will know it works

- The 1488 backend tests pass, and lint passes, after every ticket, with one new test: a call that must ask waits before its tool is looked up.
- Every tool's schema is byte-identical before and after.
- A search for the registry and dispatcher classes and modules outside the specs finds nothing.
- Making the service look a tool up before asking the gate fails the new test.
