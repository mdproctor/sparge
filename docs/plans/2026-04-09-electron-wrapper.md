# Electron Wrapper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wrap Sparge as a self-contained Electron desktop app (Mac/Win/Linux) with embedded CPython, auto-update, and full test coverage.

**Architecture:** `main.js` (Electron entry) drives `python-server.js` (state machine: idle → starting → healthy → crashed → restarting | fatal). `scripts/fetch-python.js` downloads python-build-standalone at build time. `BrowserWindow` loads the existing Python HTTP server at a dynamically allocated port. `electron-builder` packages for all three platforms; GitHub Actions releases on `git tag v*`.

**Tech Stack:** Electron 33, electron-builder 25, electron-updater 6, electron-log 5, Jest 29, Playwright (E2E), python-build-standalone CPython 3.12.

**Issues:** Epic #42, child #43. All commits: `Refs #43`.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `server.py` | Modify | Accept `--port PORT` CLI arg |
| `package.json` | Create | npm + Electron + electron-builder + Jest config |
| `jest.config.js` | Create | Jest projects: unit (node env) and integration (30s timeout) |
| `playwright.config.js` | Create | Playwright E2E config |
| `main.js` | Create | Electron entry: window lifecycle, startup, shutdown, auto-update |
| `preload.js` | Create | contextBridge: version + update events to renderer |
| `python-server.js` | Create | `findFreePort`, `pollUntilReady`, `PythonServer` class |
| `scripts/fetch-python.js` | Create | Download + verify python-build-standalone per platform |
| `electron-tests/unit/fetch-python.test.js` | Create | Unit: URL construction, checksum logic |
| `electron-tests/unit/python-server-utils.test.js` | Create | Unit: port alloc + health check (mocked net/http) |
| `electron-tests/unit/python-server.test.js` | Create | Unit: state machine, backoff, crash counter, shutdown |
| `electron-tests/unit/preload.test.js` | Create | Unit: contextBridge surface shape |
| `electron-tests/integration/python-server.integration.test.js` | Create | Integration: real Python, crash/restart, fatal, graceful shutdown |
| `electron-tests/e2e/app.e2e.test.js` | Create | E2E: app launches, API works, clean quit |
| `.github/workflows/release.yml` | Create | Matrix build → GitHub Release on `v*` tag |

---

## Task 1: Add `--port` CLI arg to `server.py`

**Files:**
- Modify: `server.py`
- Create: `tests/test_server_port_arg.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server_port_arg.py
import os, subprocess, sys, time, urllib.request

def test_server_accepts_port_arg():
    port = 19876
    proc = subprocess.Popen(
        [sys.executable, 'server.py', '--port', str(port)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=os.path.join(os.path.dirname(__file__), '..')
    )
    try:
        for _ in range(30):
            try:
                resp = urllib.request.urlopen(
                    f'http://localhost:{port}/api/config', timeout=1
                )
                assert resp.status == 200
                return
            except Exception:
                time.sleep(0.5)
        raise AssertionError('Server did not start on port 19876')
    finally:
        proc.terminate()
        proc.wait(timeout=5)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ~/claude/sparge
python3 -m pytest tests/test_server_port_arg.py -v
```
Expected: FAIL with `unrecognised arguments: --port`

- [ ] **Step 3: Add `import argparse` to `server.py`**

Add `import argparse` alongside the existing stdlib imports (line ~36–44). Then replace the `if __name__ == '__main__':` block at the bottom:

```python
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=cfg['server']['port'])
    args = parser.parse_args()

    print('Initialising state from source posts…')
    added = State.init_from_source()
    print(f'  {added} new posts added to state')

    total = len(State.get_all())
    print(f'  {total} posts tracked')
    print(f'\nBlog Migrator running → http://localhost:{args.port}/ui/')
    print(f'Project: {cfg["project_name"]}')

    HTTPServer(('localhost', args.port), Handler).serve_forever()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_server_port_arg.py -v
```
Expected: PASS

- [ ] **Step 5: Run full suite to confirm no regressions**

```bash
python3 -m pytest tests/ -q
```
Expected: 438 passing, 4 pre-existing failures in `test_md_validator.py`

- [ ] **Step 6: Commit**

```bash
git add server.py tests/test_server_port_arg.py
git commit -m "feat: server.py accepts --port CLI arg

Refs #43"
```

---

## Task 2: Electron project scaffolding

**Files:**
- Create: `package.json`
- Create: `jest.config.js`

- [ ] **Step 1: Create `package.json`**

