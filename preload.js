// preload.js
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('sparge', {
  getVersion:         () => ipcRenderer.invoke('app:version'),
  onUpdateAvailable:  (fn) => ipcRenderer.on('update:available',  (_, info) => fn(info)),
  onUpdateDownloaded: (fn) => ipcRenderer.on('update:downloaded', (_, info) => fn(info)),
  installUpdate:      () => ipcRenderer.send('update:install'),
  openDir:            (defaultPath) => ipcRenderer.invoke('dialog:openDir', defaultPath),
});
