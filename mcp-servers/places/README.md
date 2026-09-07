# places

Resolve a described place to a real POI: canonical name, address, coordinates,
`place_id`, and a Google Maps link.

Two tools over **one documented endpoint** — `POST /v1/places:searchText` from
Places API (New), plus `GET /v1/places/{id}` for details.

## Why this is ours and not a dependency

The house workflow says prefer battle-tested libraries, so the search was run
first. The finding was that nothing credible is maintained *and* correctly
shaped:

| Option | Why not |
|---|---|
| `@modelcontextprotocol/server-google-maps` | **Deprecated**, and non-functional in a new project — every endpoint it calls became Legacy on 2025-03-01 and is unavailable in new Cloud projects |
| Google's *Maps Grounding Lite* | Remote-HTTP only, and its `search_places` schema has **no `displayName` and no `formattedAddress`** |
| PyPI `google-maps-mcp` | Pins `googlemaps==4.10.0`, the legacy client — wrong API generation |
| `@cablate/mcp-google-map` | Maintained and on the right API, but see below |

The last one was actually wired in first, and replacing it is the reason this
directory exists. Four measured problems:

1. **It declares no `outputSchema` on either tool** — verified by listing its
   tools. So it cannot populate `structuredContent`, `Ok.data` arrives as `None`,
   and a code-mode script reading its result gets `undefined`. That is precisely
   the failure `docs/mcp-tool-scaling.md` §6 finding 4 recorded: *"five failing
   scripts and a cancelled turn."*
2. **Its field masks are hardcoded** to include `rating`, `userRatingCount`,
   `currentOpeningHours`, `reviews` and `editorialSummary` — Enterprise and
   Atmosphere tier fields. Every search bills at the top tier, so **1,000 free
   calls a month instead of 5,000**, and the masks are not configurable.
3. **Those fields land in the session log permanently.** A tool result becomes a
   `ToolResultEvent`, which is append-only and kept by design. Google's Platform
   ToS §3.2.3 permits storing `place_id` indefinitely but expects place content
   to be resolved on read — so a mask that returns reviews on every search stores
   reviews forever.
4. It is pre-1.0 and single-maintainer, in the path of a capability we care
   about, and it cannot be shaped: no mask control, no candidate count.

Against ~180 lines over one endpoint, depending on it was the more expensive
option.

## Requirements

A `GOOGLE_MAPS_API_KEY` from a GCP project with **Places API (New)** enabled.
Billing is normally mandatory — but the **Maps Demo Key** is a documented
no-credit-card path that covers Places API (New), and is the fastest way to a
first working run.

| Variable | Default | Notes |
|---|---|---|
| `GOOGLE_MAPS_API_KEY` | — | required |
| `PLACES_MAX_RESULTS` | `3` | operator config, not a model argument |
| `PLACES_TIMEOUT_SECONDS` | `30` | |
| `PLACES_BASE_URL` | Places API (New) | override for tests |

## The field mask is the price

Billing is per call at the **highest tier any requested field touches**, so the
mask in `config.py` *is* the cost, and `tests/unit/test_config.py` asserts it
stays Pro. Widening it is a one-word edit that quietly cuts the free allowance by
80%, which is exactly the mistake the server this replaces makes.

| SKU | Free/month | Then |
|---|---|---|
| Text Search **Pro** — what `search_text` uses | 5,000 | $32/1k |
| Text Search Enterprise | 1,000 | $35/1k |
| Place Details **Enterprise** — what `place_details` uses | 1,000 | $20/1k |

`place_details` accepts the higher tier deliberately: hours and a phone number
are the point of asking, it is a **separate** SKU with its own allowance, and it
is only called once a candidate has been chosen. Its description says so, because
fanning it across candidates is the expensive mistake.

Also note the universal **$200/month credit ended 2025-02-28** and was replaced
by these per-SKU caps. Anything you read quoting $200 is stale.

## Text Search will not take a description

The single most important thing to know. Google documents that Text Search *"is
not intended for ambiguous queries"* and names the failing shapes: *"too many
concepts or constraints"* and *"unofficial or vanity names"*.

So a query built straight from a reel — `nasi lemak stall Bangsar blue awning
banana leaf` — is bad **by construction**; no index contains "blue awning" and
its presence actively harms the match. Verified against the public geocoders too:
one non-indexed descriptor took Nominatim and Photon from 2 results to **0**.

The pipeline that works: the model **normalizes** the evidence to a clean
name-and-area query, gets a few candidates, then **re-ranks those** using the
visual detail. Descriptors are disambiguation signal, never search input.
`search_text`'s description carries a worked example, because the model is the
only thing that can get this right.

## You cannot save to a Google Maps list

Definitively, and this is settled rather than uncertain. The My Maps write API
died **31 Jan 2011**; `place/add` died **30 June 2018** (and wrote to Google's
global database, never to a user's list); the Data Portability API is
export-only and covers *starred places only*; there is no OAuth scope for Maps
saved places at all; and the feature request has been open since **2010** with
~927 votes, still unshipped.

So every candidate carries a `maps_url` — `maps/search/?api=1&query=…&query_place_id=…`
— which is officially documented, **needs no API key**, and opens the native app
where one tap saves it. It is built locally rather than requested, so
`places.googleMapsUri` could be dropped from the mask without losing the link.
A link the person taps is not a workaround; it is the only compliant path.

## Tests

```sh
uv run pytest     # hermetic: httpx.MockTransport, no network, no key needed
uv run ruff check . && uv run ruff format --check .
```

Faked at the `httpx` transport, so the assertions can cover the two things that
actually matter and are invisible otherwise: **the field mask that is sent**, and
whether location bias reached the request body or was silently dropped.
