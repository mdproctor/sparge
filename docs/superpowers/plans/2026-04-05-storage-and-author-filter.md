# Sparge Storage Migration + Author Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Sparge project data out of the repo into `~/sparge-projects/` (configured via `~/.sparge/config.json`), auto-migrate existing data on first startup, and add an author filter dropdown to the UI backed by a `?author=` API param.

**Architecture:** A new `sparge_home.py` module reads `~/.sparge/config.json` and exposes `PROJECTS_DIR`. `server.py` switches `PROJECTS_FILE` and `_project_dir()` to use this. A `_maybe_migrate()` function copies old `blog-migrator/projects/` data on first run. `_api_posts_list()` gains an `author` param. The UI gets a `<select>` that re-fetches `GET /api/posts?author=X` on change.

**Tech Stack:** Python 3.11+, stdlib only (pathlib, shutil, json), pytest, vanilla JS

**Spec:** `blog-migrator/docs/superpowers/specs/2026-04-05-author-filter-design.md`

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `blog-migrator/scripts/sparge_home.py` | **CREATE** | Read `~/.sparge/config.json`, expose `get_projects_dir()` |
| `blog-migrator/tests/test_sparge_home.py` | **CREATE** | Unit tests for home config reading and migration |
| `blog-migrator/server.py` | **MODIFY** | Use `PROJECTS_DIR` from sparge_home; auto-migrate; author param |
| `blog-migrator/ui/index.html` | **MODIFY** | Author `<select>` in filter bar |

---

## Task 1: `sparge_home.py` — read `~/.sparge/config.json`

**Files:**
- Create: `blog-migrator/scripts/sparge_home.py`
- Create: `blog-migrator/tests/test_sparge_home.py`

### Context
`~/.sparge/config.json` holds Sparge app-level config. For now, only `projects_dir` is needed. If the file doesn't exist, default to `~/sparge-projects`. Support `~/` expansion.

- [ ] **Step 1: Write failing tests**

Create `blog-migrator/tests/test_sparge_home.py`:

```python
"""Unit tests for sparge_home.py — ~/.sparge config reading."""
import json
import sys
from pathlib import Path

import pytest

MIGRATOR = Path(__file__).parent.parent
sys.path.insert(0, str(MIGRATOR / 'scripts'))


def test_default_projects_dir_when_no_config(tmp_path, monkeypatch):
    """When ~/.sparge/config.json absent, defaults to ~/sparge-projects."""
    monkeypatch.setenv('HOME', str(tmp_path))
    import importlib, sparge_home
    importlib.reload(sparge_home)
    result = sparge_home.get_projects_dir()
    assert result == tmp_path / 'sparge-projects'


def test_reads_projects_dir_from_config(tmp_path, monkeypatch):
    """When config exists, returns configured path."""
    monkeypatch.setenv('HOME', str(tmp_path))
    custom = tmp_path / 'my-projects'
    sparge_cfg = tmp_path / '.sparge'
    sparge_cfg.mkdir()
    (sparge_cfg / 'config.json').write_text(
        json.dumps({'projects_dir': str(custom)})
    )
    import importlib, sparge_home
    importlib.reload(sparge_home)
    result = sparge_home.get_projects_dir()
    assert result == custom


def test_tilde_expansion_in_projects_dir(tmp_path, monkeypatch):
    """~/path in config.json is expanded relative to HOME."""
    monkeypatch.setenv('HOME', str(tmp_path))
    sparge_cfg = tmp_path / '.sparge'
    sparge_cfg.mkdir()
    (sparge_cfg / 'config.json').write_text(
        json.dumps({'projects_dir': '~/custom-projects'})
    )
    import importlib, sparge_home
    importlib.reload(sparge_home)
    result = sparge_home.get_projects_dir()
    assert result == tmp_path / 'custom-projects'


def test_creates_sparge_dir_and_default_config(tmp_path, monkeypatch):
    """First call creates ~/.sparge/config.json with defaults."""
    monkeypatch.setenv('HOME', str(tmp_path))
    import importlib, sparge_home
    importlib.reload(sparge_home)
    sparge_home.get_projects_dir()
    cfg_path = tmp_path / '.sparge' / 'config.json'
    assert cfg_path.exists()
    data = json.loads(cfg_path.read_text())
    assert 'projects_dir' in data
```

Run: `python3 -m pytest blog-migrator/tests/test_sparge_home.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sparge_home'`

- [ ] **Step 2: Create `blog-migrator/scripts/sparge_home.py`**

