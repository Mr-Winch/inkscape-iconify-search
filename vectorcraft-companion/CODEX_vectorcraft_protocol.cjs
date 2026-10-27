const MAX_ASSETS = 120;

function escapeXmlAttribute(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" })[character]);
}

function unpackSvg(svgText) {
  if (typeof svgText !== "string" || svgText.length > 2_000_000) throw new Error("An icon contains invalid SVG data.");
  if (/<(?:script|foreignObject|iframe|object|embed)\b/i.test(svgText)) throw new Error("Unsafe SVG content was refused.");
  const opening = svgText.match(/<svg\b([^>]*)>/i);
  const closing = svgText.toLowerCase().lastIndexOf("</svg>");
  if (!opening || closing < 0) throw new Error("An icon is missing its SVG root.");
  const attributes = opening[1];
  const viewBoxMatch = attributes.match(/\bviewBox\s*=\s*["']([^"']+)["']/i);
  const widthMatch = attributes.match(/\bwidth\s*=\s*["']([\d.]+)(?:px)?["']/i);
  const heightMatch = attributes.match(/\bheight\s*=\s*["']([\d.]+)(?:px)?["']/i);
  const width = Number(widthMatch?.[1]) || 24;
  const height = Number(heightMatch?.[1]) || 24;
  const viewBox = viewBoxMatch?.[1] || `0 0 ${width} ${height}`;
  const contentStart = opening.index + opening[0].length;
  return { viewBox, content: svgText.slice(contentStart, closing) };
}

function composeSvg(assets) {
  if (!Array.isArray(assets) || !assets.length || assets.length > MAX_ASSETS) throw new Error(`Select between 1 and ${MAX_ASSETS} icons.`);
  const normalized = assets.map((asset) => ({
    name: String(asset?.name || "icon").slice(0, 120),
    size: Math.max(8, Math.min(2048, Number(asset?.size) || 64)),
    ...unpackSvg(asset?.svg)
  }));
  if (normalized.length === 1) {
    const icon = normalized[0];
    return {
      name: `${icon.name.replace(/[^a-z0-9_-]+/gi, "-")}.svg`,
      svg: `<svg xmlns="http://www.w3.org/2000/svg" width="${icon.size}" height="${icon.size}" viewBox="${escapeXmlAttribute(icon.viewBox)}">${icon.content}</svg>`
    };
  }
  const cell = Math.max(...normalized.map((icon) => icon.size));
  const gap = Math.max(8, Math.round(cell * .25));
  const columns = Math.ceil(Math.sqrt(normalized.length));
  const rows = Math.ceil(normalized.length / columns);
  const width = columns * cell + (columns - 1) * gap;
  const height = rows * cell + (rows - 1) * gap;
  const content = normalized.map((icon, index) => {
    const x = (index % columns) * (cell + gap) + (cell - icon.size) / 2;
    const y = Math.floor(index / columns) * (cell + gap) + (cell - icon.size) / 2;
    return `<svg x="${x}" y="${y}" width="${icon.size}" height="${icon.size}" viewBox="${escapeXmlAttribute(icon.viewBox)}" data-icon-name="${escapeXmlAttribute(icon.name)}">${icon.content}</svg>`;
  }).join("");
  return { name: "iconify-selection.svg", svg: `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">${content}</svg>` };
}

module.exports = { MAX_ASSETS, composeSvg, unpackSvg };
