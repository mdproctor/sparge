# Path Config & Folder Picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all hardcoded machine-specific paths, fix a missing import bug, add native folder-picker buttons to the local project creation form, and make path fields read-only in the config panel.

**Architecture:** Bug fixes touch Python scripts and tests directly. The folder picker adds one Electron IPC channel (`dialog:openDir`), a shared `ui/browse-utils.js` module (for testable path logic), browse buttons wired into `ui/projects.html`, and read-only styling in `ui/index.html`. Path resolution in `scripts/config.py` is hardened to handle absolute paths coming from the new picker.

**Tech Stack:** Python (pytest), Node/Jest (unit), Playwright (E2E), Electron `dialog` API.

**Issues:** Create epic + child issue before starting. Reference `Refs #<N>` in all commits.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `scripts/config.py` | Modify | Handle absolute paths in `_resolve()` |
| `scripts/convert_post.py` | Modify | Remove hardcoded `ROOT`; read from `cfg` in `__main__` only |
| `server.py` | Modify | Add `save` to config import; default `serve_root` to `Path.home()` |
| `tests/test_path_resolution.py` | Create | Unit tests for `_resolve()` with absolute/relative combos |
| `tests/test_convert_post.py` | Modify | Remove hardcoded absolute paths |
| `tests/test_md_generate_current.py` | Modify | Fix hardcoded `sys.path.insert` |
| `ui/browse-utils.js` | Create | `computeStoredPath(selected, serveRoot)` — pure function, unit-testable |
| `ui/projects.html` | Modify | Browse buttons + `browseField()` / `browseDir()` helpers |
| `ui/index.html` | Modify | Make path fields readonly + ghosted |
| `main.js` | Modify | Add `dialog:openDir` IPC handler |
| `preload.js` | Modify | Expose `openDir` via contextBridge |
| `electron-tests/unit/browse-path.test.js` | Create | Unit tests for `computeStoredPath` |
| `electron-tests/unit/dialog-ipc.test.js` | Create | Source-level tests for IPC handler + preload |

---

## Task 1: Fix `scripts/config.py` — handle absolute paths in `_resolve()`

**Files:**
- Modify: `scripts/config.py:15-24`
- Create: `tests/test_path_resolution.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_path_resolution.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

def _make_cfg(serve_root, posts_dir, assets_dir, md_dir):
    """Build a minimal raw config dict for _resolve() testing."""
    from config import _resolve, _cfg_path
    import config as _cfg_mod
    # Point _cfg_path to a temp location so _enriched_dir resolves safely
    orig = _cfg_mod._cfg_path
    _cfg_mod._cfg_path = Path('/tmp/fake/config.json')
    try:
        return _resolve({
            'serve_root': serve_root,
            'source': {'posts_dir': posts_dir, 'assets_dir': assets_dir},
            'output': {'md_dir': md_dir},
        })
    finally:
        _cfg_mod._cfg_path = orig

class TestResolveRelativePaths:
    def test_relative_md_dir_joins_serve_root(self):
        result = _make_cfg('/srv/blog', 'posts', 'assets', 'out/md')
        assert result['_md_dir'] == Path('/srv/blog/out/md')

    def test_relative_posts_dir_joins_serve_root(self):
        result = _make_cfg('/srv/blog', 'legacy/posts', 'assets', 'out/md')
        assert result['_posts_dir'] == Path('/srv/blog/legacy/posts')

    def test_relative_assets_dir_joins_serve_root(self):
        result = _make_cfg('/srv/blog', 'posts', 'legacy/assets', 'out/md')
        assert result['_assets_dir'] == Path('/srv/blog/legacy/assets')

class TestResolveAbsolutePaths:
    def test_absolute_md_dir_used_as_is(self):
        result = _make_cfg('/srv/blog', 'posts', 'assets', '/external/output')
        assert result['_md_dir'] == Path('/external/output')

    def test_absolute_posts_dir_used_as_is(self):
        result = _make_cfg('/srv/blog', '/data/posts', 'assets', 'out/md')
        assert result['_posts_dir'] == Path('/data/posts')

    def test_absolute_assets_dir_used_as_is(self):
        result = _make_cfg('/srv/blog', 'posts', '/data/assets', 'out/md')
        assert result['_assets_dir'] == Path('/data/assets')

    def test_absolute_inside_serve_root_still_used_as_is(self):
        """An absolute path that happens to be inside serve_root stays absolute."""
        result = _make_cfg('/srv/blog', 'posts', 'assets', '/srv/blog/markdown')
        assert result['_md_dir'] == Path('/srv/blog/markdown')
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/claude/sparge
python3 -m pytest tests/test_path_resolution.py -v
```
Expected: 7 failures (absolute path tests will get joined incorrectly)

