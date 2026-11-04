# UI layers

## Problem

Everything sits on one screen. Settings, the computer, a new bot and a new group are six unlabelled icons above the chat list. Credentials, Skills and a chat all open beside the same sidebar, so nothing feels like its own place. To manage bots, you hunt between the sidebar's Archived list and each chat's Edit bot button.

## What changes for you

1. You open the app. Assistant's chat opens, as it does today.
2. The sidebar shows the app's name and one "New" button at the top.
3. Below them, it lists your bots' chats under Bots, then your groups under Groups.
4. At its foot, it shows "Bots", "Computer" and "Settings", each with its icon and name.
5. "Computer" shows only when the computer is set up, as today.
6. You click "New". A small menu offers "Bot" and "Group".
7. You pick "Bot". The "What kind of bot do you want?" page opens, as today.
8. You click "Bots" at the sidebar's foot. The Bots page opens beside the chat sidebar.
9. The Bots page lists every bot with the start of its instructions. Assistant comes first.
10. Below the bots, it lists every group with the names of its members.
11. Below the groups, it lists the archived bots, each with "Restore" and "Delete".
12. You click a bot. Its page opens with its name, instructions, keys and chat links, as today.
13. The bot page's header reads "Bots", then the bot's name. "Bots" takes you back.
14. You archive the bot. The Bots page opens and shows it under Archived.
15. You click a group on the Bots page. Its chat opens.
16. You click "Settings". The Settings menu takes the chat sidebar's place.
17. The menu has "Back to chats", then "Credentials", "Approvals" and "Skills". Credentials opens first.
18. Each settings page looks and works as it does today.
19. You click "Back to chats". The page you left opens again.
20. In a bot's chat, "Edit bot" still opens that bot's page.
21. In the Mac app, the menu-bar item "Credentials…" opens Credentials inside Settings.
22. You go to an old address such as /credentials. Its new place in Settings opens.
23. Before a model key is saved, Settings sends you to setup, as every chat page does.

## Decisions

- Settings is its own screen, and its menu takes the sidebar's place with a way back. Sim, LobeHub and Linear build settings this way.
- "Back to chats" opens the page you left, as Sim's Back does. Always opening Assistant's chat was simpler, and was turned down at approval.
- Settings sits under the app's one root layout. The Next.js docs say a move between two root layouts reloads the whole page.
- The Bots page sits beside the chat sidebar and lists bots and groups together, as LobeHub's and Khoj's agent pages do.
- Archived bots sit at the bottom of the Bots page, as Claude's archived projects sit at the bottom of its Projects list.
- A bot's row opens its page, and a group's row opens its chat. Groups have no settings page yet.
- Bot builder stays off the Bots page, as it stays off the sidebar.
- One "New" button opens a menu of Bot and Group. LobeHub's sidebar "+" offers agent and group chat, and Character.ai's "+Create" sits at the top of its left menu.
- The New menu is shadcn's ready-made dropdown menu, built on the Base UI library the app already uses.
- The sidebar stays hand-built. shadcn's ready-made sidebar brings a phone layout and its own colours, which this change leaves out.
- Bots, Computer and Settings sit at the sidebar's foot, where shadcn's sidebar docs put "user menus, settings, or actions". LobeHub's "view all" link on its agents section was turned down at approval.
- Archiving a bot opens the Bots page, where the bot now shows. Today it opens Assistant's chat.
- Saving a bot still opens its chat, as today.
- The old addresses of Credentials, Approvals and Skills send you on to Settings. The Next.js docs suggest redirects "when you change the URL structure of pages".

## Out of scope

- New colours, fonts or components on any page.
- A layout for phones and narrow screens.
- Renaming or deleting a group.
- The computer's screen beside a chat.
- A home page, or opening the last chat at start.
- Any change to the harness, its API or the chat timeline.

## How we will know it works

- Open the app. Assistant's chat opens, and the sidebar's top holds only the name and "New".
- Click "New", then "Group". The New group form opens.
- Click "Bots". The page lists Assistant first, every group with its members, and the archived bots.
- Restore an archived bot. It leaves Archived and shows in the sidebar's Bots list.
- Open a bot from the Bots page and archive it. The Bots page shows it under Archived.
- From a bot's chat, click "Settings", then "Skills", then "Back to chats". The same bot's chat opens.
- Go to /credentials. Credentials opens inside Settings.
- Before any model key is saved, go to /settings. The setup screen opens.
- In the Mac app, click "Credentials…" in the menu bar. Credentials opens inside Settings.
- Run the app with no computer set up. The sidebar's foot shows Bots and Settings, and no Computer.
