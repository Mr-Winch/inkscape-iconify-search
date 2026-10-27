const { app, BrowserWindow, dialog, ipcMain, nativeTheme, shell } = require("electron");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const net = require("node:net");
const path = require("node:path");
const { composeSvg } = require("./CODEX_vectorcraft_protocol.cjs");

const CONTROL_HOST = "127.0.0.1";
const CONTROL_PORT = 7979;
let nextRequestId = 1;
let mainWindow;

function settingsPath() {
  return path.join(app.getPath("userData"), "vectorcraft-connection.json");
}

function readSettings() {
  try { return JSON.parse(fs.readFileSync(settingsPath(), "utf8")); }
  catch { return {}; }
}

function writeSettings(settings) {
  fs.mkdirSync(path.dirname(settingsPath()), { recursive: true });
  fs.writeFileSync(settingsPath(), JSON.stringify(settings, null, 2), "utf8");
}

function vectorCraftCandidates() {
  const configured = readSettings().executable;
  const programFiles = process.env.ProgramFiles || "C:\\Program Files";
  const programFilesX86 = process.env["ProgramFiles(x86)"] || "C:\\Program Files (x86)";
  const local = process.env.LOCALAPPDATA || "";
  return [
    configured,
    path.join(programFiles, "VectorCraft", "vectorcraft.exe"),
    path.join(programFilesX86, "VectorCraft", "vectorcraft.exe"),
    local ? path.join(local, "Programs", "VectorCraft", "vectorcraft.exe") : ""
  ].filter(Boolean);
}

function locateVectorCraft() {
  return vectorCraftCandidates().find((candidate) => fs.existsSync(candidate)) || "";
}

function controlRequest(method, params = {}, timeoutMs = 65000) {
  return new Promise((resolve, reject) => {
    const socket = net.createConnection({ host: CONTROL_HOST, port: CONTROL_PORT });
    let buffer = "";
    let settled = false;
    const fail = (error) => {
      if (settled) return;
      settled = true;
      socket.destroy();
      reject(error instanceof Error ? error : new Error(String(error)));
    };
    socket.setEncoding("utf8");
    socket.setTimeout(timeoutMs, () => fail(new Error("VectorCraft did not answer in time.")));
    socket.once("error", fail);
    socket.on("data", (chunk) => {
      buffer += chunk;
      const newline = buffer.indexOf("\n");
      if (newline < 0) return;
      try {
        const response = JSON.parse(buffer.slice(0, newline));
        if (!response.ok) throw new Error(response.error || "VectorCraft rejected the request.");
        if (!settled) {
          settled = true;
          socket.end();
          resolve(response.result);
        }
      } catch (error) { fail(error); }
    });
    socket.once("connect", () => {
      const request = { id: nextRequestId++, method, params };
      socket.write(`${JSON.stringify(request)}\n`, "utf8");
    });
  });
}

async function connectionStatus() {
  const executable = locateVectorCraft();
  try {
    await controlRequest("ui.inspect", {}, 1800);
    return { connected: true, installed: Boolean(executable), executable, host: CONTROL_HOST, port: CONTROL_PORT };
  } catch (error) {
    return { connected: false, installed: Boolean(executable), executable, host: CONTROL_HOST, port: CONTROL_PORT, error: error.code === "ECONNREFUSED" ? "VectorCraft is not listening on the control port." : error.message };
  }
}

async function chooseVectorCraft() {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: "Locate VectorCraft",
    properties: ["openFile"],
    filters: [{ name: "VectorCraft", extensions: ["exe"] }]
  });
  if (result.canceled || !result.filePaths[0]) return "";
  const executable = result.filePaths[0];
  if (path.basename(executable).toLowerCase() !== "vectorcraft.exe") throw new Error("Choose vectorcraft.exe.");
  writeSettings({ ...readSettings(), executable });
  return executable;
}

async function launchVectorCraft() {
  const already = await connectionStatus();
  if (already.connected) return already;
  const executable = locateVectorCraft() || await chooseVectorCraft();
  if (!executable) return { ...already, error: "VectorCraft was not selected." };
  const child = spawn(executable, [`--control=${CONTROL_PORT}`], {
    detached: true,
    stdio: "ignore",
    windowsHide: false,
    cwd: path.dirname(executable)
  });
  child.unref();
  for (let attempt = 0; attempt < 60; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 250));
    const status = await connectionStatus();
    if (status.connected) return status;
  }
  return {
    connected: false,
    installed: true,
    executable,
    host: CONTROL_HOST,
    port: CONTROL_PORT,
    error: "VectorCraft did not enable the control port. If it was already open, close every VectorCraft window and press Open VectorCraft again."
  };
}

async function placeAssets(assets) {
  const composition = composeSvg(assets);
  const dataBase64 = Buffer.from(composition.svg, "utf8").toString("base64");
  const result = await controlRequest("engine.execute", {
    command: "file.place",
    params: { name: composition.name, dataBase64 }
  });
  return { count: assets.length, result };
}

function themeFromInspection(inspection) {
  const candidates = [inspection?.brightness, inspection?.ui?.brightness, inspection?.theme, inspection?.ui?.theme];
  for (const value of candidates) {
    if (typeof value === "string") {
      if (/dark/i.test(value)) return "dark";
      if (/light/i.test(value)) return "light";
    }
    if (typeof value === "number") return value < .55 ? "dark" : "light";
  }
  return nativeTheme.shouldUseDarkColors ? "dark" : "light";
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1180,
    height: 820,
    minWidth: 820,
    minHeight: 620,
    show: false,
    backgroundColor: nativeTheme.shouldUseDarkColors ? "#202020" : "#f3f3f3",
    icon: path.join(__dirname, "assets", "iconify_search_icon.png"),
    title: "Iconify Search for VectorCraft",
    webPreferences: {
      preload: path.join(__dirname, "CODEX_preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });
  mainWindow.removeMenu();
  mainWindow.loadFile(path.join(__dirname, "index.html"));
  mainWindow.once("ready-to-show", () => mainWindow.show());
  mainWindow.webContents.setWindowOpenHandler(({ url }) => { if (/^https:\/\//i.test(url)) shell.openExternal(url); return { action: "deny" }; });
  mainWindow.webContents.on("will-navigate", (event, url) => { if (url !== mainWindow.webContents.getURL()) event.preventDefault(); });
}

ipcMain.handle("vectorcraft:status", connectionStatus);
ipcMain.handle("vectorcraft:launch", launchVectorCraft);
ipcMain.handle("vectorcraft:place", (_event, assets) => placeAssets(assets));
ipcMain.handle("vectorcraft:theme", async () => {
  try { return { theme: themeFromInspection(await controlRequest("ui.inspect", {}, 2500)), source: "vectorcraft" }; }
  catch { return { theme: nativeTheme.shouldUseDarkColors ? "dark" : "light", source: "windows" }; }
});

if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on("second-instance", () => { if (mainWindow) { if (mainWindow.isMinimized()) mainWindow.restore(); mainWindow.focus(); } });
  app.whenReady().then(createWindow);
  app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });
  app.on("activate", () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
}
