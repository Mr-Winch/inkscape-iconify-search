const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("vectorCraft", Object.freeze({
  status: () => ipcRenderer.invoke("vectorcraft:status"),
  launch: () => ipcRenderer.invoke("vectorcraft:launch"),
  place: (assets) => ipcRenderer.invoke("vectorcraft:place", assets),
  getTheme: () => ipcRenderer.invoke("vectorcraft:theme")
}));
