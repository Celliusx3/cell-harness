# Workspace files

## Problem

Every bot and every group now has a workspace, but the person cannot see what is in it. They see a file only when a bot hands it over in a message. The person wants a panel beside the chat that shows the chat's workspace, and in a group each member's too.

## What changes for you

1. You open Translator's chat and click "Files" in the header. A panel opens beside the chat with Translator's workspace.
2. Folders come first, then files, each with its size. You click a folder to open it, and a path at the top takes you back.
3. You click a text file or an image. The panel shows it. You click "Download" to save any file.
4. A worker writes `report.pdf` while the panel is open. It shows up in the list at once.
5. You click delete on `old.txt`. A confirm asks "Delete old.txt? Bots lose it too, and past messages that link it will not open it." You confirm, and it is gone.
6. You delete the folder `uploads/`. The same confirm names the folder, and everything in it goes.
7. You open Files in the group Team. It shows Team's workspace first. A switch at the top also offers Assistant's and Checker's own workspaces.
8. You close the panel. The app stops watching the workspace.

## Decisions

1. The panel reads the workspace from the Mac's disk through the harness, so it works with the PC off. opencode and ZCode both list through their own server.
2. The panel lists one folder at a time, folders first, then by name. An entry is its name, whether it is a folder, and its size. opencode and ZCode list the same way.
3. A path that leaves the workspace, by `..` or by a link, is refused. opencode refuses a real path outside its root.
4. While the panel is open, the harness watches that workspace and pushes each change to it. The panel lists the changed folder again. opencode and ZCode both push changes over the stream the app already has open and list the folder again. They use their own watchers. We use `watchfiles`, which is already installed.
5. A workspace a panel shows is named by its chat: a bot's chat or a group's. The harness does not ask which chat the panel is open in, since the app is the person's own.
6. Delete is ours to design: neither opencode nor ZCode deletes from its file tree. A file or a folder goes after one confirm, also while a turn runs.

## Out of scope

- Upload, rename and move from the panel. Uploads stay in the composer.
- Showing a workspace on the Computer page.
- Git status, search, and a tree with many folders open at once.
- Deleting from Telegram or Discord.

## How we will know it works

1. Open Files in a bot's chat. It lists that bot's workspace, folders first.
2. Open a folder, then go back by the path at the top.
3. Click a text file and an image. Each shows in the panel. Download saves the file.
4. With the panel open, have a worker write a file. It appears without a reload.
5. Delete a file and a folder after the confirm. Both are gone from the panel and from disk.
6. Ask for a path with `..` or one through a link that leaves the workspace. The harness refuses it.
7. Open Files in a group. It shows the group's workspace, and the switch shows each member's.
