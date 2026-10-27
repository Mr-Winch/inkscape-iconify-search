export const DEFAULT_ENDPOINTS = [
  "https://api.iconify.design",
  "https://api.simplesvg.com",
  "https://api.unisvg.com"
];

const ICON_NAME = /^[a-z0-9]+(?:-[a-z0-9]+)*:[a-z0-9]+(?:-[a-z0-9]+)*$/;

export function parseIconName(fullName) {
  if (!ICON_NAME.test(fullName)) throw new Error(`Invalid Iconify name: ${fullName}`);
  const separator = fullName.indexOf(":");
  return { prefix: fullName.slice(0, separator), name: fullName.slice(separator + 1) };
}

export function buildIconUrl(fullName, options = {}, endpoint = DEFAULT_ENDPOINTS[0]) {
  const { prefix, name } = parseIconName(fullName);
  const url = new URL(`${endpoint.replace(/\/$/, "")}/${prefix}/${name}.svg`);
  if (options.color) url.searchParams.set("color", options.color);
  if (options.width) url.searchParams.set("width", String(options.width));
  if (options.height) url.searchParams.set("height", String(options.height));
  return url.toString();
}

async function fetchWithFailover(path, params, endpoints, signal) {
  const errors = [];
  for (const endpoint of endpoints) {
    const url = new URL(endpoint.replace(/\/$/, "") + path);
    for (const [key, value] of Object.entries(params || {})) {
      if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, String(value));
    }
    try {
      const response = await fetch(url, {
        headers: { Accept: "application/json,image/svg+xml;q=0.9,*/*;q=0.1" },
        signal
      });
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      return response;
    } catch (error) {
      if (signal?.aborted) throw error;
      errors.push(`${endpoint}: ${error.message}`);
    }
  }
  throw new Error(`Iconify request failed. ${errors.join(" · ")}`);
}

export class IconifyApi {
  constructor({ endpoints = DEFAULT_ENDPOINTS } = {}) {
    this.endpoints = [...endpoints];
  }

  async collections({ signal } = {}) {
    const response = await fetchWithFailover("/collections", {}, this.endpoints, signal);
    const payload = await response.json();
    return Object.entries(payload)
      .map(([prefix, item]) => ({ prefix, name: item.name || prefix, total: Number(item.total) || 0, ...item }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }

  async search(query, { prefix = "", prefixes = [], category = "", similar = true, style = "", limit = 120, start = 0, signal } = {}) {
    const cleanQuery = String(query).trim();
    if (cleanQuery.length < 2) return { icons: [], total: 0, collections: {} };
    const response = await fetchWithFailover("/search", {
      query: cleanQuery,
      prefix,
      prefixes: Array.isArray(prefixes) ? prefixes.join(",") : prefixes,
      category,
      similar: similar ? "" : "false",
      style,
      limit: Math.max(32, Math.min(999, Number(limit) || 120)),
      start: Math.max(0, Number(start) || 0)
    }, this.endpoints, signal);
    return response.json();
  }

  async collection(prefix, { info = true, chars = false, signal } = {}) {
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(prefix)) throw new Error(`Invalid Iconify prefix: ${prefix}`);
    const response = await fetchWithFailover("/collection", {
      prefix,
      info: info ? "true" : "",
      chars: chars ? "true" : ""
    }, this.endpoints, signal);
    const payload = await response.json();
    const visible = new Set(payload.uncategorized || []);
    for (const names of Object.values(payload.categories || {})) {
      for (const name of names) visible.add(name);
    }
    return {
      ...payload,
      icons: [...visible],
      aliases: Object.keys(payload.aliases || {}),
      hidden: payload.hidden || [],
      categories: payload.categories || {},
      chars: payload.chars || {}
    };
  }

  async svg(fullName, { color = "", signal } = {}) {
    const { prefix, name } = parseIconName(fullName);
    const response = await fetchWithFailover(`/${prefix}/${name}.svg`, { color }, this.endpoints, signal);
    return response.text();
  }
}

export function sanitizeSvg(svgText) {
  const documentNode = new DOMParser().parseFromString(svgText, "image/svg+xml");
  if (documentNode.querySelector("parsererror")) throw new Error("Iconify returned invalid SVG.");
  for (const node of [...documentNode.querySelectorAll("script,foreignObject,iframe,object,embed")]) node.remove();
  for (const element of documentNode.querySelectorAll("*")) {
    for (const attribute of [...element.attributes]) {
      const name = attribute.name.toLowerCase();
      const value = attribute.value.trim().toLowerCase();
      if (name.startsWith("on") || ((name === "href" || name.endsWith(":href")) && /^(https?:|javascript:|data:text\/html)/.test(value))) {
        element.removeAttribute(attribute.name);
      }
    }
  }
  const svg = documentNode.documentElement;
  if (svg.localName !== "svg") throw new Error("Iconify did not return an SVG element.");
  return new XMLSerializer().serializeToString(svg);
}

export function svgDataUrl(svgText) {
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svgText)}`;
}

export async function svgToPngBlob(svgText, pixels = 512) {
  const safeSvg = sanitizeSvg(svgText);
  const source = URL.createObjectURL(new Blob([safeSvg], { type: "image/svg+xml" }));
  try {
    const image = new Image();
    image.decoding = "async";
    image.src = source;
    await image.decode();
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = Math.max(16, Math.min(4096, Number(pixels) || 512));
    const context = canvas.getContext("2d");
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    return await new Promise((resolve, reject) => canvas.toBlob(
      (blob) => blob ? resolve(blob) : reject(new Error("PNG conversion failed.")),
      "image/png"
    ));
  } finally {
    URL.revokeObjectURL(source);
  }
}
