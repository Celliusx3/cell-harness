# 06 Code inside a sentence shows without backticks

**Status:** done

This is a bug fix, so its commit is a `fix:`.

**What to build.**

- `frontend/components/conversation/Message.tsx`: the reply's `prose` adds `prose-code:before:content-none prose-code:after:content-none`, and styles inline code as a chip: a tinted background, a little padding, rounded corners, normal weight.
- Fenced code blocks keep their own look.

**Checks.**

- `npm run typecheck` and `npm run build` in `frontend/` pass. `make lint` passes.
- By hand, with the drive-cell-harness skill: ask the bot to name a file in backticks. The name shows as a tinted chip with no backtick characters.
- By hand: ask for a fenced code block. It looks as it does today.
- By hand: in dark mode, the chip is readable.

**Blocked by.** none
