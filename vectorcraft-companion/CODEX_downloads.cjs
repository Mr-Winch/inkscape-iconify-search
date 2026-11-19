const fs = require("node:fs");
const path = require("node:path");

const FORMATS = new Set(["svg", "png"]);
const WINDOWS_RESERVED = /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i;

function normalizeFormat(format) {
  const value = String(format || "").toLowerCase();
  if (!FORMATS.has(value)) throw new Error(`Unsupported icon format: ${format}`);
  return value;
}

function safeStem(iconName) {
  const stem = String(iconName || "icon")
    .replace(/:/g, "-")
    .replace(/[<>:"/\\|?*\u0000-\u001f]/g, "-")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^[. -]+|[. -]+$/g, "")
    .slice(0, 120) || "icon";
  return WINDOWS_RESERVED.test(stem) ? `icon-${stem}` : stem;
}

function assetFilename(asset) {
  const format = normalizeFormat(asset?.format);
  return `${safeStem(asset?.name)}.${format}`;
}

function ensureAssetExtension(filePath, format) {
  const cleanFormat = normalizeFormat(format);
  const extension = `.${cleanFormat}`;
  return path.extname(filePath).toLowerCase() === extension
    ? filePath
    : path.join(path.dirname(filePath), `${path.basename(filePath, path.extname(filePath))}${extension}`);
}

function assetBuffer(asset) {
  const data = asset?.data;
  if (Buffer.isBuffer(data)) return data;
  if (data instanceof ArrayBuffer) return Buffer.from(data);
  if (ArrayBuffer.isView(data)) return Buffer.from(data.buffer, data.byteOffset, data.byteLength);
  throw new Error(`No downloadable data was provided for ${asset?.name || "icon"}.`);
}

async function writeUnique(directory, filename, bytes) {
  const parsed = path.parse(filename);
  for (let index = 1; index <= 9999; index += 1) {
    const suffix = index === 1 ? "" : `-${index}`;
    const candidate = path.join(directory, `${parsed.name}${suffix}${parsed.ext}`);
    try {
      await fs.promises.writeFile(candidate, bytes, { flag: "wx" });
      return candidate;
    } catch (error) {
      if (error.code !== "EEXIST") throw error;
    }
  }
  throw new Error(`Could not find an available filename for ${filename}.`);
}

async function saveAssetFile(filePath, asset) {
  const target = ensureAssetExtension(filePath, asset.format);
  await fs.promises.writeFile(target, assetBuffer(asset));
  return target;
}

async function saveAssetFiles(directory, assets) {
  if (!Array.isArray(assets) || !assets.length) throw new Error("No icons were selected for download.");
  const saved = [];
  for (const asset of assets) saved.push(await writeUnique(directory, assetFilename(asset), assetBuffer(asset)));
  return saved;
}

module.exports = { assetBuffer, assetFilename, ensureAssetExtension, safeStem, saveAssetFile, saveAssetFiles };
