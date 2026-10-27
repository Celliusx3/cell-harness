# 03 Save from this Mac

**Status:** done

**What to build.**

- `PUT /api/credentials` takes a patch of credential paths: a new full value, or `null` to remove one.
- It refuses a path that is not a listed credential, one set by the environment, and the masked preview.
- The route refuses a request that carries any `x-forwarded-*` or `forwarded` header.
- It refuses a peer that is not loopback, and an `Origin` that is not a loopback origin.
- It merges the patch into `config.local.json`, keeps every other value, and checks the result against `Settings`.
- A refused value returns 422 with the field and the harness's message, without the input. Nothing is written.
- If any reply is running and `confirm` is not set, it returns 409. `RunService` gains `is_busy()`.
- The file is written in one rename, with mode 600, by a pure merge in `harness/config/` and a small writer.
- The harness answers CORS for loopback origins on this route only.
- `GET /api/credentials` also tells the page the harness's own address, from `request.scope["server"]`.
- The page tries that address. If it answers, each row gets a password field, and a set key gets Remove. Save asks first when the harness is busy.
- Otherwise the page stays read-only with "Change credentials on the Mac that runs the harness."

**Checks.**

- Route tests cover each refusal: a forwarded header, a foreign origin, an unknown path and a masked preview.
- They also cover a key set by the environment, a bad value with no input echoed, and a busy harness without confirm.
- A route test saves a patch and asserts the file keeps its other values and has mode 600.
- By hand: a save through `127.0.0.1:4897/api/credentials` is refused, and the same save from the page succeeds.

**Blocked by.** 02
