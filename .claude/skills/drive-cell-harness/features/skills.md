# Skills

A page listing the skills the bot can load, with an editor for the ones in the editable folder and an upload for a zip.

## Sub-features

- Create, edit and delete a skill in the editable folder.
- Upload a skill as a zip with its bundled files.

## How to get to it (user POV)

Click "Skills" in the sidebar.

## Driving it with Playwright MCP

`browser_click` "Skills", snapshot the list, edit in the textbox labelled "SKILL.md".

## Gotchas

The editable folder is `skills.editable` (`~/.agents/skills` by default), the person's real folder: point `HARNESS_SKILLS__EDITABLE` at `$RUN` before writing anything there.
