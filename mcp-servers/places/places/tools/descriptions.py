"""The model's only documentation.

Same three constraints as the Instagram server's, all from the harness's
TypeScript printer: descriptions are collapsed to one line, argument `Field`
descriptions are invisible, and the return type prints as `Promise<unknown>`. So
each is one dense paragraph naming every argument and every returned field.
"""

from __future__ import annotations

SEARCH_DESCRIPTION = (
    "Find real places matching a name and area, and return up to a few candidates with "
    "coordinates and a Google Maps link. args: { query: string, latitude?: number, "
    "longitude?: number, radius_meters?: number }. Give latitude and longitude together to bias "
    "results toward an area; radius_meters defaults to 5000 and bias influences ranking without "
    "excluding anything outside it. Returns { query_sent, candidates: [{ place_id, name, address, "
    "latitude, longitude, kind, maps_url }], detail }. Send a CLEAN query: the venue's name plus "
    "its area or city, and nothing else. This endpoint is documented as not built for ambiguous "
    "queries, and extra descriptive words actively harm the match — 'nasi lemak stall Bangsar "
    "blue awning banana leaf' returns nothing, while 'nasi lemak Bangsar' returns real stalls, "
    "because no index contains 'blue awning'. So use the visual details you gathered to RE-RANK "
    "the candidates this returns, never to search. An @handle from a reel is usually the venue's "
    "own account name and makes an excellent query; a dish name plus a district is the next best. "
    "An empty candidates list is not an error — read detail, then try a shorter query. maps_url "
    "needs no API key and opens the place in Google Maps, where one tap saves it, so it is the "
    "right thing to hand a person: there is no API that can add a place to their saved list."
)

# "Send a CLEAN query" and the nasi-lemak example: Google's own docs say Text
# Search is "not intended for ambiguous queries" and list "too many concepts or
# constraints" and "unofficial or vanity names". Verified against public
# geocoders too — one non-indexed descriptor took a working query to 0 results.
# Without this paragraph the model pastes the whole reel description in.
#
# "An @handle ... makes an excellent query": measured. A live reel's caption
# carried "📍 @natalinaitalian", which is the venue's real name.
#
# "there is no API that can add a place to their saved list": stops the model
# offering to save it. The My Maps write API died in Jan 2011 and `place/add` in
# June 2018; the feature request has been open since 2010.

DETAILS_DESCRIPTION = (
    "Get opening hours, rating, website and phone for ONE place you have already chosen. "
    "args: { place_id: string } — the place_id from a search_text candidate. Returns "
    "{ place_id, name, address, latitude, longitude, maps_url, opening_hours: { open_now, weekly "
    "}, rating, rating_count, website, phone }. Call this only after you have settled on a single "
    "candidate: it is a separate, more expensive billing tier than searching, and calling it for "
    "every candidate to help you choose costs several times what choosing from the search results "
    "does. If you are unsure between candidates, show them to the person with their addresses and "
    "let them pick."
)

# "only after you have settled on a single candidate": Place Details is a
# separate SKU at a higher tier than Text Search, so fanning it out across
# candidates is the expensive mistake. The last sentence gives the model
# something to do instead, because "don't" alone left it calling details anyway.
