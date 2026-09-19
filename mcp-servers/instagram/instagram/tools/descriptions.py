"""The model's only documentation."""

from __future__ import annotations

FETCH_DESCRIPTION = (
    "Download shared Instagram reels or posts and read their text metadata. Pass every URL you "
    "were given in ONE call: items are fetched concurrently, so ten URLs in one call cost about "
    "what two cost separately. Accepts instagram.com/reel/<code>/, /reels/, /p/, /tv/, "
    "/<username>/reel/<code>/, a bare shortcode, and tolerates ?igsh= / ?stkn= / ?utm_source= "
    "tracking parameters. args: { urls: string[] }. Returns { items: [{ url, shortcode, status, "
    "detail, media, duration_seconds, author, caption, hashtags, mentions, tagged_users, "
    "posted_at, retry_after_seconds, backend }] } with one item per URL, in the order given. "
    "status is ok, unavailable (private, deleted, or Instagram refused it), rate_limited (see "
    "retry_after_seconds), unsupported_url (detail says what to send instead), or error; one bad "
    "URL never fails the others, so check status per item and read detail before reporting "
    "anything as missing or abandoning the batch. media is video, image (only a poster image was "
    "available) or none (text only). The caption, the author handle, the hashtags and especially "
    "any @mention of the venue's own account are the most reliable evidence of which place a reel "
    "is about, and a caption very often names it outright — read them first and decide whether "
    "read_reels is worth its cost, because many reels need no video analysis at all. Keep "
    "the shortcode: it is the only key read_reels accepts."
)


READ_DESCRIPTION = (
    "Look at and listen to a reel you have already fetched: read the on-screen text and describe "
    "what the frames show, and transcribe any speech. Requires fetch_reels first — a "
    "shortcode with no fetched media returns status not_fetched. args: { shortcodes: string[], "
    "want: ('visual' | 'speech')[] }. 'visual' returns both the on-screen text and a description "
    "of the place in one pass; 'speech' transcribes the audio and costs noticeably more time per "
    "reel, so ask for it only when the visual pass and the caption left you unsure. Returns "
    "{ items: [{ shortcode, status, detail, overlay_text, scene, frames_read, "
    "sampled_over_seconds, transcript, speech, speech_seconds, language, notes }] }. overlay_text "
    "is the deduplicated on-screen text in reading order; scene is prose describing the terrain, "
    "architecture, food or interior visible; transcript is spoken words; notes records what was "
    "bounded or skipped and is worth reading before you conclude anything. Weight the evidence in "
    "this order: an @mention of the venue, then the caption, then overlay_text, then scene, and "
    "the transcript last — the transcriber mangles local proper nouns, rendering 'Warung Mak Cik' "
    "as 'Warung Maksik' and 'Jalan Telawi' as 'Jalan Tilikai', so never take the spelling of a "
    "name from it. speech is present, none (no speech in the audio — common and not an error, "
    "many reels carry only music), skipped (you did not ask), unavailable (no audio track) or "
    "failed (notes says why). status is ok, partial (some of what you asked for is missing; notes "
    "says why), timeout (this reel exceeded the call's time budget — call again with just its "
    "shortcode, nothing already done is lost), not_fetched, or error. This tool reports only what "
    "it observed: it never names a place, scores a match or looks anything up, because that "
    "judgement is yours to make from all the evidence together. Fewer shortcodes per call finish "
    "sooner, and a long call returns the reels it managed rather than failing outright."
)
