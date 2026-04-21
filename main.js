// main.js
'use strict';
const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path            = require('path');
const log             = require('electron-log');
const { autoUpdater } = require('electron-updater');
const { findFreePort } = require('./python-server');
const { createServer } = require('./server-factory');

function makeServer() {
  const usePython = process.env.SPARGE_SERVER === 'python';
  log.info(usePython ? 'Using PythonServer (SPARGE_SERVER=python)' : 'Using JavaServer (default)');
  return createServer({
    env:          process.env,
    isPackaged:   app.isPackaged,
    resourcesPath: process.resourcesPath,
    pythonExe:    usePython ? getPythonExe() : null,
    serverScript: usePython ? getServerScript() : null,
  });
}

autoUpdater.logger               = log;
autoUpdater.autoDownload         = true;
autoUpdater.autoInstallOnAppQuit = false;

let mainWindow = null;

function getPythonExe() {
  const platform = process.platform;
  const arch     = process.arch;
  const dirMap   = {
    'darwin-arm64': 'mac-arm64',
    'darwin-x64':   'mac-x64',
    'win32-x64':    'win-x64',
    'linux-x64':    'linux-x64',
  };
  const dir = dirMap[`${platform}-${arch}`];
  if (!dir) throw new Error(`Unsupported platform: ${platform}-${arch}`);
  const exe = platform === 'win32' ? 'python.exe' : 'python3';
  if (app.isPackaged) {
    // electron-builder strips the platform subdir when copying extraResources
    return path.join(process.resourcesPath, 'python', 'bin', exe);
  }
  return path.join(__dirname, 'resources', 'python', dir, 'bin', exe);
}

function getServerScript() {
  const base = app.isPackaged ? path.join(process.resourcesPath, 'app') : __dirname;
  return path.join(base, 'server.py');
}

const server = makeServer();

function showErrorWindow(message) {
  const escape = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const win    = new BrowserWindow({ width: 700, height: 500, show: false });
  const logs   = escape(server.getLogs().join('\n'));
  const html   = `<!DOCTYPE html><html><body style="font-family:monospace;padding:20px;background:#1a1a1a;color:#eee">
    <h2 style="color:#f87171">Sparge failed to start</h2>
    <p>${escape(message)}</p>
    <pre style="overflow:auto;background:#111;padding:10px;max-height:350px">${logs}</pre>
    </body></html>`;
  win.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
  win.show();
}

async function createMainWindow(port) {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  await mainWindow.loadURL(`http://127.0.0.1:${port}/ui/`);
  mainWindow.show();
}

function setupAutoUpdater() {
  autoUpdater.on('update-available',  info => mainWindow?.webContents.send('update:available',  info));
  autoUpdater.on('update-downloaded', info => mainWindow?.webContents.send('update:downloaded', info));
  autoUpdater.checkForUpdatesAndNotify();
  setInterval(() => autoUpdater.checkForUpdates(), 4 * 60 * 60 * 1000);
}

app.whenReady().then(async () => {
  server.on('fatal', () => showErrorWindow('The Sparge server crashed and could not restart.'));
  try {
    const port = await findFreePort();
    global.__SPARGE_PORT__ = port; // exposed for E2E tests
    await server.spawnServer(port);
    await createMainWindow(port);
    setupAutoUpdater();
  } catch (err) {
    log.error('Startup failed:', err);
    showErrorWindow(err.message);
  }
});

app.on('before-quit', async (event) => {
  event.preventDefault();
  await server.killServer();
  app.exit(0);
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

ipcMain.handle('app:version', () => app.getVersion());
ipcMain.on('update:install',  () => autoUpdater.quitAndInstall());

ipcMain.handle('dialog:openDir', async (_event, defaultPath) => {
  const { canceled, filePaths } = await dialog.showOpenDialog({
    properties: ['openDirectory'],
    defaultPath: defaultPath || app.getPath('home'),
  });
  return canceled ? null : filePaths[0];
});
