# 04 Menu bar

**Status:** done

**What to build.**

- `desktop/src/tray.ts` adds a menu-bar icon with Open Cell Harness, Open in Browser, Show Settings File and Quit.
- Closing the window hides it. Clicking the Dock icon shows it again.
- A second launch focuses the first copy.
- `processes.ts` records the children's pids in a file in the data folder after start. A clean quit deletes the file.
- On the next start, a recorded pid that is still alive and runs our command is stopped first.
- After that, a port another program already holds stops the start with a box naming the port. Otherwise the app would take that program for its own.
- The menu-bar icon is drawn in code as a black ring with a dot, so there is no image file to ship.

**Checks.**

- node:test on the stray-pid decision: a dead pid is skipped.
- An alive pid with another command is skipped, and an alive pid with our command is stopped.
- node:test on the icon: one pixel per point at each scale, black, a ring with a dot.
- By hand: close the window, and `curl 127.0.0.1:4887` still answers.
- By hand: Quit from the menu, and nothing listens. `kill -9` the app, start it again, and it opens.
- By hand: hold port 4887 with another program, start the app, and a box names the port.

**Blocked by.** 02