- [ ] **Step 3: Fix `_resolve()` in `scripts/config.py`**

Replace lines 15–24:

```python
def _resolve(raw: dict) -> dict:
    """Resolve source/output paths against serve_root.

    Paths that are already absolute are used as-is.
    Relative paths are joined to serve_root.
    """
    root = Path(raw['serve_root'])
    raw['_root'] = root

    def _res(p: str) -> Path:
        path = Path(p)
        return path if path.is_absolute() else root / path

    raw['_posts_dir']    = _res(raw['source']['posts_dir'])
    raw['_assets_dir']   = _res(raw['source']['assets_dir'])
    raw['_md_dir']       = _res(raw['output']['md_dir'])
    raw['_enriched_dir'] = Path(_cfg_path).parent / 'enriched'
    return raw
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_path_resolution.py -v
```
Expected: 7 passing

- [ ] **Step 5: Run full suite to confirm no regressions**

```bash
python3 -m pytest tests/ -q --tb=no
```
Expected: same pre-existing failures, no new ones

- [ ] **Step 6: Commit**

```bash
git add scripts/config.py tests/test_path_resolution.py
git commit -m "fix: config._resolve handles absolute paths for md_dir, posts_dir, assets_dir

Refs #<N>"
```

---

## Task 2: Fix `server.py` — missing import + hardcoded default path

**Files:**
- Modify: `server.py:51` (import line)
- Modify: `server.py:396` (`_api_projects_create`)

- [ ] **Step 1: Write the failing tests**

```python
# Add to tests/test_server_port_arg.py (or create tests/test_server_fixes.py)
import os, subprocess, sys, time, urllib.request, json

def _start_server(port):
    proc = subprocess.Popen(
        [sys.executable, 'server.py', '--port', str(port)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=os.path.join(os.path.dirname(__file__), '..')
    )
    for _ in range(30):
        try:
            urllib.request.urlopen(f'http://localhost:{port}/api/config', timeout=1)
            return proc
        except Exception:
            time.sleep(0.5)
    raise AssertionError(f'Server did not start on port {port}')

def test_projects_create_default_serve_root_is_home():
    """POST /api/projects without serve_root should default to home dir, not a hardcoded path."""
    import pathlib
    port = 19877
    proc = _start_server(port)
    try:
        resp = urllib.request.urlopen(
            urllib.request.Request(
                f'http://localhost:{port}/api/projects',
                data=json.dumps({'name': 'test-default-root'}).encode(),
                headers={'Content-Type': 'application/json'},
                method='POST',
            ), timeout=5
        )
        data = json.loads(resp.read())
        assert 'id' in data

        # Read the created config.json
        import pathlib
        projects_dir = pathlib.Path.home() / 'sparge-projects'
        config_path = projects_dir / data['id'] / 'config.json'
        assert config_path.exists()
        config = json.loads(config_path.read_text())
        # serve_root should be home dir, not a hardcoded path
        assert config['serve_root'] == str(pathlib.Path.home())
        assert '/mdproctor/' not in config['serve_root']
    finally:
        proc.terminate()
        proc.wait(timeout=5)
        # Cleanup test project
        import shutil
        test_dir = pathlib.Path.home() / 'sparge-projects' / 'test-default-root'
        if test_dir.exists():
            shutil.rmtree(test_dir)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_server_fixes.py::test_projects_create_default_serve_root_is_home -v
```
Expected: FAIL (serve_root contains `/mdproctor/`)

