# 03 Delete a file or a folder after a confirm

**Status.** done

**What to build.**

- `ChatFileService.delete_path(chat_id, path)` deletes a file, or a folder with everything in it, inside the workspace. It refuses the workspace itself and any path that leaves it.
- A route `DELETE /api/workspaces/{chat_id}?path=` answers 204, or 404 for a refused or missing path.
- Each row in the panel has a delete button. The confirm reads "Delete <name>? Bots lose it too, and past messages that link it will not open it."

**Checks.**

- A unit test deletes a file and a folder. The workspace itself, `..` and a link that leaves it are refused, and nothing is deleted.
- An integration test calls the route, and the file is gone from disk.
- In the real app, a deleted file is gone from the panel.
- `make lint` and `make test` pass at 80%.

**Blocked by.** 01
