# 02 The skill's long-chapter workflow

**Status.** done

**What to build.** In `Celliusx3/skills`, `comic-translator/SKILL.md` gains a "Long chapters" section with three roles:

- **Prepare.** Run `detect` and create an empty `names.json` in the work folder. Report ready with the page count and the work folder's full path. Add one task line per part, which the bot copies word for word.
- **Part.** Read and translate only the pages the task names. Before each page, read `names.json`. When a new name or term appears, add it.
- **Combine.** Run `render`. On its "untranslated" error, report blocked and name the pages. Otherwise check, pack and report the CBZ's full path.

A chapter with fewer than about 3 pages for each worker keeps today's single-worker workflow.

**Checks.** `evals/evals.json` gains a prepare, a part and a combine case, each with the expected report shape. A copy of the app shows the new section through the `skill` tool.

**Blocked by.** 01
