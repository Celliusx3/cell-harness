# 08 Link codes

**Status:** open

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
