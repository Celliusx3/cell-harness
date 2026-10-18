# The tools code in the model code's shape

## Problem

The tools package has no front door. Twenty-one app files reach into seven of its files by path, so nothing says which names are its public words. Its vocabulary is spread over files that also do the work: what a tool returns sits with the argument checker, the person's approve-or-deny answer sits with the gate that writes the grants file, and what a running tool is handed is split over two files. The client tools mix their answer shapes with the code that reads them. Half the native tools keep their argument shapes in a models file and half inline them, and the helpers only one tool folder uses look as public as the tool. Several names make the reader open the code to learn what they give back: render outcome returns blocks, approve runs a call, asks and granted are a question and a list that read as neither, and pending tool calls differs from pending calls by one word.

## What changes for you

Nothing a person sees changes. Every tool does what it did, and the model is shown the same schemas.

How the code reads after it, with one example: someone adds a weather tool that fails for the city Atlantis.

1. They copy any native tool folder: each keeps what it is called with and what it answers in its models file, the tool in its tool file, and a helper only it uses behind a leading underscore.
2. The bots folder's files are named for their tools.
3. They import success, failure and the context from the tools package itself, as they import a tool call from the model package.
4. Those words sit in a models folder, one file per subject: what a call returns, what a running tool is handed, and the person's answer to a call that asks. The definition, registry, dispatcher, pipeline and approval gate sit beside it.
5. The client tools keep every shape in their models file, and their other files keep only the code.
6. The failure for Atlantis becomes the blocks the model reads through a function named for those blocks, beside the model package's text of. An approved call runs through a name that says it runs an approved call, and the gate's question and list read as a question and a list.

## Decisions

- The door lists only the names other packages use, as the model package's door does.
- The client tools and each native tool keep their own doors, as the model package keeps its adapters behind their own door, and as the person chose for the native tools. The client tools read the session log, which reads the tools package, so one door for both would loop.
- The definition stays beside the registry, as the model package keeps its client beside its models folder.
- The core models folder has one file per subject, and its first file holds only its description, as the model package's does.
- The client tools get one models file, not a folder: their shapes come to about seventy lines, and each native tool has one models file.
- A file only its own folder uses gets a leading underscore; a file whose names a door exports keeps its plain name, as the OpenAI adapter does.
- What a tool is handed to do its work (the subagent runner, the bot message sender) stays with the tool, as the model client stays out of the model package's models folder.
- The location tool and the code tool keep their own no-arguments shapes: location's description is part of the schema the model reads.
- Tests may import a private file to test it directly, as the model package's tests do.
- The client service's gated and awaited keep their names: the channels name the same set gated outside the tools package.

## Out of scope

- Failure codes as a fixed list.
- Typing a tool's schema.
- A return type for the code tool's script bridge.
- Trimming the client door's exports that only tests read.
- One door for all the native tools.

## How we will know it works

- The 1485 backend tests pass, and lint passes, after every ticket, with one new test: the session models, the client tools and the skills tool each import first, on their own, in a fresh interpreter.
- After the first two tickets, no file outside the tools package imports one of its seven core files by path.
- After each ticket, a search for each old path and name finds nothing outside the specs.
- Every schema the model is shown is the same before and after the native shapes move.
- Each ticket's piece, broken on purpose, fails a test.
