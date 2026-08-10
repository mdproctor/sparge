# Spec: Electron Wrapper — Self-Contained Desktop App

**Date:** 2026-04-09
**Status:** Approved

---

## Overview

Wrap Sparge as a self-contained Electron desktop application. The Python server
(`server.py`) runs as an embedded subprocess — no external Python required at
runtime. Ships as a native installer for Mac, Windows, and Linux via GitHub
Releases with auto-update.

---

## Scope

- Electron shell with robust Python process manager
- Embedded CPython via python-build-standalone (per-platform, download at build time)
- GitHub Actions release pipeline (Mac `.dmg`, Windows `.exe`, Linux `.AppImage`)
- Auto-update via `electron-updater` + GitHub Releases
- Unit, integration, and happy-path E2E tests

**Out of scope (V1):** code-signing, multi-project tabs, Linux/Windows E2E tests.

---

## Repository Layout

```
electron/
  main.js            ← Electron entry point
  python-server.js   ← process manager
  preload.js         ← contextBridge (version, update events)
  package.json       ← Electron + electron-builder config

resources/
  python/
    mac-arm64/       ← python-build-standalone (excluded from other platforms)
    mac-x64/
    win-x64/
    linux-x64/
  app/               ← copy of server.py + scripts/ + ui/

scripts/
  fetch-python.js    ← downloads python-build-standalone at build time

.github/workflows/
  release.yml        ← matrix build triggered by git tag v*
```

---

## Startup Sequence

1. Electron launches → `main.js`
2. `python-server.js` finds a free port via TCP probe (`net.createServer` on port 0)
3. Spawns `resources/python/<platform>/bin/python3 resources/app/server.py --port PORT`
4. Health-check loop polls `GET /api/config` every 200ms, up to 15s
5. On success → `BrowserWindow` loads `http://localhost:PORT/ui/`
6. On timeout → error window showing last 200 lines of Python stdout/stderr

## Shutdown

`app.on('before-quit')` sends SIGTERM to Python process, waits up to 3s, then SIGKILL.

---

## Process Manager (`python-server.js`)

### Public API

```js
spawnServer(port)   → Promise<void>   // resolves when server reaches healthy state
killServer()        → Promise<void>   // graceful SIGTERM → SIGKILL
getPort()           → number | null
getLogs()           → string[]        // ring buffer, last 200 lines
on('crashed', fn)
on('restarted', fn)
on('fatal', fn)     // 3 restarts exhausted — stop retrying
```

### State Machine

```
idle → starting → healthy → crashed → restarting → healthy
                                                  ↘ fatal (3rd crash)
```

### Crash Recovery

- Backoff: 1s / 2s / 4s between restart attempts
- Max 3 consecutive crashes without reaching `healthy`
- Crash counter resets after 60s of stability
- On `fatal`: emits event, shows error dialog, does not restart again

### Logging

Python stdout/stderr captured to a 200-line ring buffer. Surfaced in:
- Error dialogs (fatal startup / fatal crash)
- Electron log file via `electron-log`

---

## Python Bundling

**Runtime:** python-build-standalone — pre-built, relocatable CPython.

**Fetch script (`scripts/fetch-python.js`):**
- Run during `npm ci` and in CI before packaging
- Downloads the pinned release (e.g. `20250101/cpython-3.12.8`) for the current platform
- Verifies SHA-256 checksum
- Runs `pip install -r requirements.txt --target resources/python/<platform>/lib/`
- Version pinned in `package.json` — upgrades are explicit

**`electron-builder` config:**
- `extraResources` includes only the platform-relevant `python/<platform>/` directory
- Mac users don't receive Windows/Linux Python runtimes

**`server.py` change:** Add `--port PORT` CLI argument via `argparse` (2-line change).
All other server logic unchanged.

---

## Build & Release Pipeline

**Trigger:** `git tag v*` pushed to GitHub.

**Matrix:** `macos-latest` / `windows-latest` / `ubuntu-latest` — one runner per platform.

**Each runner:**
1. `npm ci` (runs `fetch-python.js` as postinstall)
2. `electron-builder --publish never` → produces platform artifact
3. Upload artifact to workflow

**Final job:**
- Creates GitHub Release
- Attaches `.dmg`, `.exe`, `.AppImage` and update manifests (`latest.yml`, `latest-mac.yml`)

**Outputs:**

| Platform | Format | Code-signed V1 |
|----------|--------|----------------|
| Mac arm64 + x64 | Universal `.dmg` | No — users see Gatekeeper warning |
| Windows x64 | NSIS `.exe` | No — users see SmartScreen warning |
| Linux x64 | `.AppImage` | N/A |

Code-signing is a post-V1 concern.

### Auto-Update

- `electron-updater` checks GitHub Releases on launch and every 4 hours
- Non-blocking notification: *"Update available — restart to install"*
- User-triggered: downloads, verifies, relaunches
- Manifest published automatically by `electron-builder`

---

## Testing Strategy

### Unit tests (Jest) — no process spawning

- `python-server.js`: state machine transitions, backoff timing (fake timers),
  port allocation, health-check polling (mocked `http.get` and `net`)
- `preload.js`: contextBridge surface correct
- `fetch-python.js`: URL construction per platform, checksum verification logic

### Integration tests (Jest + real Python)

- `spawnServer()` reaches `healthy` state with real `server.py`
- Crash recovery: kill mid-run → `restarted` fires → `healthy` again
- Graceful shutdown: `killServer()` terminates, no port leak
- Fatal: 3× kills → `fatal` event, no further restarts
- `GET /api/config` returns valid JSON after startup

### E2E happy-path tests (Playwright + Electron launch)

- App launches, window appears, `projects.html` loads without error
- Navigate to a project, `index.html` loads and post list populates
- API call (`GET /api/posts`) succeeds through the window
- App quits cleanly — no zombie Python process

**CI coverage:** Unit + integration run on all 3 platforms.
E2E runs on `macos-latest` only for V1 (Linux/Windows E2E deferred — requires display server setup).

---

## Key Dependencies

| Package | Purpose |
|---------|---------|
| `electron` | Shell |
| `electron-builder` | Packaging + installer generation |
| `electron-updater` | Auto-update |
| `electron-log` | Structured logging from main process |
| `jest` | Unit + integration tests |
| `playwright` + `@playwright/test` | E2E tests |
| python-build-standalone | Embedded CPython (downloaded at build time) |
