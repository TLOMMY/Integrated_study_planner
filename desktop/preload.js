/**
 * 只给本地的 offline.html 暴露"更换服务器"接口；服务器上的网页拿不到这些方法。
 */
const { contextBridge, ipcRenderer } = require('electron')

if (location.protocol === 'file:') {
  contextBridge.exposeInMainWorld('desktop', {
    getServer: () => ipcRenderer.invoke('server:get'),
    testServer: (url) => ipcRenderer.invoke('server:test', url),
    saveServer: (url) => ipcRenderer.invoke('server:save', url),
    retry: () => ipcRenderer.invoke('server:retry'),
  })
}
