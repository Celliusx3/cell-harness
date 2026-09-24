---
name: create-skill
description: Make a new skill, or change one, together with its reference files and TypeScript scripts. Use whenever the user asks to save something as a skill, make or create a skill, turn what you just did into a skill, or add a reference, script or file to a skill.
---

# Create a skill

A skill is a folder: a `SKILL.md` with the instructions, plus the files those
instructions point to. `references/` holds facts a step reads when it needs
them; `scripts/` holds TypeScript programs a step runs. You write all of it
with three tools, and each one asks the user first: wait for their answer.

## Workflow

1. **Name it.** Lowercase letters, digits and single hyphens: `unit-convert`.
2. **Save `SKILL.md` first.** `skill_save({ name, text })`. No file can be
   written into a skill that does not exist yet. `text` has exactly this shape:

   ```markdown
   ---
   name: unit-convert
   description: Convert kilometres to miles and kilograms to pounds. Use when the user asks to convert a distance or a weight between these units.
   ---

   # Unit convert

   1. Read the script: `skill({ name: "unit-convert", path: "scripts/convert.ts" })`.
   2. Change only its first line to the user's number and units, then run it:
      `execute_typescript({ code: <the whole script>, description: "convert" })`.
   3. When the user asks where a factor comes from, read
      `skill({ name: "unit-convert", path: "references/factors.md" })`.
   ```

   The first line is `---`, and the frontmatter ends at the next line that
   holds only `---`. The instructions go below that line, never inside the
   frontmatter. The description says what the skill does and when to use it,
   in the words the user would type. Every step that reads or runs a file
   shows the exact call with its arguments, as above: "read it with the
   skill tool" alone leaves the next reader guessing a tool name.
3. **Write each reference.** `skill_write_file({ name, path: "references/factors.md", text })`.
   Plain facts, each one named by the step in `SKILL.md` that reads it.
4. **Write each script.** `skill_write_file({ name, path: "scripts/convert.ts", text })`.
   A script is the body of an async function, exactly like
   execute_typescript's code:

   ```ts
   const input = { value: 5, from: "km", to: "miles" };
   const factors: Record<string, number> = { "km:miles": 0.621371, "kg:pounds": 2.20462 };
   const factor = factors[`${input.from}:${input.to}`];
   if (factor === undefined) {
     return { error: `no factor for ${input.from} to ${input.to}` };
   }
   return { ...input, result: Math.round(input.value * factor * 1e6) / 1e6 };
   ```

   The first line is `const input = { ... }`, the only line that changes
   between runs, and the last statement is a `return`. No `import`, no
   `export`, no `function main()` around it. Only TypeScript runs here; a
   Python or shell script cannot, so write those steps as instructions.
5. **Run it once.** Read the script back with
   `skill({ name, path: "scripts/convert.ts" })`, set its first line, and pass
   the text to execute_typescript as the code. A script is a program you pass
   as code, never a function you call: there is no `unit_convert__convert`.

## Answer

- Say a file was saved only when its tool result said so: "saved skill
  'unit-convert'", "wrote 'references/factors.md' in skill 'unit-convert'".
  An error means that file was not written: fix what the error names and
  write it again, or tell the user it failed.
- When the user pressed Deny, say it was not saved because they denied it.
- End with the test run's result, and that `/name` uses the skill next time.

## Do not

- Do not write a file before `skill_save` has succeeded for that skill.
- Do not put secrets, passwords or API keys in a skill.
- Do not describe a file you did not write.
