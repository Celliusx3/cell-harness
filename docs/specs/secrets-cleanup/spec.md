# Secrets cleanup

## Problem

The keyring works, but one class does two jobs. It holds the encryption key and the rules for what may be saved, and it also parses the file, writes a temp file, makes it owner-only and renames it into place. Someone who changes how the file is written edits the class that holds the encryption key, and the only test that notices a file left readable by others starts the whole web app. Images and chat files are already a service over a storage contract with one disk class; the keyring is shaped differently. The 100-key cap sits in the shapes file, away from the only check that uses it, and the lookup is called "find" though the project names a lookup for what it gives back.

## What changes for you

Nothing a person sees changes. The same keys are saved, refused, listed, removed and sent, and the keyring file keeps its format, so an existing one opens as before.

How the code reads after it:

1. The routes and the fetch tool ask one secrets service, as they do today.
2. The service holds the rules: one site per name, at most 100 keys, a blank encryption key refused, each key sealed for its own record.
3. Behind it, a storage contract that only reads every sealed key and replaces them all, with one disk implementation.
4. The disk implementation owns the file: its format, the owner-only write, the rename into place. It never sees an unsealed key or the encryption key.
5. The lookup is named for the secret it gives back.

## Decisions

- A service over a storage contract with one disk class, as the images and chat files are.
- Flat files beside the shapes, as the images and chat files are; the sessions' older nested folder is not copied.
- The contract trades the whole keyring, read on every call and written whole, as today.
- Sealing stays in the service; storage only sees sealed keys.
- The seal and unseal functions keep their names, the usual crypto words.

## Out of scope

- A write that fails before the rename leaves its temp file behind. A bug, for its own change.
- Syncing the keyring write to disk, as the chat state does.

## How we will know it works

- The whole backend suite passes before and after: 1492 on this branch today, plus the new tests.
- The 112 secrets tests keep passing, each moved to the module it now tests, with the same names.
- New tests hold what had none: a failed write keeps the saved keys, the keyring's folder is made when missing, and the file is owner-only, checked without the web app.
- Breaking one line in each moved piece turns a test red: the owner-only step, the 100-key cap, the one-site-per-name rule, and sealing each key for its own record.
- Starting the app with an existing keyring lists its keys on the Keys page.
