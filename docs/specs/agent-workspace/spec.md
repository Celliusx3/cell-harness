# Agent workspace

## Problem

An agent is made up of agent nodes: the bot's own chat turn and each of its workers. Today they share no place to work. Every shell on the PC starts in one home folder shared by every bot, and a worker's files land wherever it chooses. The person wants all nodes of one agent to work in one workspace, and each group to have one of its own.

In this spec, "agent" means a bot and "agent node" means its chat turn or one of its workers. The app keeps the words "bot" and "worker".

## What changes for you

1. You make a bot called Translator. It gets an empty workspace folder on the PC.
2. You drop a PDF into Translator's chat. The PDF lands in Translator's workspace.
3. You ask Translator to run `pwd`. It answers with the path of its workspace.
4. Translator hands three tickets to workers. Each worker's shell also starts in Translator's workspace, and each one sees the PDF there.
5. You make a group with Translator and Checker. The group gets its own empty workspace.
6. You drop a PDF into the group. The PDF lands in the group's workspace.
7. Translator answers in the group. Its shell starts in the group's workspace, and it is told where its own workspace is.
8. Translator hands a ticket from the group to a worker. The worker starts in Translator's workspace and is told the group's workspace.
9. The worker finishes `report.pdf` and saves it in the group's workspace. You download it from the group chat.
10. You delete Checker. Checker's workspace is deleted, and the group's workspace stays.
11. You delete Translator too. Translator's workspace and the group's workspace are both deleted.
12. You open an old message with an upload from before this change. The file still opens.

## Decisions

1. Each agent and each group has one workspace folder. The folders sit under the chat files folder, which the PC already sees at the same path. OpenClaw names one folder per agent id. nanoclaw keeps one folder per group.
2. The harness sends the chat's workspace along with every tool call to every MCP server. The PC uses it as the shell's start folder. A call that names its own start folder still runs there. OpenClaw makes the workspace the default start folder, OpenHands starts its terminal there, and nanoclaw fixes it for every run.
3. Each node is also told its workspace in words, together with its agent workspace when it is in a group. OpenClaw and Claude Managed Agents both name the working folder in the system prompt.
4. Nothing blocks a node from reaching another workspace. OpenClaw says its workspace "is the default cwd, not a hard sandbox".
5. Nothing locks the workspace against two nodes writing at once. No source we read locks a shared workspace. Claude Code's agent teams split the work by which files each teammate owns.
6. An upload keeps today's rule of a fresh subfolder of its own, now inside the chat's workspace. Two uploads with the same name never clash. To decide at approval.
7. Relative paths in the PC's file tools resolve against the workspace, like the shell. Without this, the file tools would still start in the shared home. To decide at approval.
8. A ticket records the chat it came from. Its worker saves results for the person in that chat's workspace.
9. A ticket's report goes back to the chat it came from, so the bot hands the result over there. Today every report goes to the bot's own chat, even for a ticket from a group. To decide at approval.

## Out of scope

- Renaming bot to agent or worker to agent node in the code or the app.
- Moving old uploads into the new workspaces.
- Keeping one agent's nodes out of another agent's workspace.
- A PC per agent.
- Deleting a group by itself. The app has no way to do it today.
- Showing a workspace's files in the app.

## How we will know it works

1. In a bot's own chat, ask it to run `pwd`. It prints that bot's workspace.
2. Ask the bot to hand a ticket that runs `pwd`. The worker prints the same workspace.
3. Drop a file into the bot's chat, then ask the bot to list its workspace. The file is there.
4. In a group, ask a member to run `pwd`. It prints the group's workspace, and the member can name its own workspace when asked.
5. Drop a file into the group. It lands in the group's workspace.
6. In a group, ask a member to hand a ticket that writes `hello.txt` for you. The worker's `pwd` is its agent workspace. `hello.txt` lands in the group's workspace, and you can download it from the group chat.
7. Delete one member of a two-member group. Its workspace is gone, and the group's workspace is still there. Delete the other member. The group's workspace is gone too.
8. Open an upload sent before the change. It still downloads.
