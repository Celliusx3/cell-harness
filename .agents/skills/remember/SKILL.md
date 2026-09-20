---
name: remember
description: Save something the user wants kept (a place, a person, a fact, a decision) and find it again later. Use when the user says remember, save this, note this down, or asks about something they told you before — which cafe did I like, what is my dentist's number, what did we decide about X.
---

# Remember, and find it again

Memory is a folder of notes the user can also open in Obsidian. You write a
note when they ask you to keep something, and you search the notes before
saying you do not know something about their past.

## Workflow

0. **Select first, always.** Your first call is
   `get_function_details({ names: ["memory__write_note", "memory__search_notes", "memory__read_note", "memory__delete_note"] })`.
   Until you have done that, a direct call to any of them is refused with
   "not in your tool list"; if you see that refusal, make this call and try
   again. Every result is a structured object, never a bare string. Then call
   them directly, one at a time.
1. **Save.** `memory__write_note({ title, content, directory, tags })`.
   `title` is the thing's own name ("Kopi Sini", "Dr Lim, dentist").
   `content` is what the user said, in their words, plus what you know that
   makes it findable later: the area, the phone number, the date, why they
   liked it. `directory` is one of `places`, `people`, `notes`; `tags` are two
   or three plain words ("cafe", "bangsar"). If the note already exists, pass
   `overwrite: true` only when the user is updating that same thing.
2. **Find.** `memory__search_notes({ query })` with the words the user used,
   plus the kind of thing ("cafe Bangsar", "dentist phone"). Read the `results`
   list: each has a `title`, a `permalink` and a matching `content` snippet.
   If it is empty, try once more with fewer words.
3. **Read.** `memory__read_note({ identifier })` with the `permalink` of the
   one result that matters, when the snippet is not enough to answer.
4. **Forget.** `memory__delete_note({ identifier })` with the permalink, only
   when the user asks you to forget or delete it.

## Answer

- After a save: one line saying what you kept and under which title, so they
  can correct it. Say it only when the `write_note` result came back with a
  `file_path`; a refusal or an error means nothing was kept, and you say so.
- After a find: the answer in one or two lines, then the note's title in
  brackets so they know where it came from.
- After an empty search: "I have nothing saved about that", then the answer
  from the conversation if you have one. Never invent a memory.

## Do not

- Do not save health, finances, religion, politics or anything the user would
  not want written down, unless they ask you to remember that exact thing.
- Do not save the current task's working details; a note is for what should
  outlive this conversation.
- Do not answer a question about the user's past from general knowledge when
  a search would settle it.
