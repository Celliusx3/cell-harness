# Secrets layout

## Problem

The secrets package is one flat folder. Its shapes file holds five subjects at once: where a key may be sent, what the person may type, the sealed form the file keeps, the unsealed and listed forms, and the two errors. The disk store sits beside the rules, not where the project keeps its other stores. Some names make the reader open the code: the unsealed key is called just "secret" beside "sealed secret", the sealing functions are verbs while their neighbour, the redaction function, is named for what it returns, the encryption file speaks of sealing everywhere else, the file's permission is called "owner only" without saying it is a mode, and the redaction marker is called "blanked".

## What changes for you

Nothing a person sees changes. The same keys are saved, refused, listed, removed and sent, and the keyring file keeps its format.

How the code reads after it:

1. The shapes live in a models folder, one file per subject: the destination, the secret as typed and as handed out, the sealed form the file keeps, and the errors. This is how the tools and model code keep theirs.
2. The disk store lives in a repositories folder, with the storage contract beside the service. This is how the sessions and chat state keep theirs.
3. The sealing file is named for sealing, and its two functions are named for what they return, like the redaction function beside it.
4. The unsealed key is called an unsealed secret, the file's permission is called a file mode, and the redaction marker shares redaction's word.
5. Callers keep importing from the package itself; only the fetch tool's one type name changes.

## Decisions

- Shapes in a models folder, one file per subject, as the tools and model code do.
- The disk store under repositories, the contract beside the service, as the sessions and chat state do.
- Renames stay inside the secrets package; the fetch tool and the Keys routes keep their own names.
- Every name outside the package keeps its import from the package itself.

## Out of scope

- The names in the secrets tools and the Keys routes.
- A write that fails before the rename leaves its temp file behind. A bug, for its own change.

## How we will know it works

- The whole backend suite passes before and after: 1497 on this branch today, and the same count after.
- The 117 secrets tests keep passing with the same names.
- No file in the package is left importing an old module path or an old name.
- Breaking one line in each moved file turns a test red: the origin rule, the typed-key rule, the sealed file's shape, the owner-only mode, and sealing each key for its own record.
