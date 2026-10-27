import "./src/iconify-asset-picker.js";

const picker = document.querySelector("iconify-asset-picker");
const connection = document.querySelector(".connection");
const connectionLabel = document.querySelector("#connection-label");
const connectionDetail = document.querySelector("#connection-detail");
const notice = document.querySelector("#connection-notice");
const noticeTitle = document.querySelector("#notice-title");
const noticeCopy = document.querySelector("#notice-copy");
const connectButton = document.querySelector("#connect-button");
const launchButton = document.querySelector("#launch-button");
const themeButton = document.querySelector("#theme-button");
const toastRegion = document.querySelector("#toast-region");

let manualTheme = localStorage.getItem("iconify-vectorcraft:theme") || "auto";
let lastStatus = { connected: false };

function toast(message, type = "info") {
  const element = document.createElement("div");
  element.className = `toast ${type}`;
  element.textContent = message;
  toastRegion.append(element);
  setTimeout(() => element.remove(), 4200);
}

function applyTheme(theme) {
  const resolved = theme === "dark" || (theme === "auto" && matchMedia("(prefers-color-scheme: dark)").matches) ? "dark" : "light";
  document.documentElement.dataset.theme = resolved;
  picker.setAttribute("theme", resolved);
  themeButton.title = manualTheme === "auto" ? `Following VectorCraft (${resolved})` : `${resolved === "dark" ? "Dark" : "Light"} theme`;
}

async function syncTheme() {
  if (manualTheme !== "auto") return applyTheme(manualTheme);
  try {
    const result = await window.vectorCraft.getTheme();
    applyTheme(result.theme || "auto");
  } catch {
    applyTheme("auto");
  }
}

function showStatus(status) {
  lastStatus = status;
  const connected = Boolean(status.connected);
  connection.dataset.state = connected ? "connected" : status.error ? "error" : "idle";
  connectionLabel.textContent = connected ? "VectorCraft connected" : "VectorCraft not connected";
  connectionDetail.textContent = connected ? `Control port ${status.port}` : status.installed ? `Ready on port ${status.port}` : "VectorCraft was not found";
  connectButton.textContent = connected ? "Check" : "Connect";
  notice.hidden = connected;
  if (!connected) {
    noticeTitle.textContent = status.installed ? "Direct placement needs a connection" : "VectorCraft was not found";
    noticeCopy.textContent = status.installed
      ? "If VectorCraft is already open, close it and reopen it with the button here."
      : "Install VectorCraft, or choose its executable when prompted.";
    launchButton.textContent = status.installed ? "Open VectorCraft" : "Locate VectorCraft";
  }
}

async function refreshStatus({ quiet = false } = {}) {
  try {
    const status = await window.vectorCraft.status();
    showStatus(status);
    if (status.connected) await syncTheme();
    else if (!quiet && status.error) toast(status.error, "error");
    return status;
  } catch (error) {
    showStatus({ connected: false, installed: false, error: error.message });
    if (!quiet) toast(error.message, "error");
    return lastStatus;
  }
}

async function launchVectorCraft() {
  launchButton.disabled = true;
  launchButton.textContent = "Opening…";
  try {
    const result = await window.vectorCraft.launch();
    showStatus(result);
    if (result.connected) {
      toast("VectorCraft is connected. Select icons and press Insert.");
      await syncTheme();
    } else toast(result.error || "VectorCraft opened, but the connection is not ready yet.", "error");
  } catch (error) {
    toast(error.message, "error");
  } finally {
    launchButton.disabled = false;
    launchButton.textContent = lastStatus.installed === false ? "Locate VectorCraft" : "Open VectorCraft";
  }
}

connectButton.addEventListener("click", () => refreshStatus());
launchButton.addEventListener("click", launchVectorCraft);
themeButton.addEventListener("click", () => {
  const current = document.documentElement.dataset.theme;
  manualTheme = current === "dark" ? "light" : "dark";
  localStorage.setItem("iconify-vectorcraft:theme", manualTheme);
  applyTheme(manualTheme);
});

picker.addEventListener("iconify-import", async ({ detail }) => {
  const assets = detail.assets.filter((asset) => asset.format === "svg" && asset.text).map((asset) => ({ name: asset.name, svg: asset.text, size: asset.size }));
  if (!assets.length) {
    toast("VectorCraft placement currently uses SVG. Choose SVG and try again.", "error");
    return;
  }
  const status = lastStatus.connected ? lastStatus : await refreshStatus({ quiet: true });
  if (!status.connected) {
    toast("Connect VectorCraft before inserting icons.", "error");
    notice.hidden = false;
    return;
  }
  try {
    const result = await window.vectorCraft.place(assets);
    toast(result.count === 1 ? "Icon inserted in VectorCraft." : `${result.count} icons inserted as one editable group.`);
  } catch (error) {
    toast(error.message, "error");
    await refreshStatus({ quiet: true });
  }
});

picker.addEventListener("iconify-error", ({ detail }) => toast(detail.error.message, "error"));
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { if (manualTheme === "auto") syncTheme(); });
applyTheme(manualTheme);
refreshStatus({ quiet: true });
setInterval(() => refreshStatus({ quiet: true }), 12000);