```python
"""
Sparge home directory management.

Reads ~/.sparge/config.json to find where project data lives.
Creates the config with defaults on first use.

Public API
----------
get_projects_dir() -> Path   resolved path to the projects directory
"""
from __future__ import annotations

import json
import os
from pathlib import Path


_SPARGE_HOME = Path.home() / '.sparge'
_SPARGE_CFG  = _SPARGE_HOME / 'config.json'
_DEFAULT_PROJECTS_DIR = Path.home() / 'sparge-projects'


def get_projects_dir() -> Path:
    """
    Return the resolved projects directory path.
    Creates ~/.sparge/config.json with defaults if absent.
    """
    _SPARGE_HOME.mkdir(exist_ok=True)
    if not _SPARGE_CFG.exists():
        _SPARGE_CFG.write_text(json.dumps(
            {'projects_dir': str(_DEFAULT_PROJECTS_DIR)},
            indent=2,
        ))
    try:
        data = json.loads(_SPARGE_CFG.read_text())
        raw = data.get('projects_dir', str(_DEFAULT_PROJECTS_DIR))
    except Exception:
        raw = str(_DEFAULT_PROJECTS_DIR)
    return Path(os.path.expanduser(raw))
```

- [ ] **Step 3: Run tests**

Run: `python3 -m pytest blog-migrator/tests/test_sparge_home.py -v`
Expected: All 4 PASS

- [ ] **Step 4: Commit**

```bash
git add blog-migrator/scripts/sparge_home.py blog-migrator/tests/test_sparge_home.py
git commit -m "feat(sparge-home): read ~/.sparge/config.json for projects_dir"
```

---

## Task 2: Migration — copy old projects to `~/sparge-projects/` on first run

**Files:**
- Modify: `blog-migrator/tests/test_sparge_home.py`
- Modify: `blog-migrator/scripts/sparge_home.py`

### Context
If `blog-migrator/projects/` exists and has content but the new `PROJECTS_DIR` does not yet have a `projects.json`, copy everything across automatically. Print a console notice. Never delete the old location.

- [ ] **Step 1: Write failing tests**

Append to `blog-migrator/tests/test_sparge_home.py`:

```python
import shutil


def test_migration_copies_projects_json(tmp_path, monkeypatch):
    """projects.json is copied from old location to new on first run."""
    monkeypatch.setenv('HOME', str(tmp_path))
    old_projects = tmp_path / 'blog-migrator' / 'projects'
    old_projects.mkdir(parents=True)
    (old_projects.parent / 'projects.json').write_text(
        json.dumps([{'id': 'test-proj', 'name': 'Test'}])
    )

    import importlib, sparge_home
    importlib.reload(sparge_home)
    new_dir = tmp_path / 'sparge-projects'
    sparge_home.maybe_migrate(
        old_root=old_projects.parent,
        projects_dir=new_dir,
    )

    assert (new_dir / 'projects.json').exists()
    data = json.loads((new_dir / 'projects.json').read_text())
    assert data[0]['id'] == 'test-proj'


def test_migration_copies_project_dirs(tmp_path, monkeypatch):
    """Project subdirectories are copied with their contents."""
    monkeypatch.setenv('HOME', str(tmp_path))
    old_root = tmp_path / 'blog-migrator'
    old_proj = old_root / 'projects' / 'my-blog'
    old_proj.mkdir(parents=True)
    (old_proj / 'config.json').write_text('{"project_name": "My Blog"}')
    (old_proj / 'state.json').write_text('{}')
    (old_root / 'projects.json').write_text(
        json.dumps([{'id': 'my-blog', 'name': 'My Blog'}])
    )

    new_dir = tmp_path / 'sparge-projects'
    import importlib, sparge_home
    importlib.reload(sparge_home)
    sparge_home.maybe_migrate(old_root=old_root, projects_dir=new_dir)

    assert (new_dir / 'my-blog' / 'config.json').exists()
    assert (new_dir / 'my-blog' / 'state.json').exists()


def test_migration_skipped_if_already_done(tmp_path, monkeypatch):
    """Migration does not overwrite if new projects.json already exists."""
    monkeypatch.setenv('HOME', str(tmp_path))
    old_root = tmp_path / 'blog-migrator'
    (old_root / 'projects').mkdir(parents=True)
    (old_root / 'projects.json').write_text(json.dumps([{'id': 'old'}]))

    new_dir = tmp_path / 'sparge-projects'
    new_dir.mkdir()
    (new_dir / 'projects.json').write_text(json.dumps([{'id': 'new'}]))

    import importlib, sparge_home
    importlib.reload(sparge_home)
    sparge_home.maybe_migrate(old_root=old_root, projects_dir=new_dir)

    data = json.loads((new_dir / 'projects.json').read_text())
    assert data[0]['id'] == 'new'  # not overwritten


def test_migration_no_op_when_old_dir_absent(tmp_path, monkeypatch):
    """maybe_migrate is a no-op when old location doesn't exist."""
    monkeypatch.setenv('HOME', str(tmp_path))
    new_dir = tmp_path / 'sparge-projects'
    import importlib, sparge_home
    importlib.reload(sparge_home)
    sparge_home.maybe_migrate(
        old_root=tmp_path / 'nonexistent',
        projects_dir=new_dir,
    )
    assert not new_dir.exists()
```

