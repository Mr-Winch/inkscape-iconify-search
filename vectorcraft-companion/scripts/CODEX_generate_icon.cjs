const path = require("node:path");
const sharp = require("sharp");

(async () => {
  const source = path.join(__dirname, "..", "assets", "iconify_search_icon.svg");
  const target = path.join(__dirname, "..", "assets", "iconify_search_icon.png");
  await sharp(source, { density: 320 }).resize(512, 512).png().toFile(target);
})().catch((error) => { console.error(error); process.exitCode = 1; });