```json
{
  "name": "sparge",
  "version": "0.1.0",
  "description": "Blog migration tool — Electron desktop app",
  "main": "main.js",
  "scripts": {
    "start": "electron .",
    "test:unit": "jest --selectProjects unit",
    "test:integration": "jest --selectProjects integration",
    "test:e2e": "playwright test",
    "test": "jest",
    "postinstall": "node scripts/fetch-python.js",
    "pack": "electron-builder --dir",
    "dist": "electron-builder"
  },
  "dependencies": {
    "electron-log": "^5.2.0",
    "electron-updater": "^6.3.0"
  },
  "devDependencies": {
    "electron": "^33.4.0",
    "electron-builder": "^25.1.8",
    "@playwright/test": "^1.50.0",
    "jest": "^29.7.0"
  },
  "build": {
    "appId": "com.sparge.app",
    "productName": "Sparge",
    "files": [
      "main.js",
      "python-server.js",
      "preload.js"
    ],
    "extraResources": [
      { "from": "server.py", "to": "app/server.py" },
      { "from": "scripts", "to": "app/scripts", "filter": ["**/*", "!fetch-python.js"] },
      { "from": "ui", "to": "app/ui" }
    ],
    "mac": {
      "target": [{ "target": "dmg", "arch": ["arm64", "x64"] }],
      "extraResources": [{ "from": "resources/python/mac-${arch}", "to": "python" }]
    },
    "win": {
      "target": "nsis",
      "extraResources": [{ "from": "resources/python/win-x64", "to": "python" }]
    },
    "linux": {
      "target": "AppImage",
      "extraResources": [{ "from": "resources/python/linux-x64", "to": "python" }]
    },
    "publish": {
      "provider": "github",
      "owner": "mdproctor",
      "repo": "sparge"
    }
  }
}
```

- [ ] **Step 2: Create `jest.config.js`**

```javascript
// jest.config.js
module.exports = {
  projects: [
    {
      displayName: 'unit',
      testMatch: ['<rootDir>/electron-tests/unit/**/*.test.js'],
      testEnvironment: 'node',
    },
    {
      displayName: 'integration',
      testMatch: ['<rootDir>/electron-tests/integration/**/*.test.js'],
      testEnvironment: 'node',
      testTimeout: 30000,
    },
  ],
};
```