Run: `python3 -m pytest blog-migrator/tests/test_sparge_home.py -k migration -v`
Expected: FAIL — `AttributeError: module 'sparge_home' has no attribute 'maybe_migrate'`

- [ ] **Step 2: Add `maybe_migrate()` to `sparge_home.py`**

Append to `blog-migrator/scripts/sparge_home.py`:

```python
def maybe_migrate(old_root: Path, projects_dir: Path) -> bool:
    """
    Copy project data from old_root (blog-migrator/) to projects_dir
    if projects_dir/projects.json does not yet exist.

    Returns True if migration was performed, False otherwise.
    Never deletes the old location.
    """
    old_projects_json = old_root / 'projects.json'
    old_projects_dir  = old_root / 'projects'
    new_projects_json = projects_dir / 'projects.json'

    # Skip if: nothing to migrate, or already migrated
    if not old_projects_json.exists() and not old_projects_dir.exists():
        return False
    if new_projects_json.exists():
        return False

    projects_dir.mkdir(parents=True, exist_ok=True)

    # Copy projects.json
    if old_projects_json.exists():
        import shutil as _shutil
        _shutil.copy2(old_projects_json, new_projects_json)

    # Copy each project subdirectory
    if old_projects_dir.exists():
        for src in old_projects_dir.iterdir():
            if src.is_dir():
                import shutil as _shutil
                _shutil.copytree(src, projects_dir / src.name, dirs_exist_ok=True)

    print(
        f'[Sparge] Migrated project data from {old_root} → {projects_dir}\n'
        f'         Old location kept intact. You may remove it manually.'
    )
    return True
```

- [ ] **Step 3: Run migration tests**

Run: `python3 -m pytest blog-migrator/tests/test_sparge_home.py -v`
Expected: All 8 PASS

- [ ] **Step 4: Commit**

```bash
git add blog-migrator/scripts/sparge_home.py blog-migrator/tests/test_sparge_home.py
git commit -m "feat(sparge-home): auto-migrate projects from blog-migrator/projects/ on first run"
```

---

## Task 3: Wire `server.py` to use `PROJECTS_DIR` and auto-migrate

**Files:**
- Modify: `blog-migrator/server.py`

### Context
Replace the hardcoded `PROJECTS_FILE = ROOT / 'projects.json'` and `_project_dir()` with equivalents that use `PROJECTS_DIR` from `sparge_home`. Call `maybe_migrate()` on startup before loading projects.

- [ ] **Step 1: Import sparge_home and set up `PROJECTS_DIR`**

In `server.py`, after the existing `from scripts.config import cfg, set_config_path` block, add:

```python
from scripts.sparge_home import get_projects_dir, maybe_migrate as _maybe_migrate
```

Replace line 55:
```python
PROJECTS_FILE = ROOT / 'projects.json'
```
with:
```python
PROJECTS_DIR  = get_projects_dir()
PROJECTS_FILE = PROJECTS_DIR / 'projects.json'
```

- [ ] **Step 2: Update `_project_dir()` to use `PROJECTS_DIR`**

Replace the current `_project_dir()` function (line 69):
```python
def _project_dir(project_id: str) -> Path:
    return ROOT / 'projects' / project_id
```
with:
```python
def _project_dir(project_id: str) -> Path:
    return PROJECTS_DIR / project_id
```

- [ ] **Step 3: Call `maybe_migrate()` on startup**

Find the startup block (around line 112) where `_startup_projects = _load_projects()` is called. Add before it:

```python
# ── Auto-migrate from old location on first run ───────────────────────────────
_maybe_migrate(old_root=ROOT, projects_dir=PROJECTS_DIR)
```

- [ ] **Step 4: Update `ENRICHED_DIR` fallback**

Find the fallback line (around line 121):
```python
ENRICHED_DIR: Path = ROOT / 'projects' / 'kie-mark-proctor' / 'enriched'
```
Replace with:
```python
ENRICHED_DIR: Path = PROJECTS_DIR / 'kie-mark-proctor' / 'enriched'
```

- [ ] **Step 5: Run full test suite**

