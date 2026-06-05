const { app, BrowserWindow, ipcMain, dialog } = require('electron')
const path   = require('path')
const { spawn, execSync } = require('child_process')
const fs     = require('fs')

let win
let jarvisProcess = null

// ── Find Python and repo root ──────────────────────────────────────────────────
const repoRoot = path.join(__dirname, '..', '..')

function getPython() {
  const candidates = [
    path.join(repoRoot, '.venv', 'Scripts', 'python.exe'),  // Windows
    path.join(repoRoot, '.venv', 'bin', 'python'),           // Mac/Linux
  ]
  for (const p of candidates) {
    if (fs.existsSync(p)) return p
  }
  return null
}

// ── Start Jarvis Python backend ───────────────────────────────────────────────
function startJarvis() {
  const python = getPython()

  if (!python) {
    dialog.showErrorBox(
      'Jarvis Setup Required',
      'Virtual environment not found.\n\nPlease run setup.py first:\n  python setup.py'
    )
    app.quit()
    return
  }

  console.log('[Electron] Starting Jarvis backend...')

  jarvisProcess = spawn(python, ['main.py'], {
    cwd: repoRoot,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,   // no console window on Windows
  })

  jarvisProcess.stdout.on('data', d => process.stdout.write('[Jarvis] ' + d))
  jarvisProcess.stderr.on('data', d => process.stderr.write('[Jarvis ERR] ' + d))

  jarvisProcess.on('exit', (code) => {
    console.log(`[Electron] Jarvis exited with code ${code}`)
  })

  // Give the WebSocket bridge time to start before showing UI
  return new Promise(resolve => setTimeout(resolve, 3000))
}

// ── Create the HUD window ─────────────────────────────────────────────────────
function createWindow() {
  win = new BrowserWindow({
    fullscreen: true,
    frame: false,
    transparent: true,
    backgroundColor: '#00000000',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    alwaysOnTop: false,
    skipTaskbar: false,
    title: 'J.A.R.V.I.S',
  })

  win.loadFile(path.join(__dirname, 'index.html'))

  win.webContents.on('before-input-event', (event, input) => {
    if (input.key === 'Escape' && input.type === 'keyDown') {
      win.setFullScreen(false)
    }
    if (input.key === 'F11' && input.type === 'keyDown') {
      win.setFullScreen(!win.isFullScreen())
    }
  })
}

// ── App lifecycle ─────────────────────────────────────────────────────────────
app.whenReady().then(async () => {
  await startJarvis()
  createWindow()
})

app.on('window-all-closed', () => {
  // Kill Jarvis backend when UI closes
  if (jarvisProcess) {
    console.log('[Electron] Shutting down Jarvis...')
    jarvisProcess.kill()
  }
  app.quit()
})

app.on('before-quit', () => {
  if (jarvisProcess) jarvisProcess.kill()
})

ipcMain.on('close-app', () => {
  if (jarvisProcess) jarvisProcess.kill()
  app.quit()
})

ipcMain.on('toggle-fullscreen', () => {
  win.setFullScreen(!win.isFullScreen())
})