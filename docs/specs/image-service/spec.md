# Image service

## Problem

How the images a model is shown are kept and chosen is spread over two modules, one beside the sessions and one beside the turn loop. Several of their names don't say what comes back. The chat files reviewed in the previous change are a service over a storage contract; the images, the same kind of thing, are shaped differently. The turn loop's image field is called "vision" though it holds the place images are kept. "Show no images" is spelled as "show the newest zero images, up to zero bytes". Startup builds the image store twice.

## What changes for you

Nothing a person sees changes: the same images reach the model, the same notes replace the ones that are not shown, and the same route serves an image only to the chat whose log names it.

How the code reads after it:

1. The turn loop, the tool results, the model adapter and the image route all ask one image service.
2. The service holds the rules: which types a model is sent, the 5 MB cap, that a kept image still holds the bytes its hash names, and which names can be images.
3. Behind it, a storage contract that only keeps and finds bytes by hash, with one disk implementation.
4. The turn loop's field is named for what it holds, and "no images" is a call that says so.
5. Startup builds one image service and hands it to the turn loop and the web channel.

## Decisions

- The same shape as chat files: a service over a storage contract with a disk implementation, as this repo's sessions and chat files are.
- The images get their own package beside the chat files, instead of one module beside the sessions and one beside the turn loop.
- One image service, built once at startup, as with chat files.

## Out of scope

- An image logged without a size counts nothing toward the 12 MB budget. A bug, for its own change.
- What code mode says when a script calls a tool that returns images.
- The later file-tools change, which builds its own chat file service and shows images by path; it is reviewed with that change.

## How we will know it works

- The whole backend suite passes before and after: 1331 on this branch today.
- PR 3's 52 image tests keep passing, each moved to the module it now tests, with the same names.
- The frontend typecheck stays clean.
- Breaking one line in each moved piece turns a test red: the hash check on read, the 5 MB cap, the type filter, the route's "only images this chat's log names", the "no images" call, and startup handing the turn loop the image service.