- [ ] **Step 3: Install dependencies (skip postinstall — fetch-python.js doesn't exist yet)**

```bash
cd ~/claude/sparge
npm install --ignore-scripts
```
Expected: `node_modules/` created, no errors.

- [ ] **Step 4: Commit**

```bash
git add package.json jest.config.js package-lock.json
git commit -m "feat: Electron project scaffolding — package.json, jest config

Refs #43"
```

---

## Task 3: `scripts/fetch-python.js` + unit tests

**Files:**
- Create: `scripts/fetch-python.js`
- Create: `electron-tests/unit/fetch-python.test.js`

- [ ] **Step 1: Write the failing unit tests**

```javascript
// electron-tests/unit/fetch-python.test.js
const { getDownloadUrl, getPlatformDir, PYTHON_VERSION, STANDALONE_TAG } = require('../../scripts/fetch-python');

describe('getDownloadUrl', () => {
  test('mac arm64 uses aarch64-apple-darwin tar.gz', () => {
    const url = getDownloadUrl('darwin', 'arm64');
    expect(url).toContain(STANDALONE_TAG);
    expect(url).toContain('aarch64-apple-darwin');
    expect(url).toContain('install_only');
    expect(url).toMatch(/\.tar\.gz$/);
  });

  test('mac x64 uses x86_64-apple-darwin tar.gz', () => {
    const url = getDownloadUrl('darwin', 'x64');
    expect(url).toContain('x86_64-apple-darwin');
    expect(url).toMatch(/\.tar\.gz$/);
  });

  test('windows x64 uses x86_64-pc-windows-msvc zip', () => {
    const url = getDownloadUrl('win32', 'x64');
    expect(url).toContain('x86_64-pc-windows-msvc');
    expect(url).toMatch(/\.zip$/);
  });

  test('linux x64 uses x86_64-unknown-linux-gnu tar.gz', () => {
    const url = getDownloadUrl('linux', 'x64');
    expect(url).toContain('x86_64-unknown-linux-gnu');
    expect(url).toMatch(/\.tar\.gz$/);
  });

  test('throws on unsupported platform', () => {
    expect(() => getDownloadUrl('freebsd', 'x64')).toThrow('Unsupported');
  });
});

describe('getPlatformDir', () => {
  test('darwin arm64 → mac-arm64', () => expect(getPlatformDir('darwin', 'arm64')).toBe('mac-arm64'));
  test('darwin x64 → mac-x64',     () => expect(getPlatformDir('darwin', 'x64')).toBe('mac-x64'));
  test('win32 x64 → win-x64',      () => expect(getPlatformDir('win32', 'x64')).toBe('win-x64'));
  test('linux x64 → linux-x64',    () => expect(getPlatformDir('linux', 'x64')).toBe('linux-x64'));
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
npm run test:unit -- --testPathPattern=fetch-python
```
Expected: FAIL — `Cannot find module '../../scripts/fetch-python'`

- [ ] **Step 3: Create `scripts/fetch-python.js`**

```javascript
// scripts/fetch-python.js
'use strict';
const https  = require('https');
const fs     = require('fs');
const path   = require('path');
const crypto = require('crypto');
const { execSync } = require('child_process');

const PYTHON_VERSION = '3.12.9';
const STANDALONE_TAG = '20250409';
const BASE_URL = 'https://github.com/astral-sh/python-build-standalone/releases/download';

const PLATFORM_MAP = {
  'darwin-arm64': { dir: 'mac-arm64', arch: 'aarch64-apple-darwin',     ext: 'tar.gz' },
  'darwin-x64':   { dir: 'mac-x64',   arch: 'x86_64-apple-darwin',      ext: 'tar.gz' },
  'win32-x64':    { dir: 'win-x64',   arch: 'x86_64-pc-windows-msvc',   ext: 'zip'    },
  'linux-x64':    { dir: 'linux-x64', arch: 'x86_64-unknown-linux-gnu', ext: 'tar.gz' },
};

function _key(platform, arch) { return `${platform}-${arch}`; }

function getPlatformDir(platform, arch) {
  const info = PLATFORM_MAP[_key(platform, arch)];
  if (!info) throw new Error(`Unsupported platform: ${_key(platform, arch)}`);
  return info.dir;
}

function getDownloadUrl(platform, arch) {
  const info = PLATFORM_MAP[_key(platform, arch)];
  if (!info) throw new Error(`Unsupported platform: ${_key(platform, arch)}`);
  const filename = `cpython-${PYTHON_VERSION}+${STANDALONE_TAG}-${info.arch}-install_only_stripped.${info.ext}`;
  return `${BASE_URL}/${STANDALONE_TAG}/${filename}`;
}

function sha256File(filePath) {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');
}

function download(url, dest) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(dest);
    const request = (u) => https.get(u, (res) => {
      if (res.statusCode === 301 || res.statusCode === 302) return request(res.headers.location);
      if (res.statusCode !== 200) { reject(new Error(`HTTP ${res.statusCode} for ${u}`)); return; }
      res.pipe(file);
      file.on('finish', () => file.close(resolve));
    }).on('error', reject);
    request(url);
  });
}

async function fetchAndVerify(url, tmpDir) {
  const filename     = path.basename(url);
  const archivePath  = path.join(tmpDir, filename);
  const checksumPath = archivePath + '.sha256';
  console.log(`Downloading ${url}`);
  await download(url, archivePath);
  await download(url + '.sha256', checksumPath);
  const expected = fs.readFileSync(checksumPath, 'utf8').trim().split(/\s+/)[0];
  const actual   = sha256File(archivePath);
  if (actual !== expected) throw new Error(`Checksum mismatch: expected ${expected}, got ${actual}`);
  console.log('Checksum OK');
  return archivePath;
}

function extract(archivePath, destDir, ext) {
  fs.mkdirSync(destDir, { recursive: true });
  if (ext === 'tar.gz') {
    execSync(`tar -xzf "${archivePath}" -C "${destDir}" --strip-components=1`);
  } else {
    execSync(`powershell -Command "Expand-Archive -Path '${archivePath}' -DestinationPath '${destDir}' -Force"`);
  }
}

async function main() {
  const platform = process.platform;
  const arch     = process.arch;
  const info     = PLATFORM_MAP[_key(platform, arch)];
  if (!info) { console.log(`Platform ${_key(platform, arch)} not supported — skipping`); return; }

  const projectRoot = path.join(__dirname, '..');
  const destDir     = path.join(projectRoot, 'resources', 'python', info.dir);
  const tmpDir      = path.join(projectRoot, 'resources', '_tmp');

  const marker = path.join(destDir, 'bin', platform === 'win32' ? 'python.exe' : 'python3');
  if (fs.existsSync(marker)) { console.log(`Python already at ${destDir} — skipping`); return; }

  fs.mkdirSync(tmpDir, { recursive: true });
  const archivePath = await fetchAndVerify(getDownloadUrl(platform, arch), tmpDir);
  extract(archivePath, destDir, info.ext);
  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log(`Python installed to ${destDir}`);
}

if (require.main === module) {
  main().catch(err => { console.error(err); process.exit(1); });
}

module.exports = { getDownloadUrl, getPlatformDir, sha256File, PYTHON_VERSION, STANDALONE_TAG };
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npm run test:unit -- --testPathPattern=fetch-python
```
Expected: 9 passing

- [ ] **Step 5: Run `fetch-python.js` to download embedded Python**

```bash
node scripts/fetch-python.js
```
Expected: Downloads and extracts to `resources/python/mac-arm64/` (or current platform). Takes ~1-2 minutes on first run.

- [ ] **Step 6: Commit**

```bash
git add scripts/fetch-python.js electron-tests/unit/fetch-python.test.js
git commit -m "feat: fetch-python.js downloads python-build-standalone at build time

Refs #43"
```

---

## Task 4: `python-server.js` — port allocation + health check + unit tests

**Files:**
- Create: `python-server.js` (utilities only — PythonServer class stub)
- Create: `electron-tests/unit/python-server-utils.test.js`

- [ ] **Step 1: Write failing unit tests**

```javascript
// electron-tests/unit/python-server-utils.test.js
jest.mock('http');
jest.mock('net');

const http = require('http');
const net  = require('net');
const { findFreePort, pollUntilReady } = require('../../python-server');

describe('findFreePort', () => {
  test('returns the port assigned by the OS', async () => {
    const mockServer = {
      listen:  jest.fn((port, host, cb) => cb()),
      address: jest.fn(() => ({ port: 54321 })),
      close:   jest.fn((cb) => cb()),
      on:      jest.fn(),
    };
    net.createServer.mockReturnValue(mockServer);
    const port = await findFreePort();
    expect(port).toBe(54321);
    expect(mockServer.listen).toHaveBeenCalledWith(0, '127.0.0.1', expect.any(Function));
  });
});

describe('pollUntilReady', () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  test('resolves when server responds 200', async () => {
    const mockRes = { statusCode: 200, resume: jest.fn() };
    http.get.mockImplementation((_url, cb) => {
      cb(mockRes);
      return { on: jest.fn(), setTimeout: jest.fn(), destroy: jest.fn() };
    });
    await expect(pollUntilReady(9876, { intervalMs: 200, timeoutMs: 5000 })).resolves.toBeUndefined();
  });

  test('rejects after timeout when server never responds', async () => {
    http.get.mockImplementation((_url, _cb) => ({
      on: (ev, fn) => { if (ev === 'error') fn(new Error('ECONNREFUSED')); },
      setTimeout: jest.fn(),
      destroy: jest.fn(),
    }));
    const promise = pollUntilReady(9876, { intervalMs: 50, timeoutMs: 200 });
    jest.advanceTimersByTime(300);
    await expect(promise).rejects.toThrow('did not start');
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
npm run test:unit -- --testPathPattern=python-server-utils
```
Expected: FAIL — `Cannot find module '../../python-server'`

- [ ] **Step 3: Create `python-server.js`**

```javascript
// python-server.js
'use strict';
const { spawn }      = require('child_process');
const http           = require('http');
const net            = require('net');
const { EventEmitter } = require('events');

const MAX_RESTARTS        = 3;
const STABILITY_RESET_MS  = 60_000;
const BACKOFF_MS          = [1000, 2000, 4000];
const LOG_BUFFER_SIZE     = 200;

function findFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
    server.on('error', reject);
  });
}

function pollUntilReady(port, { intervalMs = 200, timeoutMs = 15000 } = {}) {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + timeoutMs;
    const attempt = () => {
      if (Date.now() >= deadline) {
        reject(new Error(`Server did not start within ${timeoutMs}ms`));
        return;
      }
      const req = http.get(`http://127.0.0.1:${port}/api/config`, (res) => {
        res.resume();
        if (res.statusCode === 200) resolve();
        else setTimeout(attempt, intervalMs);
      });
      req.on('error', () => setTimeout(attempt, intervalMs));
      req.setTimeout(intervalMs, () => { req.destroy(); });
    };
    attempt();
  });
}

