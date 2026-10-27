import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";

test("the compiled preload loads only electron, the one module a sandboxed preload may load", () => {
  const compiled = readFileSync(path.join(__dirname, "setupPreload.js"), "utf8");
  const loaded = [...compiled.matchAll(/require\("([^"]+)"\)/g)].map((match) => match[1]);

  assert.deepEqual(loaded, ["electron"]);
});
