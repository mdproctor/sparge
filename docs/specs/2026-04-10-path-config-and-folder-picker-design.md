# Spec: Path Configuration & Folder Picker

**Date:** 2026-04-10
**Status:** Approved

---

## Overview

Two related changes:

1. **Bug fixes** — remove all hardcoded machine-specific paths from Python scripts and tests
2. **Folder picker** — add native file dialog buttons to the local project creation form; make path fields read-only (ghosted) in the config panel after creation

---

## Scope

### Bug Fixes

| File | Issue | Fix |
|------|-------|-----|
| `scripts/convert_post.py:8` | `ROOT = Path('/Users/mdproctor/...')` hardcoded | Read from `cfg['_root']` (the project's resolved serve_root) |
| `server.py` | `save_cfg` called but not imported | Add `save` to imports from `scripts.config` |
| `server.py:_api_projects_create` | Uses `ROOT.parent` as default serve_root | Default to `str(Path.home())` |
| `tests/test_convert_post.py` | Hardcoded absolute paths in test fixtures | Use `pytest.importorskip` / skip if paths absent; resolve from config API |
| `tests/test_md_generate_current.py:445` | `sys.path.insert(0, '/Users/mdproctor/...')` | Replace with `Path(__file__).parent.parent / 'scripts'` |

### Path Resolution Fix (`scripts/config.py`)

Currently `_md_dir` is always computed as `serve_root / output.md_dir`. If `md_dir` is an absolute path (user browsed outside serve_root), this silently produces a wrong path. Fix: detect absolute paths and use them as-is.

```python
raw_md = cfg.get('output', {}).get('md_dir', 'output/md')
md_path = Path(raw_md)
cfg['_md_dir'] = md_path if md_path.is_absolute() else root / raw_md
```

Apply the same pattern to `posts_dir` and `assets_dir`.

---

## Folder Picker

### Where

Local project creation form only (`ui/projects.html`). Four fields get a browse button:

| Field | Label | Dialog starts at |
|-------|-------|-----------------|
| `serve_root` | Serve root | Home dir |
| `posts_dir` | Posts dir | `serve_root` if set, else home |
| `assets_dir` | Assets dir | `serve_root` if set, else home |
| `md_dir` | MD output dir | `serve_root` if set, else home |

### Path storage rule

After the user selects a folder:
- If selected path is **inside** `serve_root` → store the **relative** portion (e.g. `legacy/posts`)
- If selected path is **outside** `serve_root` (or `serve_root` not yet set) → store the **absolute** path

### Layout

Each path field becomes a row:
```
[  text input (flex: 1)  ] [ 📁 Browse… ]
```

The text input remains editable — the browse button is a shortcut, not a replacement.

### Config panel (read-only after creation)

Path fields in `ui/index.html` config panel (`serve_root`, `source.posts_dir`, `source.assets_dir`, `output.md_dir`) become read-only:
- Rendered as `<input readonly>` with `opacity: 0.5` and `cursor: default`
- A small label below each field: *"Set at project creation — create a new project to change"*
- Non-path fields (`project_name`, `filter.author`, `server.port`) remain editable

---

## Electron IPC

### New IPC channel: `dialog:openDir`

**`main.js`** — add handler:
```javascript
ipcMain.handle('dialog:openDir', async (_event, defaultPath) => {
  const { canceled, filePaths } = await dialog.showOpenDialog({
    properties: ['openDirectory'],
    defaultPath: defaultPath || app.getPath('home'),
  });
  return canceled ? null : filePaths[0];
});
```

**`preload.js`** — expose to renderer:
```javascript
openDir: (defaultPath) => ipcRenderer.invoke('dialog:openDir', defaultPath),
```

**`ui/projects.html`** — call from browse buttons:
```javascript
async function browseDir(defaultPath) {
  if (window.sparge?.openDir) {
    return await window.sparge.openDir(defaultPath);
  }
  return null; // browser mode: no-op
}
```

Browse buttons are rendered regardless of environment. In browser mode (no `window.sparge`), clicking the button does nothing — the text input is the fallback.

---

## Testing Strategy

Testing is the most important part of this feature — path logic across relative/absolute/Electron-IPC/browser is easy to get wrong silently.

### Unit tests — path resolution (`tests/test_path_resolution.py`)

```
- resolve_md_dir: relative path inside serve_root → joined correctly
- resolve_md_dir: absolute path outside serve_root → used as-is
- resolve_md_dir: absolute path that happens to be inside serve_root → still used as-is (absolute wins)
- resolve_posts_dir: same three cases
- resolve_assets_dir: same three cases
- config._resolve: end-to-end with mixed absolute/relative fields
```

### Unit tests — browse path logic (`electron-tests/unit/browse-path.test.js`)

```
- computeStoredPath: selected inside serve_root → returns relative
- computeStoredPath: selected outside serve_root → returns absolute
- computeStoredPath: serve_root not yet set → returns absolute
- computeStoredPath: selected path equals serve_root → returns '.'
- computeStoredPath: Windows paths (if applicable)
```

### Unit tests — IPC handler (`electron-tests/unit/dialog-ipc.test.js`)

```
- dialog:openDir: returns null when user cancels
- dialog:openDir: returns selected path when user confirms
- dialog:openDir: uses defaultPath when provided
- dialog:openDir: falls back to home dir when defaultPath is null/undefined
```

### Integration tests — config API

```
- POST /api/projects with absolute md_dir → config.json stores absolute path
- POST /api/projects with relative md_dir → config.json stores relative path
- GET /api/config after project with absolute md_dir → _md_dir resolves correctly
- save_cfg works (regression: import was missing)
```

### E2E tests — project creation form (`electron-tests/e2e/`)

```
- Browse button present on all four path fields
- In browser mode (no window.sparge): clicking browse does nothing, text input still works
- Config panel path fields are readonly (cannot type into them)
- Config panel non-path fields remain editable
```

### Regression — existing tests

```
- test_convert_post.py: no hardcoded paths; skips cleanly when paths absent
- test_md_generate_current.py: sys.path uses relative resolution; passes on fresh machine
```

---

## Out of Scope

- Browsing inside the Electron app shell (covered by native OS dialog)
- Path validation beyond existence checking at project creation time
- Editing paths after project creation (create a new project instead)
- Ingest mode path fields (ingest derives paths from the blog URL)

---

## Issues

Epic: TBD (new epic or under #11 Sparge Application Foundation)
Child issue: TBD — create before implementation begins