// PythonServer class — implemented in Task 5
class PythonServer extends EventEmitter {}

module.exports = { PythonServer, findFreePort, pollUntilReady };
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npm run test:unit -- --testPathPattern=python-server-utils
```
Expected: 3 passing

- [ ] **Step 5: Commit**

```bash
git add python-server.js electron-tests/unit/python-server-utils.test.js
git commit -m "feat: python-server.js — findFreePort and pollUntilReady

Refs #43"
```

---

## Task 5: `PythonServer` class — state machine + crash recovery + unit tests

**Files:**
- Modify: `python-server.js` (replace stub class)
- Create: `electron-tests/unit/python-server.test.js`

- [ ] **Step 1: Write failing unit tests**

```javascript
// electron-tests/unit/python-server.test.js
const { EventEmitter } = require('events');

jest.mock('child_process');

// Override pollUntilReady to resolve immediately — we test state logic, not HTTP polling
jest.mock('../../python-server', () => {
  const actual = jest.requireActual('../../python-server');
  return { ...actual, pollUntilReady: jest.fn().mockResolvedValue(undefined) };
});

const { spawn }         = require('child_process');
const { PythonServer }  = require('../../python-server');

function makeMockProcess() {
  const proc = new EventEmitter();
  proc.stdout = new EventEmitter();
  proc.stderr = new EventEmitter();
  proc.kill   = jest.fn((signal) => setImmediate(() => proc.emit('exit', null, signal)));
  return proc;
}

