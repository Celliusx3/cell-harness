---
name: search-web
description: Look something up on the web, or read a link the user pasted. Use when the user asks what is the latest, what happened, is it true, when does it open, how much does it cost, or anything that needs today's information, and whenever a message contains a URL to read or summarise.
---

# Search the web, and read a page

The user wants a current answer with somewhere to check it. Give them a few
lines with the url beside each fact, never a page dump and never a guess
dressed as a lookup.

## Workflow

0. **Select first, always.** Your first call is
   `get_function_details({ names: ["exa__web_search_exa", "exa__web_fetch_exa"] })`.
   Until you have done that, a direct call to either is refused with "not in
   your tool list"; if you see that refusal, make this call and try again.
   Both return prose, not an object: a script cannot index into the result, so
   call them directly, one at a time.
1. **Search once.** `exa__web_search_exa({ query, numResults: 5 })`. Describe
   the page you want, not keywords: "the Deno release notes page for the
   latest version", not "deno latest". Each hit comes back as Title, URL,
   Published, Author and a few highlighted lines. Read the Published dates
   before trusting a hit: for a "latest" or "now" question the newest hit
   wins, and you do not know today's date, so say the page's date rather than
   "currently".
2. **Read only when the highlights are not enough.**
   `exa__web_fetch_exa({ urls: [url] })` with the one or two urls that matter,
   never every hit. The user pasted a link: skip step 1 and read it here.
3. **Search again only with a different question.** A second search with the
   same words returns the same hits; change what you describe or stop.

## Answer

- Two to five lines. Every fact that came from the web has its url in
  brackets right after it, so the user can open the source.
- A date or a number is given as the page gave it, with the page's date when
  the question is about "now".
- When the hits disagree, say so and show both with their urls; do not pick
  silently.
- When nothing useful came back, say what you searched for and answer from
  what you already know, marked as such. Never present memory as a lookup.
- When the tool returns an error, say the web is unavailable right now and
  answer from what you know, marked as such.

## Do not

- Do not fetch a page the highlights already answered.
- Do not paste a page. Summarise it and give the url.
- Do not search for what you already know for certain (arithmetic, a
  definition, how to write a loop).
- Do not put a person's private details in the answer because a search
  returned them.
