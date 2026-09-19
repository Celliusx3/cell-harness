"""The model's only documentation."""

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
