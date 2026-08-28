import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("the public landing page links to the containment slice", async () => {
  const source = await readFile(new URL("../index.html", import.meta.url), "utf8");
  assert.match(source, /href="\/app"/);
  assert.match(source, /ephemeral preview evidence/);
  assert.match(source, /LEDGAT<span>o<\/span>/);
  assert.doesNotMatch(source, /LEDGAT<span>O<\/span>/);
  assert.match(source, /\.hero h1\{font-family:var\(--display\)\}/);
});

test("the app route calls the atomic preview API", async () => {
  const document = await readFile(new URL("../app/index.html", import.meta.url), "utf8");
  const source = await readFile(new URL("../app/main.js", import.meta.url), "utf8");
  assert.match(document, /LEDGAT<span>o<\/span>/);
  assert.doesNotMatch(document, /LEDGAT<span>O<\/span>/);
  assert.match(source, /\/api\/v1\/demo\/run/);
});

test("Vercel routing preserves the app and scopes rewrites to API only", async () => {
  const config = JSON.parse(await readFile(new URL("../vercel.json", import.meta.url), "utf8"));
  assert.deepEqual(config.rewrites, [
    { source: "/app", destination: "/app/index.html" },
    { source: "/api/:path*", destination: "/api/index" },
  ]);
  assert.equal(config.redirects, undefined);
});
