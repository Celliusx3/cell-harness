# 02 Preview a text file or an image in the panel

**Status.** open

**What to build.**

- Clicking a file in the panel shows it in the panel. An image shows from the existing file route. A text file shows its first 256 KB.
- Any other file shows its name and size with "Download".
- Text is read from the existing file route in the browser. No new route.

**Checks.**

- The frontend typecheck passes.
- In the real app, a `.txt` file and a `.png` each show in the panel, and a `.pdf` offers Download.

**Blocked by.** 01