- [ ] **Step 3: Fix `server.py`**

**Fix 1** — line 51, add `save` to the config import:
```python
from scripts.config import cfg, set_config_path, save as save_cfg
```

**Fix 2** — line 396 in `_api_projects_create`, change:
```python
'serve_root':   data.get('serve_root', str(ROOT.parent)),
```
to:
```python
'serve_root':   data.get('serve_root', str(Path.home())),
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_server_fixes.py::test_projects_create_default_serve_root_is_home -v
```
Expected: PASS

- [ ] **Step 5: Run full suite**

```bash
python3 -m pytest tests/ -q --tb=no
```
Expected: same pre-existing failures, no new ones

- [ ] **Step 6: Commit**

```bash
git add server.py tests/test_server_fixes.py
git commit -m "fix: server.py — import save_cfg, default serve_root to home dir

Refs #<N>"
```

---

## Task 3: Fix `scripts/convert_post.py` — remove hardcoded ROOT

**Files:**
- Modify: `scripts/convert_post.py:8` and `scripts/convert_post.py:649-656`

`ROOT` is **only used in the `__main__` CLI block** (lines 649-656) as a default path when no argument is given. The `convert_post()` function itself does not use `ROOT`. Fix: remove the module-level constant and read `cfg['_root']` inside `__main__`.

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_server_fixes.py

def test_convert_post_root_not_hardcoded():
    """convert_post.py must not contain a hardcoded absolute path as ROOT."""
    from pathlib import Path
    src = (Path(__file__).parent.parent / 'scripts' / 'convert_post.py').read_text()
    assert '/Users/' not in src.split('if __name__')[0], \
        "Hardcoded absolute path found in module-level code of convert_post.py"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_server_fixes.py::test_convert_post_root_not_hardcoded -v
```
Expected: FAIL

- [ ] **Step 3: Fix `scripts/convert_post.py`**

Remove line 8 (`ROOT = Path('/Users/mdproctor/mdproctor.github.io')`).

Replace the `if __name__ == '__main__':` block (lines ~649-656) with:

```python
if __name__ == '__main__':
    from scripts.config import cfg
    _root = cfg['_root']
    html = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        _root / 'legacy/posts/mark-proctor/2006-05-31-what-is-a-rule-engine.html'
    )
    result = convert_post(html)
    out = _root / 'mark-proctor' / (html.stem + '.md')
    out.parent.mkdir(exist_ok=True)
    out.write_text(result, encoding='utf-8')
    print(f'Written: {out}')
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_server_fixes.py::test_convert_post_root_not_hardcoded -v
```
Expected: PASS

- [ ] **Step 5: Run full suite**

```bash
python3 -m pytest tests/ -q --tb=no
```
Expected: same pre-existing failures, no new ones

- [ ] **Step 6: Commit**

```bash
git add scripts/convert_post.py tests/test_server_fixes.py
git commit -m "fix: convert_post.py — remove hardcoded ROOT, read from cfg in CLI block

Refs #<N>"
```

---

## Task 4: Fix hardcoded paths in tests

**Files:**
- Modify: `tests/test_convert_post.py` (hardcoded path at line ~593)
- Modify: `tests/test_md_generate_current.py:454`

- [ ] **Step 1: Fix `tests/test_md_generate_current.py:454`**

Find line 454:
```python
sys.path.insert(0, '/Users/mdproctor/claude/sparge/scripts')
```

Replace with:
```python
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
```

(The `from pathlib import Path` import is already on line 453.)

- [ ] **Step 2: Find and fix hardcoded paths in `tests/test_convert_post.py`**

Search for hardcoded paths:
```bash
grep -n '/Users/' tests/test_convert_post.py
```

For each occurrence, wrap the test in a skip guard. The standard pattern for tests requiring local data that may not exist on all machines:

```python
import pytest
from pathlib import Path

