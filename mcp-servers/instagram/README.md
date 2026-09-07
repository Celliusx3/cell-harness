# instagram

An MCP server that turns a shared Instagram reel into **text observations**.

It reports what a reel says and shows. It never names a place, scores a match or
looks anything up — that inference belongs to the harness model, which has the
caption, the mentions, the on-screen text and the scene in front of it at once.
That boundary is what lets this compose with a Places server instead of arguing
with it.

Two tools:

| Tool | Costs | Returns |
|---|---|---|
| `fetch_reels(urls)` | network only, **zero provider tokens** | caption, author, hashtags, mentions, tagged_users, posted_at, media kind |
| `read_reels(shortcodes, want)` | a vision call, plus an ASR call if you ask | on-screen text, scene description, transcript |

They are separate because **the caption often names the place on its own**, and
then the video never needs decoding. Measured on two real reels: one carried
`📍 @natalinaitalian`, the other `📍 Rajgad Fort`. Fusing the tools would remove
the model's ability to *not* pay for vision.

## Requirements

- **Python ≥ 3.13**, and `uv`.
- **ffmpeg on PATH.** Unlike `instaloader`, which is a pinned pip dependency,
  ffmpeg cannot be one — so it is checked at startup and its absence is a refusal
  to start rather than a failure on first use.
- A provider key for the vision and transcription calls. Any
  OpenAI-compatible endpoint that accepts `image_url` content blocks and has a
  Whisper-shaped `/audio/transcriptions`.

## Configuration

Environment only, validated before the server binds. An unusable value **refuses
to start**, which means the harness logs it and the tools are simply absent from
`list_functions` — so the model learns it has no Instagram capability instead of
retrying a tool that cannot work.

Two prefixes, because there are two kinds of setting. **`AI_*`** configures the
model provider — another server would need these identically. **`INSTAGRAM_*`**
configures this server and is meaningless outside it.

Note that **Instagram itself needs no credential**: `AI_PROVIDER_API_KEY` is for
the vision and transcription calls this server makes, not for Instagram. It is
usually the same key as the harness's own `llm.api_key`.

| Variable | Default | Notes |
|---|---|---|
| `AI_PROVIDER_BASE_URL` | — | required; any OpenAI-compatible endpoint |
| `AI_PROVIDER_API_KEY` | — | required; for vision + ASR, **not** for Instagram |
| `AI_VISION_MODEL` | `glm-5.3-flash` | must accept `image_url` blocks |
| `AI_ASR_MODEL` | `ilmu-asr-v4.2` | Whisper-shaped `/audio/transcriptions` |
| `INSTAGRAM_MEDIA_BACKEND` | `instaloader` | or `fixture` |
| `INSTAGRAM_FIXTURE_ROOT` | — | required when backend is `fixture` |
| `INSTAGRAM_WORK_DIR` | `~/.harness/instagram` | media root, `0700`, swept at startup |
| `INSTAGRAM_FFMPEG` | `ffmpeg` | |
| `INSTAGRAM_MAX_FRAMES` | `8` | spread across the whole video, not the first N seconds |
| `INSTAGRAM_MAX_SPEECH_SECONDS` | `180` | bounds one long video's cost |
| `INSTAGRAM_FETCH_CONCURRENCY` | `4` | |
| `INSTAGRAM_READ_CONCURRENCY` | `3` | |
| `INSTAGRAM_CALL_BUDGET_SECONDS` | `45` | soft, under the harness's hard 60s |
| `INSTAGRAM_REQUEST_TIMEOUT_SECONDS` | `120` | |

## How this reaches Instagram

**Anonymously, with no account and no cookies** — verified against a live public
reel while this was designed.

Instagram serves a logged-out visitor a ~620 KB JavaScript shell with **zero**
meta tags: no caption, no thumbnail, not even `og:title`, and the *same* shell
for a post that does not exist. The meta tags every scraper used to read are
injected client-side. So a raw-HTTP client has to use the private GraphQL
endpoint, and `instaloader` does — bootstrapping its own CSRF token for anonymous
use. Alternatives, checked the same afternoon:

| | Anonymous single post |
|---|---|
| **instaloader** 4.15.3 | ✅ verified live |
| `yt-dlp` 2026.06.09 | ❌ fails at metadata, webpage *and* embed |
| `gallery-dl` 1.32.11 | ❌ needs cookies, and its profile path is broken even with them |
| `instagrapi` | ❌ login required; upstream benchmarks its public path at 0/4 |