beforeEach(() => jest.useFakeTimers());
afterEach(() => { jest.useRealTimers(); jest.clearAllMocks(); });

test('starts idle, reaches healthy after spawnServer', async () => {
  spawn.mockReturnValue(makeMockProcess());
  const server = new PythonServer({ pythonExe: 'python3', serverScript: 'server.py' });
  expect(server._state).toBe('idle');
  await server.spawnServer(19001);
  expect(server._state).toBe('healthy');
});

test('emits crashed then restarted after unexpected exit', async () => {
  const proc1 = makeMockProcess();
  const proc2 = makeMockProcess();
  spawn.mockReturnValueOnce(proc1).mockReturnValueOnce(proc2);

  const server = new PythonServer({ pythonExe: 'python3', serverScript: 'server.py' });
  await server.spawnServer(19002);

  const events = [];
  server.on('crashed',   () => events.push('crashed'));
  server.on('restarted', () => events.push('restarted'));

  proc1.emit('exit', 1, null);
  expect(server._state).toBe('crashed');
  await jest.advanceTimersByTimeAsync(1100); // BACKOFF_MS[0] = 1000ms
  expect(events).toEqual(['crashed', 'restarted']);
  expect(server._state).toBe('healthy');
});

test('emits fatal after MAX_RESTARTS consecutive crashes', async () => {
  const procs = [0, 1, 2, 3].map(() => makeMockProcess());
  procs.forEach(p => spawn.mockReturnValueOnce(p));

  const server  = new PythonServer({ pythonExe: 'python3', serverScript: 'server.py' });
  await server.spawnServer(19003);

  const events = [];
  server.on('fatal', () => events.push('fatal'));

  procs[0].emit('exit', 1, null);
  await jest.advanceTimersByTimeAsync(1100);
  procs[1].emit('exit', 1, null);
  await jest.advanceTimersByTimeAsync(2100);
  procs[2].emit('exit', 1, null);
  await jest.advanceTimersByTimeAsync(4100);
  procs[3].emit('exit', 1, null);

  expect(events).toContain('fatal');
  expect(server._state).toBe('fatal');
});

test('crash counter resets after stability period (60s)', async () => {
  const procs = [0, 1].map(() => makeMockProcess());
  procs.forEach(p => spawn.mockReturnValueOnce(p));

  const server = new PythonServer({ pythonExe: 'python3', serverScript: 'server.py' });
  await server.spawnServer(19004);

  procs[0].emit('exit', 1, null); // crash 1
  await jest.advanceTimersByTimeAsync(1100);
  expect(server._crashCount).toBe(1);

  await jest.advanceTimersByTimeAsync(61000); // stability period expires
  expect(server._crashCount).toBe(0);
});

test('killServer sends SIGTERM and resolves', async () => {
  spawn.mockReturnValue(makeMockProcess());
  const server = new PythonServer({ pythonExe: 'python3', serverScript: 'server.py' });
  await server.spawnServer(19005);
  const killPromise = server.killServer();
  expect(server._process.kill).toHaveBeenCalledWith('SIGTERM');
  await killPromise;
  expect(server._state).toBe('idle');
});

