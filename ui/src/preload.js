const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  closeApp:        () => ipcRenderer.send('close-app'),
  toggleFullscreen: () => ipcRenderer.send('toggle-fullscreen'),
})