`instaloader` is therefore **pinned, not floated**. Instagram rotates the
`doc_id` it queries, and a float turns "Instagram changed" into "the capability
broke on a machine nobody touched".

### Two known failure signatures

**An immediate, empty-bodied 429.** Instagram answers HTTP/1.1 web-API requests
with `429` while the identical HTTP/2 request returns 200 — a partial rollout,
independent of account and IP, unfixed upstream as of 2026-09. `instaloader`
speaks HTTP/1.1 via `requests`, so on an affected network *nothing* works and it
looks exactly like rate limiting. It is not: **waiting does not help.** The
server says so explicitly in `rate_limited.detail`, because the fix is an
HTTP/2 transport, not patience.

**`doc_id` rotation.** Presents as `unavailable` on every reel at once. The fix
is a version bump; check upstream releases before assuming a bug here.

### What is not available anonymously

Instagram's **location sticker** is login-gated by explicit upstream design, so
there is deliberately no field for it — a field that is always empty is a fact
the model would reason from wrongly. `tagged_users` carries the corroborating
signal instead. **Profile enumeration** is also unavailable (and broken in
yt-dlp and gallery-dl too), so "process my saved collection" is out of scope;
per-reel sharing is the supported path.

### Terms

Anonymous access removes *account* risk — there is no account to be challenged
or banned, and the worst case is an IP throttle. It does **not** make this
sanctioned: Instagram's ToU was amended effective 2025-01-01 to cover automated
collection *"regardless of whether… logged in"*, and `robots.txt` ends
`Disallow: /` for anything off its 23-agent allowlist. Low account risk,
non-zero terms risk. Sized for personal use at a couple of reels a day.

## Reading a reel

Frames are sampled **evenly across the whole duration** (`fps=n/duration`), not
at a fixed interval — a 10-minute video would otherwise return twelve frames of
its first 24 seconds while `sampled_over_seconds` claimed the whole thing.
Duration is captured at fetch and written beside the media, because fetch and
read are separate MCP calls.

Audio is **extracted before transcribing**, even though the endpoint accepts an
mp4 directly: measured on a real 70-second reel, the mp4 is 15 MB and the same
audio as 16 kHz mono mp3 is 276 KB. A 58× smaller upload for an identical
transcript.

### Evidence is not equally trustworthy

Weight it: **`mentions` > `caption` > `overlay_text` > `scene` > `transcript`.**
Transcription mangles exactly the words that identify a place — observed:
"Warung Mak Cik" → "Warung Maksik", "Jalan Telawi" → "Jalan Tilikai". The tool
description says so, with those examples, because a general "transcripts may be
inaccurate" did not stop the model spelling a venue's name from audio.

### Music is not silence

ASR on a music-only reel returns **confident nonsense**, not an empty string —
observed: `"bira bira bira bira"` across 16 seconds. So `speech: "none"` is
asserted by detecting that shape, and the text is **withheld**. Passing it
through would hand the model a transcript contradicting a correct caption with no
way to tell which to believe.

## Tests

```sh
uv run pytest              # hermetic: no network, no Instagram, no provider
uv run ruff check . && uv run ruff format --check .
```

Faked at three seams, never by monkeypatching a module: the `MediaSource`
Protocol (checked-in fixtures under `tests/fixtures/media/`, including ones that
raise on purpose), the provider's `httpx.AsyncClient` (`MockTransport`), and
`CommandRunner` for ffmpeg argv.

`tests/unit/test_descriptions.py` is the unusual one and it earns its place: it
asserts every description survives being collapsed to one line, contains no
`*/`, and **names every field of its return model** — the mechanical half of
"prompt text is code", catching the two failure modes the harness's TypeScript
printer creates.

The live check, opt-in and never in CI:

```sh
INSTAGRAM_LIVE=1 AI_PROVIDER_API_KEY=... uv run pytest tests/integration/test_live.py -s

# ...or point it at a specific reel you want to check
INSTAGRAM_LIVE_REEL="https://www.instagram.com/reel/<code>/" \
INSTAGRAM_LIVE=1 AI_PROVIDER_API_KEY=... uv run pytest tests/integration/test_live.py -s
```

It prints the caption, mentions, on-screen text, scene and transcript, because
the value of this check is as much in reading the output as in the assertions.

The boundary that draws: *we test that we handle every shape instaloader and the
provider can hand us; we do not test that they still hand us those shapes.* Run
it before trusting a version bump.
