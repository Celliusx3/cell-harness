# 01 Browse and download a chat's workspace

**Status.** open

**What to build.**

- `ChatFileService.listing(chat_id, path) -> WorkspaceListing`: one folder of the chat's workspace, its entries folders first then by name. A `WorkspaceEntry` is `name`, `kind: Literal["file", "folder"]` and `size`. A relative path that leaves the workspace, by `..` or a link, raises.
- A route `GET /api/workspaces/{chat_id}?path=` answers the listing, with 404 for a refused or missing path. Downloads use the existing `GET /api/conversations/{chat_id}/file`.
- In the frontend, a "Files" button in `ChatHeader` opens a panel beside the chat. The panel lists the workspace, opens folders, shows the path back, and downloads a file.

**Checks.**

- A unit test lists a workspace with a folder and two files. The folder comes first, with sizes.
- `..` and a link that leaves the workspace are refused.
- An integration test calls the route for a bot's chat and gets the listing.
- The frontend typecheck passes. In the real app, Files in a bot's chat lists its workspace.
- `make lint` and `make test` pass at 80%.

**Blocked by.** none
