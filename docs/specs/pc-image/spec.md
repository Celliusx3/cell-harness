# Our own PC image

## Problem

Every bot's PC runs Rakazo's published image, on a tag that Rakazo can change
at any time. The app downloads that image for every person who installs it. We
cannot see what changed, cannot add to it, and cannot make it smaller.

## What changes for you

1. You start the app. It downloads the PC image from your GitHub account once,
   and the PC starts. Nothing else looks different.
2. You open the Computer page. You see the PC's desktop, and Chromium on it.
3. You take control and click in Chromium. The page reacts.
4. You open the terminal beside the screen and run `python3 --version`. It
   answers.
5. You ask a bot to open a site and tell you what is on it. It reads the page
   and clicks a link by its reference, as it does today.
6. You change the image's recipe and push. GitHub builds the new PC image for
   Mac and for Windows and Linux, and publishes it. The app uses it only after
   the config names that exact version.

## Decisions

1. **The PC image does what Rakazo's image does for us today, nothing more.**
   Pages, the live screen with take-control, the terminal, files and the shell.
2. **Built from scratch on a plain Debian base, with standard packages.** Rakazo,
   Anthropic's computer-use demo, E2B, Cua and Steel all start from a slim
   Debian or Ubuntu base. Each adds Xvfb, a window manager, x11vnc and noVNC.
3. **Chromium, on both arm64 and amd64.** Google Chrome has no Linux arm64 build.
   Rakazo and Steel use Debian's Chromium for the same reason.
4. **agent-browser reads and clicks pages, under a page script of our own.** It
   attaches to the Chromium on the screen and returns the page as text with
   references such as `@e1`. It is one file per machine type, checked by its
   hash. Rakazo uses it the same way. Playwright's snapshot also has
   references, but they work only for the latest snapshot. Playwright also
   brings a Node or Python package with it.
5. **A screenshot is one command in the PC, not a web service.** Today the
   server's only use of Rakazo's control service is a screenshot for the
   preview. A command removes a port, a token and a program. To decide at
   approval.
6. **It only has to run in microsandbox.** Removing the Docker engine is a
   separate change.
7. **GitHub builds it, on its own Mac-type (arm64) and PC-type (amd64)
   machines.** Each half is built natively, then joined into one image. Rakazo
   and Cua build this way. Steel emulates arm64 on one machine, and Rakazo
   notes that emulation "took hours".
8. **Public on GitHub's registry, and the config names the exact version.** A
   tag can move, and an exact version cannot.
9. **Nothing moves across from the current PC.** Its home folder and sign-ins
   are thrown away. The new PC starts empty.
10. **The server's own Rakazo-adapted parts stay for now.** These are the
    live-screen scripts, the terminal program and the file scripts, credited
    in the server's notice. This spec replaces the image only. To decide at
    approval.

## Out of scope

- Removing the Docker engine.
- New abilities in the PC, such as extra Python packages for skills.
- Rakazo's extras around agent-browser. These are hidden secrets on pages,
  upload rules, a cap on how many controls a page lists, and a check before
  each click.
- Google Chrome or Brave as the PC's browser.
- Replacing the server's Rakazo-adapted parts (decision 10).

## How we will know it works

1. Push a change to the recipe. The GitHub build passes, and the registry shows
   one PC image for both arm64 and amd64.
2. Start the app on this Mac with the config naming that version. The Computer
   page shows the desktop with Chromium.
3. Take control and click a link. The page changes.
4. In the terminal, `python3 --version` answers.
5. Ask a bot "open coingecko.com and tell me the top coin". It reads the page
   and answers. Ask it to click a coin, and it opens that coin's page.
6. Use a reference from before the page changed. The bot is told the
   reference is stale, and gets the new page.
7. Search the PC image's recipe and the app's config for "rakazo". Nothing is
   found.
