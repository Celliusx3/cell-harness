---
name: find-place
description: Turn a shared Instagram reel or post into the real place it shows, with a Google Maps link. Use when the user shares an instagram.com link (reel, reels, p, tv) or asks where a reel was filmed, what restaurant/cafe/spot it is, or how to get there.
---

# Find the place in a reel

The user wants somewhere to go. Give them one place they can tap to open in
Maps, or a short shortlist when the evidence genuinely splits — never a
description of what the reel contains.

## Workflow

Write ONE program that does all of this; each step is one capability call.
Before writing it, call `get_function_details` for the four functions below —
every result is `{ items: [...] }` or `{ candidates: [...] }`, never a bare
object, and a program that guesses the shape reads `undefined` and searches for
nothing.

1. **Fetch first, read only if needed.** `instagram__fetch_reels({ urls })` with
   every link the user sent. Look at `caption`, `author`, `hashtags`,
   `mentions` and `tagged_users` before anything else — a caption very often
   names the venue outright, and an `@mention` is usually the venue's own
   account. If that already gives a name and an area, skip step 2.
2. **Look and listen only when the text is not enough.**
   `instagram__read_reels({ shortcodes, want: ["visual"] })`. Add `"speech"`
   only if the caption and the on-screen text still leave you unsure — it is
   slow. Trust evidence in this order: @mention, caption, `overlay_text`,
   `scene`, transcript last. Never take the spelling of a name from the
   transcript.
3. **Search clean.** `places__search_text({ query })` with the venue name plus
   its area or city and nothing else — `"nasi lemak Bangsar"`, not
   `"nasi lemak stall Bangsar blue awning"`. An `@handle` makes a good query.
   Use what you saw in the reel to *re-rank* the candidates, never to search.
   If `candidates` is empty, try a shorter query once before giving up.
4. **Details only for the one you chose.** `places__place_details` costs more
   than searching; call it once, for the single candidate you settled on, and
   not at all if you are showing a shortlist.

Return from the program only what the answer needs: the chosen candidate (or
the shortlist), and the one or two facts from the reel that justify the pick.

## Answer

- **Name** — one line on what it is, in the user's words (a cafe, a viewpoint).
- **Address**, then the `maps_url` as a plain link.
- Why you are confident: the caption said so / the sign in the video read … /
  the account tagged is the venue's. One sentence.
- If `place_details` was called: hours (`open_now`), rating.

When two or three candidates are plausible, list them with addresses and let
the user choose. When nothing matches, say what the reel showed and what you
searched for, so the user can correct the query — do not invent a place.

## Do not

- Do not call `read_reels` for every reel by default; most are settled by the
  caption.
- Do not describe the video. The user has seen it.
- Do not report a reel as unavailable without reading its `detail`.
