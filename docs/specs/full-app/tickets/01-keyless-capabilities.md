# 01 The app runs every capability that needs no key

**Status.** done

**What to build.** `desktop/scripts/bundle.sh` adds uv and Node to the
bundle's `bin`, each checked against its published SHA-256, as Deno is. It
installs each project under `mcp-servers/` (not `computer`, which is 04)
with the bundled Python into its own folder. `desktop/config.json` lists
every server `backend/config.json` has, with commands that use the bundled
tools and pinned versions for the `npx` and `uvx` ones. The children's
`npm` and `uv` caches go in the app's data folder. `paths.ts` and its test
change with the layout.

**Checks.** Run `make app`, then the packaged app with `PATH=/usr/bin:/bin`
and an empty home folder. Exa, system monitor, YouTube, memory and jobs
connect, as the backend log shows. A bot answers a question with Exa.

**Blocked by.** none