_KIE_POSTS = Path('/Users/mdproctor/mdproctor.github.io/legacy/posts/mark-proctor')
pytestmark_kie = pytest.mark.skipif(
    not _KIE_POSTS.exists(),
    reason="KIE archive not present on this machine"
)
```

Then decorate the affected test classes/functions with `@pytestmark_kie`. The paths remain in the test (for documentation) but the test skips cleanly on machines where they don't exist.

- [ ] **Step 3: Verify tests run without error**

```bash
python3 -m pytest tests/test_convert_post.py tests/test_md_generate_current.py -v --tb=short 2>&1 | head -40
```
Expected: Tests either pass or skip — no errors about missing paths.

- [ ] **Step 4: Commit**

```bash
git add tests/test_convert_post.py tests/test_md_generate_current.py
git commit -m "fix: remove hardcoded absolute paths from test files

Refs #<N>"
```

---

## Task 5: Create `ui/browse-utils.js` — path computation module

**Files:**
- Create: `ui/browse-utils.js`
- Create: `electron-tests/unit/browse-path.test.js`

This is a pure function — no Electron, no DOM — so it's trivially unit-testable.

- [ ] **Step 1: Write the failing unit tests**

```javascript
// electron-tests/unit/browse-path.test.js
const { computeStoredPath } = require('../../ui/browse-utils');