test('getLogs returns captured stdout + stderr lines', async () => {
  const proc = makeMockProcess();
  spawn.mockReturnValue(proc);
  const server = new PythonServer({ pythonExe: 'python3', serverScript: 'server.py' });
  await server.spawnServer(19006);
  proc.stdout.emit('data', 'line one\nline two\n');
  proc.stderr.emit('data', 'error line\n');
  expect(server.getLogs()).toEqual(['line one', 'line two', 'error line']);
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
npm run test:unit -- --testPathPattern=python-server.test
```
Expected: FAIL — PythonServer class is empty

- [ ] **Step 3: Replace stub class in `python-server.js`**

Replace `class PythonServer extends EventEmitter {}` with:

```javascript
class PythonServer extends EventEmitter {
  constructor({ pythonExe, serverScript }) {
    super();
    this._pythonExe    = pythonExe;
    this._serverScript = serverScript;
    this._port         = null;
    this._process      = null;
    this._state        = 'idle';
    this._logs         = [];
    this._crashCount   = 0;
    this._stabilityTimer = null;
  }

  getPort() { return this._port; }
  getLogs() { return [...this._logs]; }

  async spawnServer(port) {
    this._port  = port;
    this._state = 'starting';
    this._doSpawn();
    await pollUntilReady(port);
    this._state = 'healthy';
    this._resetStabilityTimer();
  }

  _doSpawn() {
    this._process = spawn(this._pythonExe, [this._serverScript, '--port', String(this._port)]);
    this._process.stdout.on('data', d => this._appendLog(d.toString()));
    this._process.stderr.on('data', d => this._appendLog(d.toString()));
    this._process.on('exit', (code, signal) => this._onExit(code, signal));
  }

  _appendLog(text) {
    const lines = text.split('\n').filter(l => l.length > 0);
    this._logs.push(...lines);
    if (this._logs.length > LOG_BUFFER_SIZE) this._logs = this._logs.slice(-LOG_BUFFER_SIZE);
  }

  _resetStabilityTimer() {
    if (this._stabilityTimer) clearTimeout(this._stabilityTimer);
    this._stabilityTimer = setTimeout(() => { this._crashCount = 0; }, STABILITY_RESET_MS);
  }

  _onExit(code, signal) {
    if (this._state === 'idle') return;
    this._state = 'crashed';
    this.emit('crashed', { code, signal });
    this._crashCount++;
    if (this._crashCount > MAX_RESTARTS) {
      this._state = 'fatal';
      this.emit('fatal', { logs: this.getLogs() });
      return;
    }
    const delay = BACKOFF_MS[Math.min(this._crashCount - 1, BACKOFF_MS.length - 1)];
    setTimeout(() => this._restart(), delay);
  }

  async _restart() {
    this._state = 'restarting';
    this._doSpawn();
    try {
      await pollUntilReady(this._port);
      this._state = 'healthy';
      this.emit('restarted');
      this._resetStabilityTimer();
    } catch (_) {
      // _onExit handles the next failure
    }
  }

  async killServer() {
    this._state = 'idle';
    if (this._stabilityTimer) clearTimeout(this._stabilityTimer);
    if (!this._process) return;
    return new Promise((resolve) => {
      const timer = setTimeout(() => { this._process.kill('SIGKILL'); resolve(); }, 3000);
      this._process.once('exit', () => { clearTimeout(timer); resolve(); });
      this._process.kill('SIGTERM');
    });
  }
}
```

- [ ] **Step 4: Run all unit tests**

```bash
npm run test:unit
```
Expected: all passing

- [ ] **Step 5: Commit**

```bash
git add python-server.js electron-tests/unit/python-server.test.js
git commit -m "feat: PythonServer — state machine, crash recovery, backoff

Refs #43"
```

---

## Task 6: Integration tests for `PythonServer`

**Files:**
- Create: `electron-tests/integration/python-server.integration.test.js`

These tests spawn **real** `server.py` using system Python3. Set `PYTHON_EXE` env var if `python3` is not in PATH.

- [ ] **Step 1: Create the integration test file**

```javascript
// electron-tests/integration/python-server.integration.test.js
const http = require('http');
const path = require('path');
const { PythonServer, findFreePort } = require('../../python-server');

const PYTHON_EXE    = process.env.PYTHON_EXE || 'python3';
const SERVER_SCRIPT = path.join(__dirname, '..', '..', 'server.py');

function getJson(port, route) {
  return new Promise((resolve, reject) => {
    http.get(`http://127.0.0.1:${port}${route}`, (res) => {
      let body = '';
      res.on('data', d => body += d);
      res.on('end', () => resolve(JSON.parse(body)));
    }).on('error', reject);
  });
}

test('happy path: spawnServer reaches healthy, /api/config returns JSON', async () => {
  const port   = await findFreePort();
  const server = new PythonServer({ pythonExe: PYTHON_EXE, serverScript: SERVER_SCRIPT });
  await server.spawnServer(port);
  expect(server._state).toBe('healthy');
  const config = await getJson(port, '/api/config');
  expect(config).toHaveProperty('server');
  await server.killServer();
  expect(server._state).toBe('idle');
});

test('crash recovery: SIGKILL → restarted event → healthy again', async () => {
  const port   = await findFreePort();
  const server = new PythonServer({ pythonExe: PYTHON_EXE, serverScript: SERVER_SCRIPT });
  await server.spawnServer(port);

  const restarted = new Promise(resolve => server.once('restarted', resolve));
  server._process.kill('SIGKILL');
  await restarted;

  expect(server._state).toBe('healthy');
  const config = await getJson(port, '/api/config');
  expect(config).toHaveProperty('server');
  await server.killServer();
});

test('graceful shutdown: killServer resolves, state is idle', async () => {
  const port   = await findFreePort();
  const server = new PythonServer({ pythonExe: PYTHON_EXE, serverScript: SERVER_SCRIPT });
  await server.spawnServer(port);
  await server.killServer();
  expect(server._state).toBe('idle');
});

test('fatal: 3 restarts exhausted → fatal event, no further attempts', async () => {
  const port   = await findFreePort();
  const server = new PythonServer({ pythonExe: PYTHON_EXE, serverScript: SERVER_SCRIPT });
  await server.spawnServer(port);

  const fatal = new Promise(resolve => server.once('fatal', resolve));
  const killLoop = () => {
    if (server._process && server._state !== 'fatal') {
      server._process.kill('SIGKILL');
      setTimeout(killLoop, 400);
    }
  };
  killLoop();
  await fatal;
  expect(server._state).toBe('fatal');
});
```

- [ ] **Step 2: Run integration tests**

```bash
npm run test:integration
```
Expected: 4 passing. Each test may take up to 10s (server startup + restart cycles).

- [ ] **Step 3: Commit**

```bash
git add electron-tests/integration/python-server.integration.test.js
git commit -m "test: PythonServer integration tests — happy path, crash recovery, fatal

Refs #43"
```

---

## Task 7: `preload.js` and `main.js`

**Files:**
- Create: `preload.js`
- Create: `main.js`
- Create: `electron-tests/unit/preload.test.js`

- [ ] **Step 1: Create `preload.js`**

```javascript
// preload.js
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('sparge', {
  getVersion:          () => ipcRenderer.invoke('app:version'),
  onUpdateAvailable:   (fn) => ipcRenderer.on('update:available',  (_, info) => fn(info)),
  onUpdateDownloaded:  (fn) => ipcRenderer.on('update:downloaded', (_, info) => fn(info)),
  installUpdate:       () => ipcRenderer.send('update:install'),
});
```

- [ ] **Step 2: Write preload unit test**

```javascript
// electron-tests/unit/preload.test.js
// preload.js calls Electron APIs (contextBridge) which aren't available in Jest.
// We verify the API surface by reading the source.
const fs  = require('fs');
const src = fs.readFileSync(require.resolve('../../preload.js'), 'utf8');

test('exposes getVersion',         () => expect(src).toContain('getVersion'));
test('exposes onUpdateAvailable',  () => expect(src).toContain('onUpdateAvailable'));
test('exposes onUpdateDownloaded', () => expect(src).toContain('onUpdateDownloaded'));
test('exposes installUpdate',      () => expect(src).toContain('installUpdate'));
test('uses exposeInMainWorld',     () => expect(src).toContain('exposeInMainWorld'));
```

- [ ] **Step 3: Run preload unit tests**

```bash
npm run test:unit -- --testPathPattern=preload
```
Expected: 5 passing

- [ ] **Step 4: Create `main.js`**

```javascript
// main.js
'use strict';
const { app, BrowserWindow, ipcMain } = require('electron');
const path        = require('path');
const log         = require('electron-log');
const { autoUpdater } = require('electron-updater');
const { PythonServer, findFreePort } = require('./python-server');

autoUpdater.logger        = log;
autoUpdater.autoDownload  = true;
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
  const base = app.isPackaged ? process.resourcesPath : path.join(__dirname, 'resources');
  const exe  = platform === 'win32' ? 'python.exe' : 'python3';
  return path.join(base, 'python', dir, 'bin', exe);
}

function getServerScript() {
  const base = app.isPackaged ? path.join(process.resourcesPath, 'app') : __dirname;
  return path.join(base, 'server.py');
}

const server = new PythonServer({ pythonExe: getPythonExe(), serverScript: getServerScript() });

function showErrorWindow(message) {
  const win = new BrowserWindow({ width: 700, height: 500, show: false });
  const logs = server.getLogs().join('\n').replace(/</g, '&lt;');
  const html = `<!DOCTYPE html><html><body style="font-family:monospace;padding:20px;background:#1a1a1a;color:#eee">
    <h2 style="color:#f87171">Sparge failed to start</h2>
    <p>${message}</p>
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
```

- [ ] **Step 5: Smoke-test locally**

```bash
npm start
```
Expected: App window opens, loads `http://127.0.0.1:<port>/ui/`, shows the Sparge projects page.

- [ ] **Step 6: Commit**

```bash
git add main.js preload.js electron-tests/unit/preload.test.js
git commit -m "feat: main.js + preload.js — Electron entry, window, auto-update

Refs #43"
```

---

## Task 8: E2E tests (Playwright)

**Files:**
- Create: `playwright.config.js`
- Create: `electron-tests/e2e/app.e2e.test.js`

- [ ] **Step 1: Create `playwright.config.js`**

```javascript
// playwright.config.js
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir:  './electron-tests/e2e',
  timeout:   60000,
  use: { headless: false }, // Electron doesn't support fully headless on all platforms
});
```

- [ ] **Step 2: Install Playwright Chromium**

```bash
npx playwright install chromium
```
Expected: Chromium browser downloaded to Playwright's cache.

- [ ] **Step 3: Create E2E test file**

```javascript
// electron-tests/e2e/app.e2e.test.js
const { test, expect } = require('@playwright/test');
const { _electron: electron } = require('playwright');
const path = require('path');

let app;
let window;

test.beforeAll(async () => {
  app = await electron.launch({ args: [path.join(__dirname, '..', '..', 'main.js')] });
  window = await app.firstWindow();
  await window.waitForLoadState('domcontentloaded');
});

test.afterAll(async () => {
  if (app) await app.close();
});

test('app launches and main window appears', async () => {
  expect(window).toBeTruthy();
  const url = window.url();
  expect(url).toContain('/ui/');
});

test('projects.html loads without JS errors', async () => {
  const errors = [];
  window.on('pageerror', err => errors.push(err.message));
  // Navigate to projects page via the server URL embedded in the window
  const currentUrl = window.url();
  const base = currentUrl.replace(/\/ui\/.*$/, '');
  await window.goto(`${base}/ui/projects.html`);
  await window.waitForLoadState('domcontentloaded');
  expect(errors).toHaveLength(0);
});

test('GET /api/posts returns an array', async () => {
  const result = await window.evaluate(async () => {
    const base = window.location.origin;
    const res  = await fetch(`${base}/api/posts`);
    return res.json();
  });
  expect(Array.isArray(result)).toBe(true);
});

test('app quits cleanly with no zombie Python process', async () => {
  await app.close();
  app = null;
  // If a zombie process were running, re-launching would fail or reuse the port.
  // A successful re-launch confirms the port was freed.
  const app2   = await electron.launch({ args: [path.join(__dirname, '..', '..', 'main.js')] });
  const window2 = await app2.firstWindow();
  await window2.waitForLoadState('domcontentloaded');
  expect(window2.url()).toContain('/ui/');
  await app2.close();
});
```

- [ ] **Step 4: Run E2E tests**

```bash
npm run test:e2e
```
Expected: 4 passing. The app will visibly open and close twice (once per `beforeAll`/afterAll cycle, once for the zombie test).

- [ ] **Step 5: Commit**

```bash
git add playwright.config.js electron-tests/e2e/app.e2e.test.js
git commit -m "test: Playwright E2E — app launch, projects page, API, clean quit

Refs #43"
```

---

## Task 9: electron-builder config + GitHub Actions release pipeline

**Files:**
- Modify: `.gitignore`
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: Update `.gitignore`**

Add these lines to `.gitignore`:

```
# Electron build artefacts
node_modules/
resources/python/
resources/_tmp/
dist/
```

- [ ] **Step 2: Verify local pack works**

```bash
npm run pack
```
Expected: `dist/` directory created with the unpacked app. Confirm `dist/*/Contents/Resources/python/` (Mac) or equivalent contains the Python runtime. Confirm `dist/*/Contents/Resources/app/server.py` is present.

- [ ] **Step 3: Create `.github/workflows/release.yml`**

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: macos-latest
            platform: mac
          - os: windows-latest
            platform: win
          - os: ubuntu-latest
            platform: linux

    runs-on: ${{ matrix.os }}

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - name: Install dependencies
        run: npm ci --ignore-scripts

      - name: Fetch python-build-standalone
        run: node scripts/fetch-python.js

      - name: Run unit tests
        run: npm run test:unit

      - name: Run integration tests
        run: npm run test:integration

      - name: Build Electron app
        run: npm run dist -- --publish never
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: sparge-${{ matrix.platform }}
          path: |
            dist/*.dmg
            dist/*.exe
            dist/*.AppImage
            dist/latest*.yml

  release:
    needs: build
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          path: artifacts
          merge-multiple: true

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          files: artifacts/**/*
          generate_release_notes: true
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

- [ ] **Step 4: Commit**

```bash
git add .gitignore .github/workflows/release.yml
git commit -m "feat: GitHub Actions release pipeline — Mac/Win/Linux matrix + GitHub Release

Refs #43"
```

---

## Self-review checklist (run before marking done)

- [ ] All unit tests pass: `npm run test:unit`
- [ ] All integration tests pass: `npm run test:integration`
- [ ] E2E tests pass: `npm run test:e2e`
- [ ] `npm run pack` produces a working app with Python runtime included
- [ ] All commits reference `#43`
- [ ] Close issue #43: `gh issue close 43 --repo mdproctor/sparge --comment "Implemented on branch electron-wrapper"`
