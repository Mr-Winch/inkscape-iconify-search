import test from "node:test";
import assert from "node:assert/strict";
import { buildIconUrl, IconifyApi, parseIconName } from "../src/iconify-api.js";

test("parses Iconify names", () => assert.deepEqual(parseIconName("lucide:camera"), { prefix: "lucide", name: "camera" }));
test("rejects malformed Iconify names", () => assert.throws(() => parseIconName("not an icon")));
test("builds encoded API URLs", () => {
  const url = new URL(buildIconUrl("lucide:camera", { color: "#ff00aa", width: 48 }));
  assert.equal(url.pathname, "/lucide/camera.svg");
  assert.equal(url.searchParams.get("color"), "#ff00aa");
  assert.equal(url.searchParams.get("width"), "48");
});

test("sends advanced Iconify search filters", async () => {
  const originalFetch = globalThis.fetch;
  let requested;
  globalThis.fetch = async (url) => {
    requested = new URL(url);
    return new Response(JSON.stringify({ icons: [], total: 0 }), { status: 200, headers: { "content-type": "application/json" } });
  };
  try {
    await new IconifyApi({ endpoints: ["https://example.test"] }).search("home", {
      prefixes: ["lucide", "tabler"], category: "General", similar: false,
      style: "stroke", limit: 120, start: 8
    });
    assert.equal(requested.pathname, "/search");
    assert.equal(requested.searchParams.get("prefixes"), "lucide,tabler");
    assert.equal(requested.searchParams.get("category"), "General");
    assert.equal(requested.searchParams.get("similar"), "false");
    assert.equal(requested.searchParams.get("style"), "stroke");
    assert.equal(requested.searchParams.get("start"), "8");
  } finally { globalThis.fetch = originalFetch; }
});

test("normalizes collection browsing metadata", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({
    prefix: "demo", uncategorized: ["home"], categories: { Actions: ["home", "close"] },
    aliases: { dismiss: "close" }, hidden: ["old-home"], chars: { e001: "home" }
  }), { status: 200, headers: { "content-type": "application/json" } });
  try {
    const result = await new IconifyApi({ endpoints: ["https://example.test"] }).collection("demo", { chars: true });
    assert.deepEqual(result.icons, ["home", "close"]);
    assert.deepEqual(result.aliases, ["dismiss"]);
    assert.deepEqual(result.hidden, ["old-home"]);
    assert.deepEqual(result.categories.Actions, ["home", "close"]);
  } finally { globalThis.fetch = originalFetch; }
});
