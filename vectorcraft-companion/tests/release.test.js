import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const version = "1.0.1";
const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

test("public version is aligned", () => {
  assert.equal(JSON.parse(read("package.json")).version, version);
  assert.match(read("src/iconify-asset-picker.js"), new RegExp(`VERSION = [\"']${version.replaceAll(".", "\\.")}`));
  assert.match(read("README.md"), new RegExp(version.replaceAll(".", "\\.")));
  assert.match(read("CHANGELOG.md"), new RegExp(`## ${version.replaceAll(".", "\\.")}`));
});

test("release package builds an installable Windows application", () => {
  const metadata = JSON.parse(read("package.json"));
  assert.equal(metadata.private, true);
  assert.equal(metadata.main, "CODEX_main.cjs");
  assert.equal(metadata.scripts.dist, "electron-builder --win nsis");
  assert.equal(metadata.build.win.target[0].target, "nsis");
  assert.equal(metadata.build.nsis.createDesktopShortcut, true);
  assert.match(metadata.build.nsis.artifactName, /Setup/);
});
