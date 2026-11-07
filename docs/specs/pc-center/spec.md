# The PC at the center

## Problem

Today the PC is one optional tool among seven. Bots are not told it exists, and
the app starts without it. It also needs Docker, which every person who
downloads the app would have to install. The PC can reach every port on your
Mac, including the app's own API, which has no login. You want each bot to work
like a person at their own computer, the way Grok Bot does.

## What changes for you

1. You install only the app. The PC comes inside it, on Mac, Windows and Linux.
2. The first time you start the app, it downloads the PC once and starts it.
   If this computer cannot run a PC, the app says what to turn on.
3. You ask any bot "what can you do?". It says it has a PC with Chrome, a shell
   and your chat files. Its instructions did not have to say so.
4. You ask "is solana worth buying?". The bot opens pages in the PC's Chrome
   and runs Python in its shell. You watch it on the Computer page.
5. You take control on the Computer page, and click and type in the PC's Chrome
   yourself. You sign in to a site. Next week a bot uses it, still signed in.
6. You ask a bot to reply to an email on that site. Before it clicks Send, it
   asks you in the chat. It sends only after you answer yes.
7. A web page tells the bot to run a command that calls the app on your Mac.
   The PC refuses the connection, and the bot sees why.

## Decisions

1. **The PC runs in a small VM that ships inside the app.** It uses
   microsandbox (Apache-2.0), which runs our current PC image on Mac, Linux and
   Windows. Claude Cowork ships a VM the same way: "Users install nothing for
   this". Docker's `sbx` and Rancher Desktop also bring their own VM. On
   7 November we booted our PC image in it on this Mac. Chrome opened
   CoinGecko, and a click through the live view worked.
2. **Docker stays as a second engine, chosen in the config.** It already works,
   and some Linux servers have Docker but no VM support. Taken at approval
   (the recommended answer): keep Docker as a setting.
3. **Scripts that call your tools stay in Deno, offline.** The PC is a tool the
   bot uses, and no key of yours reaches it. Grok Bot, OpenMausBot, Rakazo,
   Cloudflare Code Mode and Anthropic all work this way.
4. **The PC reaches only public addresses.** It cannot reach your Mac, your
   local network or cloud metadata. The programs that skills run on your Mac
   stay reachable, each on its own port. OpenMausBot's gate "connects only to
   public addresses". microsandbox has outgoing-traffic rules of its own, so
   the gate is its settings, not a program of ours.
5. **Asking before send, post, pay or delete is the bot's own judgement.** The
   PC's instructions tell the bot to ask first, as ChatGPT agent does. The app
   cannot tell a Send button from any other button, so this is not enforced.
   Taken at approval (the recommended answer): the bot's judgement.
6. **Bots learn about the PC from the PC's own instructions.** An MCP server
   can send instructions when it connects. The app puts the instructions of
   every connected server in the prompt and logs them.
7. **The PC's home folder lives outside the VM.** Sign-ins and files survive a
   restart and a new PC image. Grok Bot says "Image updates preserve files".

## Out of scope

- Routines and webhooks.
- Sign-up and other people's PCs. This is one owner and one PC.
- A PC per bot, and a PC in the cloud. A cloud PC is the only way to keep
  working while your computer is off.
- Scripts that call your tools from the PC.
- An allowlist of public sites.

## How we will know it works

1. With Docker stopped, start the app. The PC starts, and the Computer page
   shows its desktop.
2. Take control on the Computer page and click in Chrome. The page reacts.
3. Sign in to a site, restart the app, and open the site again. You are still
   signed in.
4. Ask a new bot "what can you do?". It mentions the PC, Chrome and the shell.
5. On the PC, `curl` the app's API on your Mac. The connection is refused. A
   public site answers.
6. Run a skill that uses a program on your Mac. It still works.
7. On a test page with a Send button, ask a bot to send a message. It asks you
   before the click.
