# The model code answers through one door

## Problem

The bots, images, secrets and sandbox packages each have a front door: the package lists what other packages may use, the files only it uses are marked private, and a test stops other packages from importing a private file. The model code has none of this. Ninety-eight files reach into its separate modules by path, so nothing says which names are its public vocabulary, and the four helper files of the adapter (the converter, the line reader, the call joiner and the overflow check) are as open to the rest of the app as the client itself.

## What changes for you

Nothing a person sees changes. The model is sent the same requests and its replies are read the same way.

How the code reads after it, with one example: the turn code needs a tool call, a tool result and the completed event.

1. Today it imports them from two modules by path. After, it imports all three from the model package itself, the way the run code imports a bot from the bots package.
2. The web startup builds the client and asks for the context window through the adapters package's own door, not through the files that hold them.
3. The four adapter helpers are marked private. If any other package imports one, the existing layering test fails.
4. Inside the model package, files import each other directly, as the bots service imports the bots models.

## Decisions

- The door copies the bots package: the package's first file lists the names other packages use, and only those, as every other door in the app does.
- A file whose names the door exports keeps its plain name, and a file used only inside the package gets a leading underscore, as the bots models and service do beside the private turn order.
- Tests may import a private file to test it directly, as the turn-order test does; the layering test checks only the app's code.
- No new test guards the door, as the bots package has none; the existing layering test guards only the private files.

## Out of scope

- Renaming the model files themselves or merging them into one models file.
- Doors for the other packages that lack one.
- The two docstring fixes on the line reader, left from the cleanup.
- A test that fails when another package imports a model file by path.

## How we will know it works

- The 1455 backend tests pass, and lint passes, after every ticket.
- After the last ticket, no file outside the model package imports its modules by path; a search for those import lines finds nothing.
- Importing a private adapter file from the web code, on purpose, fails the layering test.
