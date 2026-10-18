# The model vocabulary in a models folder, with names that say what they give back

## Problem

The model package keeps its whole vocabulary in two files: one holds tool calls, tool specs, the three kinds of block a result is made of and the five kinds of message, and the other holds the stream's events. A reader looking for what a tool call is opens the same file as one looking for how a result's text is joined. Seven names make the reader open the code to learn what they give back: the function that joins a result's text is called render, the context-window lookup is called length, a raw tool-call fragment is read by a function named after its own argument, and the endpoint's listing of models is read into a class called just Model.

## What changes for you

Nothing a person sees changes. The model is sent the same requests and its replies are read the same way.

How the code reads after it:

1. The vocabulary sits in a models folder, one file per subject: tool calls and specs, the blocks a result is made of, the messages, and the stream's events. The client keeps its name and its file.
2. The rest of the app still imports everything from the model package itself; only the files inside the package change their imports.
3. A result's text is had from text_of, which sits beside images_of. The context window comes from context_window_tokens, the name the app already logs it under. The private helpers of the line reader and the converter say what they give back.

## Decisions

- The client keeps the name client, as the person chose; there is no service file.
- The models folder has four files by subject, as the person chose. Its first file holds only its description: inside the package files import each other directly, as the bots service imports the bots models.
- All seven renames, as the person chose.

## Out of scope

- Renaming the stream's Completed and Failed events.
- The adapters folder, whose structure was settled by the one-door change.

## How we will know it works

- The 1455 backend tests pass, and lint passes, after every ticket.
- After the first ticket, no file imports the old message or stream module; a search finds nothing.
- After the second, a search for each old name finds nothing in the code, the tests or the docs.