describe('computeStoredPath', () => {
  test('selected inside serve_root → returns relative path', () => {
    expect(computeStoredPath('/srv/blog/legacy/posts', '/srv/blog'))
      .toBe('legacy/posts');
  });

  test('selected is serve_root itself → returns dot', () => {
    expect(computeStoredPath('/srv/blog', '/srv/blog')).toBe('.');
  });

  test('selected outside serve_root → returns absolute path', () => {
    expect(computeStoredPath('/other/dir/posts', '/srv/blog'))
      .toBe('/other/dir/posts');
  });

  test('no serve_root set (null) → returns absolute path', () => {
    expect(computeStoredPath('/any/path', null)).toBe('/any/path');
  });

  test('no serve_root set (empty string) → returns absolute path', () => {
    expect(computeStoredPath('/any/path', '')).toBe('/any/path');
  });

  test('trailing slashes are normalised', () => {
    expect(computeStoredPath('/srv/blog/posts/', '/srv/blog/'))
      .toBe('posts');
  });

  test('deeply nested path returns full relative chain', () => {
    expect(computeStoredPath('/srv/blog/a/b/c', '/srv/blog'))
      .toBe('a/b/c');
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/claude/sparge
npm run test:unit -- --testPathPattern=browse-path
```
Expected: FAIL — `Cannot find module '../../ui/browse-utils'`

- [ ] **Step 3: Create `ui/browse-utils.js`**

```javascript
// ui/browse-utils.js
'use strict';

/**
 * Compute the path to store in config after the user picks a folder.
 *
 * Rules:
 *   - If selected is inside serveRoot  → store relative path
 *   - If selected equals serveRoot     → store '.'
 *   - If selected is outside serveRoot → store absolute path
 *   - If serveRoot is not set          → store absolute path
 *
 * @param {string} selectedPath  Absolute path returned by the OS dialog
 * @param {string|null} serveRoot  Current value of the serve_root field
 * @returns {string}
 */
function computeStoredPath(selectedPath, serveRoot) {
  if (!serveRoot) return selectedPath;

  const norm = (p) => p.replace(/\\/g, '/').replace(/\/$/, '');
  const sel  = norm(selectedPath);
  const root = norm(serveRoot);

  if (sel === root) return '.';
  if (sel.startsWith(root + '/')) return sel.slice(root.length + 1);
  return selectedPath;
}

if (typeof module !== 'undefined') module.exports = { computeStoredPath };
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npm run test:unit -- --testPathPattern=browse-path
```
Expected: 7 passing

- [ ] **Step 5: Commit**

```bash
git add ui/browse-utils.js electron-tests/unit/browse-path.test.js
git commit -m "feat: browse-utils.js — computeStoredPath for relative/absolute path logic

Refs #<N>"
```

---

## Task 6: Electron IPC — `dialog:openDir` + unit tests

**Files:**
- Modify: `main.js:3` (add `dialog` import) and `main.js:100-101` (add handler)
- Modify: `preload.js:4-9` (add `openDir`)
- Create: `electron-tests/unit/dialog-ipc.test.js`

- [ ] **Step 1: Write the unit tests (source-level)**

```javascript
// electron-tests/unit/dialog-ipc.test.js
const fs   = require('fs');
const path = require('path');

const mainSrc    = fs.readFileSync(path.join(__dirname, '..', '..', 'main.js'), 'utf8');
const preloadSrc = fs.readFileSync(path.join(__dirname, '..', '..', 'preload.js'), 'utf8');

describe('main.js dialog:openDir handler', () => {
  test('dialog is imported from electron', () => {
    expect(mainSrc).toMatch(/const\s*\{[^}]*dialog[^}]*\}\s*=\s*require\('electron'\)/);
  });

  test('dialog:openDir ipcMain handler is registered', () => {
    expect(mainSrc).toContain("'dialog:openDir'");
  });

  test('handler calls showOpenDialog with openDirectory property', () => {
    expect(mainSrc).toContain('showOpenDialog');
    expect(mainSrc).toContain("'openDirectory'");
  });

  test('handler uses app.getPath(home) as fallback defaultPath', () => {
    expect(mainSrc).toContain("app.getPath('home')");
  });

  test('handler returns null on cancel', () => {
    expect(mainSrc).toContain('canceled');
    expect(mainSrc).toContain('null');
  });
});

describe('preload.js openDir', () => {
  test('exposes openDir via contextBridge', () => {
    expect(preloadSrc).toContain('openDir');
  });

  test('openDir invokes dialog:openDir channel', () => {
    expect(preloadSrc).toContain("'dialog:openDir'");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
npm run test:unit -- --testPathPattern=dialog-ipc
```
Expected: 7 failures

- [ ] **Step 3: Update `main.js`**

Line 3 — add `dialog` to the destructured import:
```javascript
const { app, BrowserWindow, ipcMain, dialog } = require('electron');
```

After line 101 (`ipcMain.on('update:install', ...)`), add:
```javascript
ipcMain.handle('dialog:openDir', async (_event, defaultPath) => {
  const { canceled, filePaths } = await dialog.showOpenDialog({
    properties: ['openDirectory'],
    defaultPath: defaultPath || app.getPath('home'),
  });
  return canceled ? null : filePaths[0];
});
```

- [ ] **Step 4: Update `preload.js`**

Add `openDir` to the `exposeInMainWorld` object:
```javascript
contextBridge.exposeInMainWorld('sparge', {
  getVersion:         () => ipcRenderer.invoke('app:version'),
  onUpdateAvailable:  (fn) => ipcRenderer.on('update:available',  (_, info) => fn(info)),
  onUpdateDownloaded: (fn) => ipcRenderer.on('update:downloaded', (_, info) => fn(info)),
  installUpdate:      () => ipcRenderer.send('update:install'),
  openDir:            (defaultPath) => ipcRenderer.invoke('dialog:openDir', defaultPath),
});
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
npm run test:unit -- --testPathPattern=dialog-ipc
```
Expected: 7 passing

- [ ] **Step 6: Run all unit tests**

```bash
npm run test:unit
```
Expected: all passing

- [ ] **Step 7: Commit**

```bash
git add main.js preload.js electron-tests/unit/dialog-ipc.test.js
git commit -m "feat: Electron dialog:openDir IPC — native folder picker

Refs #<N>"
```

---

## Task 7: UI — browse buttons in `ui/projects.html`

**Files:**
- Modify: `ui/projects.html` (local form HTML + JavaScript)

The `<script src="/ui/browse-utils.js">` tag must be added. Browse buttons appear on all four path fields. In browser mode (`window.sparge` absent), clicking the button is a no-op.

- [ ] **Step 1: Add `browse-utils.js` script tag to `ui/projects.html`**

Find the closing `</head>` tag and add before it:
```html
<script src="/ui/browse-utils.js"></script>
```

- [ ] **Step 2: Add `browseDir()` and `browseField()` helper functions**

In the JavaScript section, add after the existing helper functions (near `showErr`):

```javascript
async function browseDir(defaultPath) {
  if (window.sparge && window.sparge.openDir) {
    return await window.sparge.openDir(defaultPath || null);
  }
  return null; // browser mode — no-op
}

async function browseField(inputId, relativeToId) {
  const defaultPath = relativeToId
    ? ($$(relativeToId).value.trim() || null)
    : null;
  const selected = await browseDir(defaultPath);
  if (!selected) return;
  const input = $$(inputId);
  if (relativeToId) {
    const serveRoot = $$(relativeToId).value.trim();
    input.value = computeStoredPath(selected, serveRoot);
  } else {
    input.value = selected;
  }
}
```

(Note: `$$` is the existing `$` alias for `document.getElementById` in this file; adjust if needed. Check the existing alias — it may be `$` — and use whichever is consistent.)

- [ ] **Step 3: Add browse buttons to the four path fields**

Find the local form HTML. Replace each path field's `<input>` with a row containing the input + button.

**Serve root field** — replace:
```html
<input id="l-root" type="text" placeholder="/Users/you/blog-archive"
  onfocus="this.style.borderColor='var(--accent)'" onblur="this.style.borderColor=''">
<div class="note">Static files are served from this directory</div>
```
with:
```html
<div style="display:flex;gap:6px;align-items:center">
  <input id="l-root" type="text" placeholder="/Users/you/blog-archive" style="flex:1"
    onfocus="this.style.borderColor='var(--accent)'" onblur="this.style.borderColor=''">
  <button type="button" onclick="browseField('l-root', null)" title="Browse for folder"
    style="padding:5px 10px;white-space:nowrap;flex-shrink:0">📁</button>
</div>
<div class="note">Static files are served from this directory. Starts at your home folder.</div>
```

**Posts dir field** — replace the `<input id="l-posts">` with:
```html
<div style="display:flex;gap:6px;align-items:center">
  <input id="l-posts" type="text" placeholder="posts" style="flex:1"
    onfocus="this.style.borderColor='var(--accent)'" onblur="this.style.borderColor=''">
  <button type="button" onclick="browseField('l-posts', 'l-root')" title="Browse for folder"
    style="padding:5px 10px;flex-shrink:0">📁</button>
</div>
```

**Assets dir field** — replace the `<input id="l-assets">` with:
```html
<div style="display:flex;gap:6px;align-items:center">
  <input id="l-assets" type="text" placeholder="assets" style="flex:1"
    onfocus="this.style.borderColor='var(--accent)'" onblur="this.style.borderColor=''">
  <button type="button" onclick="browseField('l-assets', 'l-root')" title="Browse for folder"
    style="padding:5px 10px;flex-shrink:0">📁</button>
</div>
```

**MD output dir field** — replace the `<input id="l-md">` with:
```html
<div style="display:flex;gap:6px;align-items:center">
  <input id="l-md" type="text" placeholder="markdown" style="flex:1"
    onfocus="this.style.borderColor='var(--accent)'" onblur="this.style.borderColor=''">
  <button type="button" onclick="browseField('l-md', 'l-root')" title="Browse for folder"
    style="padding:5px 10px;flex-shrink:0">📁</button>
</div>
```

- [ ] **Step 4: Smoke test in the Electron app**

```bash
npm start
```
Open Projects → Local Archive tab. Verify:
- All four 📁 buttons appear alongside path fields
- Clicking 📁 on Serve root opens a native folder picker starting at home dir
- Clicking 📁 on Posts/Assets/MD opens picker starting at serve_root value (if set)
- Selecting a folder inside serve_root fills in the relative path
- Selecting a folder outside serve_root fills in the absolute path
- Clicking 📁 in a browser tab does nothing (text input still works)

- [ ] **Step 5: Commit**

```bash
git add ui/projects.html ui/browse-utils.js
git commit -m "feat: browse buttons on all path fields in local project creation form

Refs #<N>"
```

---

## Task 8: UI — read-only path fields in `ui/index.html` config panel

**Files:**
- Modify: `ui/index.html` (config panel inputs)

Path fields are shown ghosted (readable, clearly not interactive). Non-path fields remain editable.

- [ ] **Step 1: Find the config panel inputs in `ui/index.html`**

```bash
grep -n 'cfg-root\|cfg-posts\|cfg-assets\|cfg-md\|cfg-name\|cfg-author' ui/index.html | head -20
```

Note the line numbers for the four path inputs (`cfg-root`, `cfg-posts`, `cfg-assets`, `cfg-md`).

- [ ] **Step 2: Add `readonly` + ghost styling to path inputs**

For each of the four path inputs (`cfg-root`, `cfg-posts`, `cfg-assets`, `cfg-md`), add:
- `readonly` attribute
- `style="opacity:0.5;cursor:default"`
- `title="Set at project creation — create a new project to change paths"`

Example — change:
```html
<input id="cfg-root" type="text" ...>
```
to:
```html
<input id="cfg-root" type="text" readonly
  style="opacity:0.5;cursor:default"
  title="Set at project creation — create a new project to change paths"
  ...>
```

Apply the same change to `cfg-posts`, `cfg-assets`, and `cfg-md`.

Leave `cfg-name`, `cfg-author`, and any port/server fields untouched.

- [ ] **Step 3: Add a note below the path fields block**

After the four path field rows, add:
```html
<div class="note" style="margin-top:4px;opacity:0.65">
  Paths are locked at project creation. To use different paths, create a new project.
</div>
```

- [ ] **Step 4: Smoke test**

```bash
npm start
```
Open a project → Settings panel. Verify:
- Path fields (`serve_root`, `posts_dir`, `assets_dir`, `md_dir`) appear greyed out
- Clicking on them does not allow typing
- Hovering shows the tooltip
- Project name and author filter fields remain editable
- The note appears below the path fields

- [ ] **Step 5: Run Electron E2E tests to confirm no regressions**

```bash
npm run test:e2e
```
Expected: 4 passing

- [ ] **Step 6: Commit**

```bash
git add ui/index.html
git commit -m "feat: config panel path fields are read-only — locked at project creation

Refs #<N>"
```

---

## Task 9: GitHub issues + final verification

- [ ] **Step 1: Create epic and child issue**

```bash
# Create epic
gh issue create --repo mdproctor/sparge \
  --title "Project Configuration & Path Management" \
  --label "enhancement,epic" \
  --body "## Overview
Path handling correctness across the app: remove hardcoded machine paths,
fix config resolver to handle absolute paths, add native folder picker to
project creation, lock path fields after creation.

## Scope
- [ ] #TBD — Path config fixes + folder picker V1"

# Create child issue (update TBD after epic is created)
gh issue create --repo mdproctor/sparge \
  --title "fix: hardcoded paths, folder picker at project creation, read-only config panel" \
  --label "enhancement,bug" \
  --body "Implements docs/superpowers/specs/2026-04-10-path-config-and-folder-picker-design.md

Part of epic #<EPIC_N>"
```

- [ ] **Step 2: Run full Python test suite**

```bash
python3 -m pytest tests/ -q --tb=short
```
Expected: same pre-existing failures only

- [ ] **Step 3: Run full JS test suites**

```bash
npm run test:unit && npm run test:integration && npm run test:e2e
```
Expected: all passing

- [ ] **Step 4: Update plan commit references**

Amend the issue number into any commits that used `#<N>` placeholders, or push as-is and note the issue number in a follow-up commit referencing the new issue number.

- [ ] **Step 5: Push to main**

```bash
git push origin main
```
