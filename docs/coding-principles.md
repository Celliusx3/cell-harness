# Coding Principles

Behavioral guidelines for everyone (humans + LLMs) writing code in this repo. Adapted from [Andrej Karpathy's observations on LLM coding pitfalls](https://x.com/karpathy/status/2015883857489522876).

**Tradeoff:** these guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:

- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First (KISS + YAGNI)

**KISS — Keep It Simple:** the minimum code that solves the problem, nothing
clever. **YAGNI — You Aren't Gonna Need It:** build only what the current task
needs, nothing speculative.

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- No "we might need it later" hooks, params, or interfaces — add them when the
  second caller actually arrives, not before.
- If you write 200 lines and it could be 50, rewrite it.

Ask: *"Would a senior engineer say this is overcomplicated?"* If yes, simplify.

Concrete: three similar code paths is fine — extract only at ~5+ when the shape genuinely converges. An abstraction earns its keep once several concrete variants share it; below that threshold, inline is better.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:

- Remove imports/variables/functions that *your* changes made unused.
- Don't remove pre-existing dead code unless asked.

**The test:** every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure typecheck + tests pass before and after"

For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## Check before committing

Run the project's typecheck and test suites and make sure they pass before committing. Weak criteria ("it seems to work") aren't enough — the checks must be green.
