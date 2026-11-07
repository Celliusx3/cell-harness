# MCP servers you set up yourself

## Problem

The app ships capabilities you may not want, such as markets, and carries uv
and Node to run them. You cannot add a server of your own without editing
config files and restarting. You want only the PC built in, and a screen
where you set up your own MCP servers.

## What changes for you

1. You open Settings, then MCP servers. It lists the built-in PC and the
   servers you added. Each shows its state: running, waiting for a key, or
   failed with its error.
2. You click Add server. You type a name and a command such as `npx`. You
   add its arguments one per line, and its settings as `NAME=value` rows.
   You list the keys it needs, such as `EXA_API_KEY`.
3. You click Save. The server starts within seconds, with no restart. Its
   tools reach the bots on their next message.
4. A server that needs a key waits. You open Credentials and add a
   Capability key for it. It starts.
5. A server failed. You fix its command with Edit, or click Restart.
6. You click Remove. The server stops, and the bots no longer see it.
7. In the Mac app, a command that works in your Terminal, such as `npx` from
   Homebrew, works here too.
8. `make dev` shows the same screen. Its config files list only the PC.

## Decisions

1. **Only the PC is built in.** Every other server is added on the screen.
   The app stops carrying uv, Node and our other capabilities.
2. **A form, not a file to edit.** Cherry Studio and Goose add a server
   through a form with command, arguments and settings. Claude Desktop,
   Cursor and LM Studio make you edit a JSON file and restart.
3. **Programs on this Mac only.** Servers at a web address come later.
4. **Saved in their own file, beside bots.json.** The bots file works this
   way. Cherry Studio keeps its servers in its own store too.
5. **A change applies at once.** Adding, editing or removing a server
   starts or stops only that server. Cherry Studio restarts one server the
   same way. Claude Desktop and Cursor need a full restart.
6. **The form names the keys a server needs; their values stay on
   Credentials.** Goose saves only key names with a server, and keeps the
   values in the keychain.
7. **The screen is the one place for servers.** A server listed only in a
   config file stops the harness, with a message to add it on the screen.
   To decide at approval.
8. **The Mac app reads your Terminal's PATH at start.** 5ire does this with
   `fix-path`; Cherry Studio runs your shell with `-l`. Assumed, not yet
   confirmed: see Assumptions.
9. **You install Node and uv yourself.** The app no longer carries them.

## Assumptions

- The Mac app finds commands through your Terminal's PATH (decision 8). You
  did not confirm this; it was the recommended answer.

## Out of scope

- Servers reached by web address, and sign-in.
- A list of known servers to add with one click.
- An on/off switch: remove a server to turn it off.
- Moving today's servers onto the screen. It starts empty.
- Importing a Claude Desktop or Cursor config file.

## How we will know it works

1. Add a server with `npx -y exa-mcp-server`. Within a minute it shows as
   running, and a bot searches the web with it.
2. Add one that needs `GOOGLE_MAPS_API_KEY`. It shows as waiting. Add the
   key on Credentials, and it runs.
3. Edit a server's command to one that does not exist. It shows failed,
   with the error. Fix it, and it runs.
4. Remove a server. A bot no longer lists its tools.
5. Restart the harness. The servers you added come back.
6. Open the Mac app from the Dock. A server run with Homebrew's `npx`
   starts.
7. The Mac app is smaller than 436 MB, and has no uv or Node inside.