Run: `python3 -m pytest blog-migrator/tests/ -q`
Expected: All 244 tests pass (236 + 8 new sparge_home tests)

- [ ] **Step 6: Smoke test**

Start the server: `python3 blog-migrator/server.py`

Check:
- `~/.sparge/config.json` was created
- `~/sparge-projects/` was created (or migration ran if `blog-migrator/projects/` had data)
- Projects load correctly

- [ ] **Step 7: Commit**

```bash
git add blog-migrator/server.py
git commit -m "feat(server): use PROJECTS_DIR from ~/.sparge/config.json; auto-migrate on startup"
```

---

## Task 4: API author filter — `GET /api/posts?author=X`

**Files:**
- Modify: `blog-migrator/server.py`
- Modify: `blog-migrator/tests/test_server_api.py`

### Context
`_api_posts_list()` currently takes no arguments and returns all posts. We add an `author` parameter: if provided, filter; if absent, fall back to `cfg['filter']['author']`; if that's also empty, return all.

The GET handler already parses `parsed.path` but throws away the query string for `/api/posts`. Pass it through.

- [ ] **Step 1: Write failing tests**

Append to `blog-migrator/tests/test_server_api.py`:

```python
class TestPostsAuthorFilter:
    """GET /api/posts?author=X filters by author."""

    def test_author_param_filters_posts(self, server, tmp_path):
        """?author=X returns only posts with matching author."""
        # Create a project with posts from two authors
        proj_name = f'filter-test-{uuid.uuid4().hex[:6]}'
        payload = {
            'name': proj_name,
            'serve_root': str(tmp_path),
            'posts_dir': 'posts',
            'assets_dir': 'assets',
            'md_dir': 'md',
        }
        r = SESSION_HTTP.post(f'{API}/projects', json=payload)
        assert r.status_code == 200
        proj_id = r.json()['id']

        # Write state.json with two authors
        import json as _json
        from pathlib import Path as _Path
        import sparge_home as _sh
        proj_dir = _sh.get_projects_dir() / proj_id
        state = {
            'post-alice': {'slug': 'post-alice', 'author': 'Alice', 'ingested_at': '2026-01-01'},
            'post-bob':   {'slug': 'post-bob',   'author': 'Bob',   'ingested_at': '2026-01-01'},
        }
        (proj_dir / 'state.json').write_text(_json.dumps(state))

        # Activate
        SESSION_HTTP.post(f'{API}/projects/{proj_id}/activate')

        # Filter by Alice
        r = SESSION_HTTP.get(f'{API}/posts?author=Alice')
        assert r.status_code == 200
        slugs = [p['slug'] for p in r.json()]
        assert 'post-alice' in slugs
        assert 'post-bob' not in slugs

        # Empty author returns all
        r = SESSION_HTTP.get(f'{API}/posts?author=')
        assert r.status_code == 200
        assert len(r.json()) == 2

        # Cleanup
        SESSION_HTTP.delete(f'{API}/projects/{proj_id}')

    def test_no_author_param_returns_all_when_config_empty(self, server):
        """No ?author param and no config filter → all posts returned."""
        r = SESSION_HTTP.get(f'{API}/posts')
        assert r.status_code == 200
        assert isinstance(r.json(), list)
```

Run: `python3 -m pytest blog-migrator/tests/test_server_api.py::TestPostsAuthorFilter -v`
Expected: SKIP (server not running) or FAIL if server is running

- [ ] **Step 2: Update GET handler to pass author param**

In `server.py`'s `do_GET` handler, find:
```python
elif path == '/api/posts':
    self._api_posts_list()
```

Replace with:
```python
elif path == '/api/posts':
    params = dict(urllib.parse.parse_qsl(parsed.query))
    self._api_posts_list(author=params.get('author'))
```

- [ ] **Step 3: Update `_api_posts_list()` to accept and apply `author`**

Replace the current `_api_posts_list()` method:
```python
def _api_posts_list(self):
    posts = State.get_all()
    # Sort by date then slug
    posts.sort(key=lambda p: (p.get('date', ''), p.get('slug', '')))
    self._json(200, posts)
```

with:
```python
def _api_posts_list(self, author: str | None = None):
    posts = State.get_all()
    # Resolve effective author: param > config default > all
    effective = author if author is not None else cfg.get('filter', {}).get('author', '')
    if effective:
        posts = [p for p in posts if p.get('author', '') == effective]
    posts.sort(key=lambda p: (p.get('date', ''), p.get('slug', '')))
    self._json(200, posts)
```

- [ ] **Step 4: Run full test suite**

Run: `python3 -m pytest blog-migrator/tests/ -q`
Expected: All tests pass (server API tests skip if server not running)

