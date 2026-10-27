# 08 Link codes

**Status:** done, except the by-hand check with a real token

**What to build.**

- A bot's page gains "Link Telegram" and "Link Discord". Each shows a six-digit code that lasts 15 minutes and names that bot. Codes are kept in memory.
- A direct chat that sends exactly a valid code is linked to that bot, and gets a reply naming it. A new code moves the chat.
- A direct chat that never linked gets no answer. Telegram groups get no answer.
- Discord server channels keep answering @mentions as the Assistant.
- Chats that talk to the Assistant before this change stay linked to it.
- The channels' `conversation_for` reads the link, not the Assistant's id.

**Checks.**

- Tests:
  - a code links a direct chat, and an expired or unknown code does nothing
  - an unlinked direct chat and a Telegram group get no reply
  - a Discord @mention in a server reaches the Assistant
  - a chat stored before this change keeps the Assistant
- By hand: link a Telegram chat to Chef, and Chef answers there.

**Blocked by.** 07

**Notes.**

- The by-hand check has not run: it needs a real Telegram token and a real chat. With a fake token on port 4986, Chef's page showed a six-digit code, the text naming Chef and a countdown, and "Link Discord" showed the 409 message.
- A code link is stored as `ChatState.linked_bot_id`, written only by a code. A Telegram or Discord chat writes into its code's bot; else, once stored (from before codes, under any old id, or a Discord server channel on its first @mention), into Assistant's; else nowhere.
- A chat linked to a bot that is archived or deleted is silent, logged at debug only, and creates no conversation file. Its link stays, so restoring the bot brings it back. It never falls back to Assistant.
- In a Discord server channel nobody has @mentioned, slash commands get silence. The first @mention links the channel to Assistant.
- Wrong guesses below five are kept in memory until a restart; they are never reset.
