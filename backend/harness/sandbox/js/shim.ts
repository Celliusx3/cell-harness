// The program that runs inside the sandbox. Shipped as a `data:` URL, so it is
// never on disk and the child needs no read permission.
//
// Protocol is newline-delimited JSON both ways over stdio:
//   in   {"kind":"run","code":"…","names":["yt__get_subtitles", …]}
//   out  {"kind":"call","id":1,"name":"…","args":{…}}
//   in   {"kind":"result","id":1,"ok":true,"value":…}
//   out  {"kind":"done","result":…,"logs":[…]}  |  {"kind":"failed","message":"…"}

type Reply = { id: number; ok: boolean; value?: unknown; error?: string };

const encoder = new TextEncoder();

async function send(frame: Record<string, unknown>): Promise<void> {
  await Deno.stdout.write(encoder.encode(JSON.stringify(frame) + "\n"));
}

/** stdin as a stream of newline-delimited frames. */
async function* frames(): AsyncGenerator<Record<string, unknown>> {
  const decoder = new TextDecoder();
  let buffer = "";
  for await (const chunk of Deno.stdin.readable) {
    buffer += decoder.decode(chunk, { stream: true });
    let cut: number;
    while ((cut = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, cut).trim();
      buffer = buffer.slice(cut + 1);
      if (line) yield JSON.parse(line);
    }
  }
}

const input = frames();

const first = await input.next();
if (first.done) Deno.exit(0);
const run = first.value as { code: string; names: string[] };

// Pumped in the background so a script using Promise.all can have several calls
// outstanding at once.
const pending = new Map<number, (reply: Reply) => void>();
(async () => {
  for await (const frame of input) {
    if (frame.kind === "result") {
      const reply = frame as unknown as Reply;
      pending.get(reply.id)?.(reply);
      pending.delete(reply.id);
    }
  }
})();

let sequence = 0;

/** One tool, as an async function the script can call by its exact name. */
function bridge(name: string) {
  return async (args: unknown = {}) => {
    const id = ++sequence;
    const reply = new Promise<Reply>((resolve) => pending.set(id, resolve));
    await send({ kind: "call", id, name, args });
    const settled = await reply;
    // Our outcomes are values; TypeScript callers expect a throw.
    if (!settled.ok) throw new Error(settled.error ?? `${name} failed`);
    return settled.value;
  };
}

for (const name of run.names) {
  (globalThis as Record<string, unknown>)[name] = bridge(name);
}

// Captured, not written: stdout is the protocol, and only what the script
// prints or returns comes back.
const logs: string[] = [];
const record = (...args: unknown[]) => {
  logs.push(args.map((a) => (typeof a === "string" ? a : JSON.stringify(a))).join(" "));
};
console.log = record;
console.info = record;
console.warn = record;
console.error = record;

try {
  // A function *body*, so `return` works; imported as a data: module, which is
  // what strips its type annotations.
  const source = `export default async function () {\n${run.code}\n}`;
  const module = await import("data:text/typescript," + encodeURIComponent(source));
  const result = await module.default();
  await send({ kind: "done", result: result ?? null, logs });
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  await send({ kind: "failed", message, logs });
}

Deno.exit(0);
