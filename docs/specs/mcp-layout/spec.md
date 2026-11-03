# Spec: the mcp package, laid out like the rest

## Problem

The mcp package took its shape before the house layout settled. Its first
cleanup gave each file one job and fixed the names, but the package still reads
unlike tools, secrets and the model code. Its shapes hide inside the files that
use them. The contract for a server session and the real stdio session share
one file. The relay, a table of loopback pages for the browser, sits in a
package about tool servers. Callers reach into six modules by path, because the
package lists nothing that it offers.

## What changes for you

Nothing a person sees changes. Routes, responses, events and logs are what they
were.

How the code reads after it, with one example. The web startup needs the
service, the three errors and the relay table.

1. Today it imports them from three modules by path. After, it imports the
   service and the errors from the mcp package itself. It imports the relay
   table from a new relay package.
2. The relay package has three files. A service holds the open relays. A
   models file holds the shapes. A third file points a tool result's relay
   entry at a new relay.
3. The mcp shapes live in a models folder, one file per subject. Its subjects
   are the errors, a server's status, the queued commands, and a file a tool
   hands back. This is how secrets keeps its shapes.
4. The session contract is one file. The real stdio session lives under a
   clients folder. This is how the model client and the keyring store are
   split.
5. The package's first file lists the names other packages may use. The
   connection loop and the result renderer are used only inside, so their
   files are marked private.
6. The first part of this branch stays. The result renderer has its own file.
   The names say which side of the tool boundary they name. The error
   unwinding has a test.

## Decisions

- The relay becomes its own package, beside mcp. Its table class becomes a
  service, as bots, runs and mcp name theirs. (to decide at approval)
- The real session goes under a clients folder, as secrets puts its disk store
  under repositories. Files and images keep theirs flat, the other choice. (to
  decide at approval)
- The service keeps the stdio session as its default. Passing it in from
  startup would touch 13 test files that never start a server. (to decide at
  approval)
- The package lists only the names other packages import, as the model package
  does. A file it does not list gets a leading underscore. (to decide at
  approval)
- The models files keep plain names, even the two that only the package uses.
  The tools models folder does the same. (to decide at approval)
- The error describer moves beside the connection, its one caller. Then the
  models folder holds only shapes. (to decide at approval)
- The result builder keeps its name, which ends in "of". A strict reading of
  the naming rule would rename it, because it builds a new value. (to decide at
  approval)

## Out of scope

- The app routes and the relay routes keep their files and names.
- Stale build output under the package stays untouched.
- Test helper locals keep their names. Only imports and the names the change
  touches move.
- No new test guards the list of names, as the model package has none. The
  layering test already fails when another package imports a private file.

## How we will know it works

1. Run the backend suite. 1669 tests pass before the change and after each
   ticket.
2. Run lint. Check, format and the line and complexity caps pass after each
   ticket.
3. Run the mcp and relay tests. The same 152 pass with the same names,
   including the real stdio server run.
4. Search for imports of an mcp or relay module by path from outside its
   package. After the last ticket, the search finds only tests of a private
   file.
5. Import a private mcp file from the web code on purpose. The layering test
   fails.
