const assert = require("node:assert/strict");
const test = require("node:test");
const { composeSvg, unpackSvg } = require("../CODEX_vectorcraft_protocol.cjs");

test("extracts SVG content and viewBox", () => {
  const result = unpackSvg('<svg viewBox="0 0 16 20"><path d="M0 0"/></svg>');
  assert.equal(result.viewBox, "0 0 16 20");
  assert.match(result.content, /<path/);
});

test("prepares one sized SVG for VectorCraft", () => {
  const result = composeSvg([{ name: "tabler:home", size: 72, svg: '<svg viewBox="0 0 24 24"><path d="M0 0"/></svg>' }]);
  assert.equal(result.name, "tabler-home.svg");
  assert.match(result.svg, /width="72" height="72"/);
  assert.match(result.svg, /viewBox="0 0 24 24"/);
});

test("arranges multiple icons without overlapping", () => {
  const svg = '<svg viewBox="0 0 24 24"><path d="M0 0"/></svg>';
  const result = composeSvg([
    { name: "a:one", size: 64, svg },
    { name: "a:two", size: 64, svg },
    { name: "a:three", size: 64, svg }
  ]);
  assert.equal(result.name, "iconify-selection.svg");
  assert.match(result.svg, /data-icon-name="a:one"/);
  assert.match(result.svg, /x="80"/);
});

test("refuses active SVG content", () => {
  assert.throws(() => composeSvg([{ name: "bad:icon", svg: '<svg><script>alert(1)</script></svg>' }]), /Unsafe SVG/);
});
