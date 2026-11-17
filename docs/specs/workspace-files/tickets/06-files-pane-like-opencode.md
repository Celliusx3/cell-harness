# 06 Files open as tabs in a wide pane, and the chat narrows

**Status.** done

**What to build.** The design is the "Like opencode: files open as tabs, the chat narrows" artboard in the Cell Harness Redesign canvas. It follows opencode's layout: the chat keeps 450 px by default and the files pane takes the rest.

- Opening Files narrows the chat to 450 px (at least 400). The files pane takes the rest of the row, at least 320 px.
- A drag handle between them resizes both. The width is kept in the browser, per viewer.
- The pane has a tab bar: "Browse", then one tab per opened file, each with a close button. Clicking a file opens its tab, or moves to it when open.
- Inside the pane, a 220 px tree lists the workspace. Folders open in place. The group or member switch sits at the tree's top.
- A file that appears while the pane is open is marked "new" until it is opened.
- A file tab shows its path, size and change time, then Download and Delete. Text has line numbers in 13 px monospace. An image fills the view.
- Delete asks in place, inside the file's header, with Cancel and Delete, and the same words as today.
- `WorkspaceEntry` gains `modified: datetime`, the file's change time, so the header can say "changed just now".

**Checks.**

- A unit test lists a file and gets its change time as `modified`.
- The frontend typecheck passes.
- In the real app, Files narrows the chat, and the handle resizes it.
- Two files open as two tabs, and closing one leaves the other.
- A file a worker writes shows "new" in the tree.
- `make lint` and `make test` pass at 80%.

**Blocked by.** 05