- [ ] **Step 5: Commit**

```bash
git add blog-migrator/server.py blog-migrator/tests/test_server_api.py
git commit -m "feat(server): GET /api/posts?author=X filters by author; falls back to config"
```

---

## Task 5: UI — author `<select>` dropdown

**Files:**
- Modify: `blog-migrator/ui/index.html`

### Context
The existing `#nav-filters` bar has status filter buttons. We add a `<select>` at the left end populated from unique authors in `allPosts`. On change it re-fetches `GET /api/posts?author=X`. On page load it pre-selects `cfg.filter.author` from `/api/config`.

The existing `loadPosts()` function (or equivalent) fetches from `/api/posts` — find it and parameterise it.

- [ ] **Step 1: Find the current `loadPosts` / initial fetch call**

Search `index.html` for where `fetch('/api/posts')` or `fetch(API + '/posts')` is called. Note the variable name used to hold the URL.

Run: `grep -n "api/posts\|loadPosts\|allPosts" blog-migrator/ui/index.html | head -20`

- [ ] **Step 2: Extract `fetchPosts(author='')` function**

Find the existing posts fetch and wrap it in a reusable function. The pattern in the existing code will look something like:

```javascript
// Existing pattern (find and replace with this)
async function fetchPosts(author = '') {
  const url = author ? `/api/posts?author=${encodeURIComponent(author)}` : '/api/posts';
  const r = await fetch(url);
  allPosts = await r.json();
  updateStats();
  renderNav();
}
```

Replace any direct `fetch('/api/posts')` calls with `fetchPosts(currentAuthor)`. Add `let currentAuthor = '';` near the other `let` declarations.

- [ ] **Step 3: Add author `<select>` to `#nav-filters`**

Find `<div id="nav-filters">` in `index.html`. Add a `<select>` as the first child:

```html
<select id="author-select" style="background:#161b22;color:#c9d1d9;border:1px solid #30363d;border-radius:4px;padding:3px 6px;font-size:12px;cursor:pointer" title="Filter by author">
  <option value="">All authors</option>
</select>
```

- [ ] **Step 4: Populate dropdown and wire up change handler**

Find the page initialisation code (where posts are first loaded, config is read). Add:

```javascript
// Populate author dropdown after loading config
async function initAuthorFilter() {
  // Pre-select from config
  const cfgR = await fetch('/api/config');
  const cfgData = await cfgR.json();
  currentAuthor = cfgData.filter?.author || '';

  // Populate options from current posts
  const authors = [...new Set(allPosts.map(p => p.author).filter(Boolean))].sort();
  const sel = document.getElementById('author-select');
  sel.innerHTML = '<option value="">All authors</option>' +
    authors.map(a => `<option value="${a}"${a === currentAuthor ? ' selected' : ''}>${a}</option>`).join('');

  // Wire up change
  sel.addEventListener('change', async () => {
    currentAuthor = sel.value;
    await fetchPosts(currentAuthor);
  });
}
```

Call `initAuthorFilter()` after the initial `fetchPosts()` call completes.

- [ ] **Step 5: Manual smoke test**

Start Sparge with a multi-author project or the existing `kie-mark-proctor` project. Verify:
- Dropdown appears in filter bar with "All authors" and author names
- Changing selection re-fetches and updates the list
- Correct author pre-selected on load if `filter.author` is set in config

- [ ] **Step 6: Commit**

```bash
git add blog-migrator/ui/index.html
git commit -m "feat(ui): author filter dropdown — pre-selected from config, re-fetches on change"
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| `~/.sparge/config.json` created with default `projects_dir` | Task 1 |
| `~/` expansion in `projects_dir` | Task 1 |
| Auto-migration from `blog-migrator/projects/` | Task 2 |
| Migration skipped if already done | Task 2 |
| Old location not deleted | Task 2 |
| `PROJECTS_DIR` used throughout server.py | Task 3 |
| `GET /api/posts?author=X` filters by author | Task 4 |
| Falls back to `cfg.filter.author` if no param | Task 4 |
| Empty param returns all | Task 4 |
| UI dropdown populated from post authors | Task 5 |
| Pre-selected from config on page load | Task 5 |
| Re-fetches on change | Task 5 |

**Placeholder scan:** None — all steps have concrete code.

**Type consistency:** `author: str | None` in `_api_posts_list`, `currentAuthor` string in JS, `effective` string for filtering — consistent throughout.

**Note on Task 5:** Step 1 says to grep for the existing fetch pattern before writing code, because `index.html` is large and the exact variable names need to be confirmed before modification. The subagent must read the file first.
