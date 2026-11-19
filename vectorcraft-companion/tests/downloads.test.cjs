const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");
const { assetFilename, ensureAssetExtension, saveAssetFiles } = require("../CODEX_downloads.cjs");

test("creates readable, Windows-safe icon filenames", () => {
  assert.equal(assetFilename({ name: "lucide:camera", format: "svg" }), "lucide-camera.svg");
  assert.equal(assetFilename({ name: "bad/<name>", format: "png" }), "bad-name.png");
});

test("normalizes a chosen filename to the selected format", () => {
  assert.equal(ensureAssetExtension("C:\\Icons\\camera.png", "svg"), "C:\\Icons\\camera.svg");
});

test("downloads multiple icons without overwriting existing files", async () => {
  const directory = await fs.promises.mkdtemp(path.join(os.tmpdir(), "CODEX_iconify_downloads_"));
  try {
    await fs.promises.writeFile(path.join(directory, "lucide-camera.svg"), "existing");
    const paths = await saveAssetFiles(directory, [
      { name: "lucide:camera", format: "svg", data: Buffer.from("<svg/>") },
      { name: "tabler:home", format: "svg", data: Buffer.from("<svg/>") }
    ]);
    assert.equal(path.basename(paths[0]), "lucide-camera-2.svg");
    assert.equal(path.basename(paths[1]), "tabler-home.svg");
    assert.equal(await fs.promises.readFile(paths[0], "utf8"), "<svg/>");
  } finally {
    await fs.promises.rm(directory, { recursive: true, force: true });
  }
});
