---
name: translate-comic
description: Translate comic pages into English and write it into the original bubbles. Use when the person attaches comic pages or a chapter and asks for it in English.
compatibility: Needs photocraft-cli installed on the Mac that runs the app; the bots' computer starts it for this skill.
metadata:
  host-service: photocraft-cli serve --port {port} --control-token-file {token_file} --automation-read-root {files} --automation-write-root {files}
  host-service-env: PHOTOCRAFT
---

# Translate a comic into English

You find the bubbles, read them and write the English. This skill's scripts run
in your computer: they erase the original text with PhotoCraft and write your
English in its place. The pages can be in any language, and their text can run
in rows or in columns from top to bottom.

Every script runs through `computer__shell`. Its `command` is `uv run --script`,
then this skill's folder followed by `/scripts/run.py`, then the step and its
arguments. A run prints one JSON object. A run whose output starts with `error:`
failed; read the line and act on it. While a run's `status` is `running`, call
`computer__shell` again with the same arguments.

## Workflow

0. **Select the tool first.** Your first call is `get_function_details` with
   `names` set to `["computer__shell"]`. Call `computer__shell` and
   `view_image` directly, never from `execute_typescript`: a script does not
   receive the images. `view_image`, `make_archive` and `send_file` are
   already in your tool list.
1. **Unpack the pages.** Run the step `pages` with one argument: the attached
   file's path, the part after "saved at". Its `work` is the work folder. Each
   entry of its `pages` has `page` (the page's name), `parts` and `views`: one
   image path per part, top to bottom, each overlapping the next.
2. **For each page in `pages`, in order:**
   1. Call `view_image` with `path` set to each of the page's `views`, in
      order. In each part, find every speech bubble and caption with text in
      it. Leave out text drawn into the artwork, such as sound effects.
   2. Each bubble is one item, with four fields. `part` is the number of the
      view, counting from 1, that shows the whole bubble. `box_2d` is the box
      around all of the bubble's original text in that view, as
      `[ymin, xmin, ymax, xmax]`, each from 0 to 1000 of the view's height or
      width; cover every letter and stay inside the bubble's outline.
      `original` is that text exactly as you read it in the image. `english`
      is your English for it. Two bubbles that touch are two items. A bubble
      that shows in two views is one item, from the view that shows all of it.
   3. Run the step `write` with two arguments, the `work` folder and the
      `page`, and with `stdin` set to every item of the page as one JSON list,
      in reading order. Never put the items in `command`. Each write replaces
      the page's English and starts again from the original page, so send all
      of the page's items every time, also when you fix one box or one line.
      A page with no bubble or caption is written with an empty list, so it
      still gets its `english`.
   4. Check the result. Call `view_image` with `path` set to each of its
      `views`. Each area in `left_over` still holds text, given as `part` and
      `box_2d` like an item's: when it is a bubble or caption, add an item for
      it or widen the box of the item that only partly covered it; when it is
      part of the drawing, leave it. Shorten each line in `cut_off` (it did not
      fit even at the smallest size) or `spills` (it runs onto a bubble's edge
      or the artwork). Fix a line that sits outside its bubble or a box that
      cut a bubble's outline. Then run `write` again for that page. Stop fixing
      the page when the checks are clear or its `attempt` is 3.
3. **Hand them over.** Call `make_archive` with `paths` set to every page's
   `english`, in page order, and `name` set to the attached file's name with
   `-english` before its extension. Call `send_file` with `paths` set to the
   archive's path. Then run the step `cleanup` with two arguments, the `work`
   folder and the archive's path; it deletes everything else in the work
   folder.

## Answer

- How many pages and how many bubbles are now in English.
- Each area or line still in any page's `left_over`, `cut_off` or `spills`, by
  page, that you could not fix.
- Text you left untranslated on purpose, by page.

## Do not

- Do not describe or retell the pages. The person can see them.
- When a run fails, read its `error:` line. If it names your items, fix them
  and run again; otherwise tell the person the error in one line and stop.
