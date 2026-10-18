# Model code cleanup

## Problem

The code that talks to the model provider works, but it is harder to read and easier to break than it needs to be. Reading one streamed line is split across two files, and each file checks the line's fields its own way. The system instructions are sent through a catch-all that copies every field, and nothing tests that path. A failure code is free text, so a typo would quietly stop long chats from being compacted. Several names make the reader open the code to learn what they give back: a function called classify that returns a code, a method called drain that empties nothing, and a file called models that holds no models. Tests lean on a shortcut the app never uses, and on an image size that quietly defaults to zero.

## What changes for you

Nothing a person sees changes, with one exception: a streamed line that is valid JSON but not an object (a bare number, or null) used to crash the reply, and is now skipped with a warning, the same as a line that is not JSON at all.

How the code reads after it:

1. Each streamed line is read once, in one place, into a small named shape: its text, its tool-call pieces, its token count, and whether the provider sent an error. The code that joins tool-call pieces takes those shapes and checks nothing itself.
2. The request is built by its own small function. The function that streams only connects, reads and hands back events.
3. The system instructions are sent as their role and their text, by name. Anything that is not one of the four message kinds is refused instead of copied.
4. Every name says what it gives back: the overflow check returns a failure code, the accumulator returns its tool calls, and the file that reads the context window says so.
5. A failure code comes from a fixed list. An image always states its size. The tools list has no silent default.
6. Tests read a result's words with the same helper the app uses.

## Decisions

- Streamed lines are read with hand-written type checks into frozen dataclasses, not with a pydantic model, because pydantic's lax mode would turn the text "7" into the number 7 and reject a whole tool call over a numeric id, both of which today are ignored field by field.
- The client interface stays an abstract base class, as the repo's other subclassed interfaces are (the tool hooks, the step hooks, the sandbox runner).
- The tools list keeps "none" as a value and loses only its default, because the turn sends none when a bot has no tools and tests recognise the compaction request by it.
- The failure code is a fixed list, as the stream's kind fields already are.

## Out of scope

- Checking a tool's schema. It belongs where a schema first comes in, in the tools code; checking it in the model code would give every request a new way to fail.
- Renaming the stream's Completed and Failed events to nouns.
- Moving the application message next to the session events; the two session files would import each other.
- Sharing the provider address and login header between the two files that build them.

## How we will know it works

- The backend suite passes with the coverage gate, and lint passes, after every ticket.
- The 1428 tests that passed before still pass, with only call shapes and names changed, plus new tests for every streamed-line rule nothing checked: an index sent as text, an id sent as a number, a token count sent as text, a token count kept from an earlier line, empty text, an empty error, lines after the end marker, a later extra-content block, the request's address, login header and body, and how a system message is sent.
- A streamed bare number or null no longer crashes the reply: a test sends one and the reply completes.
- Each ticket's piece, broken on purpose, fails a test.
- A real chat with a live model streams a reply and runs a tool, as before.
