# CodeMirror Editors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the plain textarea MD editor with CodeMirror (markdown mode) and add a new CodeMirror HTML editor to the HTML panel for editing the enriched HTML copy.

**Architecture:** Two new server endpoints (`GET /html`, `POST /save-html`) follow the existing `save-md` pattern. CodeMirror 5 is loaded from CDN (no bundler). The MD editor's `<textarea>` becomes a `<div>` hosting a CodeMirror instance; a new HTML editor `<div>` sits alongside the existing iframe in the HTML panel.

**Tech Stack:** Python 3.11+, CodeMirror 5.65.16 (CDN), vanilla JS, pytest

**Spec:** `blog-migrator/docs/superpowers/specs/2026-04-05-codemirror-editors-design.md`

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `blog-migrator/server.py` | **MODIFY** | Add `_api_post_html()` and `_api_save_html()` methods + routing |
| `blog-migrator/ui/index.html` | **MODIFY** | CDN tags; MD textarea→div; HTML editor div+buttons; all JS |
| `blog-migrator/tests/test_server_api.py` | **MODIFY** | Tests for new `/html` and `/save-html` endpoints |

---

## Task 1: Backend — `GET /api/posts/{slug}/html`

**Files:**
- Modify: `blog-migrator/server.py`
- Modify: `blog-migrator/tests/test_server_api.py`

### Context
The new endpoint returns raw HTML text. Reads `ENRICHED_DIR/{slug}.html` if it exists, falls back to `POSTS_DIR/{slug}.html`. Returns `text/plain` (not `text/html`) so the browser doesn't try to render it as a page.

Current GET routing (lines ~244-251):
```python
elif path.startswith('/api/posts/'):
    rest = path[len('/api/posts/'):]
    if rest.endswith('/staged'):
        self._api_staged_get(rest[:-len('/staged')])
    else:
        self._api_post_get(rest)
```

- [ ] **Step 1: Write failing test**

Append to `blog-migrator/tests/test_server_api.py`:

```python
class TestPostHtmlEndpoint:
    """GET /api/posts/{slug}/html returns raw HTML source."""

    def test_returns_html_for_known_post(self, server):
        posts = SESSION_HTTP.get(f'{API}/posts').json()
        if not posts:
            pytest.skip('No posts in active project')
        slug = posts[0]['slug']
        r = SESSION_HTTP.get(f'{API}/posts/{slug}/html')
        assert r.status_code == 200
        assert '<' in r.text  # basic HTML sanity check

    def test_returns_404_for_unknown_slug(self, server):
        r = SESSION_HTTP.get(f'{API}/posts/this-slug-does-not-exist-xyz/html')
        assert r.status_code == 404
```

Run (server must be running): `python3 -m pytest blog-migrator/tests/test_server_api.py::TestPostHtmlEndpoint -v`
Expected: SKIP (server not running) or FAIL if running

- [ ] **Step 2: Add routing for `/html` in `do_GET`**

In `blog-migrator/server.py`, find the GET routing block and add the `/html` case before the catch-all:

```python
elif path.startswith('/api/posts/'):
    rest = path[len('/api/posts/'):]
    if rest.endswith('/staged'):
        self._api_staged_get(rest[:-len('/staged')])
    elif rest.endswith('/html'):
        self._api_post_html(rest[:-len('/html')])
    else:
        self._api_post_get(rest)
```

- [ ] **Step 3: Add `_api_post_html()` method**

Add after `_api_post_get()` in `server.py`:

```python
def _api_post_html(self, slug: str):
    """Return raw HTML source — enriched copy if available, else original."""
    enriched = ENRICHED_DIR / (slug + '.html')
    original = POSTS_DIR   / (slug + '.html')
    if enriched.exists():
        html_path = enriched
    elif original.exists():
        html_path = original
    else:
        self._json(404, {'error': f'HTML not found: {slug}'}); return
    try:
        content = html_path.read_text(encoding='utf-8', errors='replace')
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(content.encode('utf-8', errors='replace'))
    except Exception as e:
        self._json(500, {'error': str(e)})
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest blog-migrator/tests/ -q`
Expected: 241 passed, 1 skipped (or more if server running)

- [ ] **Step 5: Commit**

```bash
git add blog-migrator/server.py blog-migrator/tests/test_server_api.py
git commit -m "feat(server): GET /api/posts/{slug}/html returns raw HTML source"
```

---

## Task 2: Backend — `POST /api/posts/{slug}/save-html`

**Files:**
- Modify: `blog-migrator/server.py`
- Modify: `blog-migrator/tests/test_server_api.py`

### Context
Follows the same pattern as `_api_save_md`. Writes to `ENRICHED_DIR/{slug}.html`. Returns updated post state.

- [ ] **Step 1: Write failing test**

Append to `blog-migrator/tests/test_server_api.py`:

```python
class TestSaveHtmlEndpoint:
    """POST /api/posts/{slug}/save-html writes enriched HTML."""

    def test_save_html_writes_enriched_copy(self, server, tmp_path):
        posts = SESSION_HTTP.get(f'{API}/posts').json()
        if not posts:
            pytest.skip('No posts in active project')
        slug = posts[0]['slug']

        # Get current HTML to use as content
        r = SESSION_HTTP.get(f'{API}/posts/{slug}/html')
        if r.status_code != 200:
            pytest.skip('Cannot fetch HTML for post')
        original_html = r.text

        # Save with a marker appended
        marker = '<!-- test-save-html-marker -->'
        modified = original_html + marker
        r = SESSION_HTTP.post(
            f'{API}/posts/{slug}/save-html',
            data=modified.encode('utf-8'),
            headers={'Content-Type': 'text/html; charset=utf-8'},
        )
        assert r.status_code == 200

        # Verify the marker is in the enriched copy
        r2 = SESSION_HTTP.get(f'{API}/posts/{slug}/html')
        assert marker in r2.text

        # Restore original
        SESSION_HTTP.post(
            f'{API}/posts/{slug}/save-html',
            data=original_html.encode('utf-8'),
            headers={'Content-Type': 'text/html; charset=utf-8'},
        )
```

Run: `python3 -m pytest blog-migrator/tests/test_server_api.py::TestSaveHtmlEndpoint -v`
Expected: SKIP (server not running)

- [ ] **Step 2: Add routing for `/save-html` in `do_POST`**

In `blog-migrator/server.py`, find the POST routing block for `/api/posts/`. Add after the `save-md` line:

```python
elif rest.endswith('/save-html'):
    self._api_save_html(rest[:-len('/save-html')], body)
```

- [ ] **Step 3: Add `_api_save_html()` method**

Add after `_api_save_md()` in `server.py`:

```python
def _api_save_html(self, slug: str, content: str):
    """Write manually-edited HTML to the enriched copy. Never touches original."""
    ENRICHED_DIR.mkdir(parents=True, exist_ok=True)
    html_path = ENRICHED_DIR / (slug + '.html')
    try:
        html_path.write_text(content, encoding='utf-8')
        print(f'Saved HTML (manual edit): {slug}.html → enriched/')
        self._json(200, State.get(slug))
    except Exception as e:
        self._json(500, {'error': str(e)})
```

- [ ] **Step 4: Run full test suite**

Run: `python3 -m pytest blog-migrator/tests/ -q`
Expected: 241 passed, 1 skipped

- [ ] **Step 5: Commit**

```bash
git add blog-migrator/server.py blog-migrator/tests/test_server_api.py
git commit -m "feat(server): POST /api/posts/{slug}/save-html writes to enriched copy"
```

---

## Task 3: UI — Load CodeMirror from CDN

**Files:**
- Modify: `blog-migrator/ui/index.html`

### Context
CodeMirror 5 requires scripts in dependency order: xml/js/css before htmlmixed. The `material-darker` theme matches the existing dark UI. Add to `<head>` after existing stylesheets.

- [ ] **Step 1: Add CDN tags to `<head>`**

In `blog-migrator/ui/index.html`, find the closing `</head>` tag. Add immediately before it:

```html
<!-- CodeMirror 5 — syntax-highlighted editors -->
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.css">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/theme/material-darker.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/xml/xml.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/javascript/javascript.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/css/css.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/htmlmixed/htmlmixed.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/markdown/markdown.min.js"></script>
```

Also add this CSS for CodeMirror to fill its container, after the CDN link tags:

```html
<style>
  .CodeMirror { height: 100%; font-size: 13px; font-family: 'SFMono-Regular', Consolas, monospace; }
  .CodeMirror-scroll { height: 100%; }
  #md-editor.cm-wrap, #html-editor { height: 100%; }
</style>
```

- [ ] **Step 2: Smoke test — open browser and check console**

Open http://localhost:9000. Open browser devtools console. Verify:
- No `CodeMirror is not defined` errors
- `typeof CodeMirror` returns `"function"`

- [ ] **Step 3: Commit**

```bash
git add blog-migrator/ui/index.html
git commit -m "feat(ui): load CodeMirror 5 from CDN with markdown and htmlmixed modes"
```

---

## Task 4: UI — Upgrade MD editor from textarea to CodeMirror

**Files:**
- Modify: `blog-migrator/ui/index.html`

### Context
The existing MD editor is a `<textarea id="md-editor">`. Replace the element with a `<div id="md-editor">` that CodeMirror mounts into. Update `enterEditMode()`, `cancelEdit()`, and `saveContent()` to use `mdEditor.getValue()` / `mdEditor.setValue()` instead of `.value`.

- [ ] **Step 1: Replace `<textarea>` with `<div>`**

Find in `blog-migrator/ui/index.html`:
```html
<textarea id="md-editor" style="display:none;width:100%;height:100%;background:#0d1117;color:#c9d1d9;border:none;outline:none;padding:16px;font-family:'SFMono-Regular',Consolas,monospace;font-size:13px;line-height:1.6;resize:none;box-sizing:border-box"></textarea>
```

Replace with:
```html
<div id="md-editor" style="display:none;height:100%"></div>
```

- [ ] **Step 2: Add `mdEditor` state variable**

Find `let editMode = false;` in the JS. Add immediately after:
```javascript
let mdEditor = null;
```

- [ ] **Step 3: Update `enterEditMode()`**

Find the `enterEditMode()` function. Replace the lines that set `$('md-editor').value` and `$('md-editor').style.display`:

Replace:
```javascript
  $('md-editor').value = raw;
  $('md-editor').style.display = 'block';
```
with:
```javascript
  if (!mdEditor) {
    mdEditor = CodeMirror($('md-editor'), {
      mode: 'markdown',
      theme: 'material-darker',
      lineNumbers: true,
      lineWrapping: true,
      value: raw,
    });
  } else {
    mdEditor.setValue(raw);
  }
  $('md-editor').style.display = 'block';
  mdEditor.refresh();
```

Remove the `$('md-editor').focus()` line (CodeMirror focuses itself after init).

- [ ] **Step 4: Update `cancelEdit()`**

Find the lines that hide the editor:
```javascript
  $('md-editor').style.display = 'none';
```
After that line add:
```javascript
  if (mdEditor) mdEditor.setValue('');
```

- [ ] **Step 5: Update `saveContent()`**

Find:
```javascript
  const content = $('md-editor').value;
```
Replace with:
```javascript
  const content = mdEditor ? mdEditor.getValue() : '';
```

- [ ] **Step 6: Manual smoke test**

Open a post in Sparge, click ✎ Edit. Verify:
- CodeMirror editor appears with markdown syntax highlighting
- Headers, bold, code fences are coloured
- Save works (saves MD, re-validates)
- Cancel works (hides editor, shows rendered MD)

- [ ] **Step 7: Commit**

```bash
git add blog-migrator/ui/index.html
git commit -m "feat(ui): upgrade MD editor from textarea to CodeMirror markdown mode"
```

---

## Task 5: UI — Add HTML editor with CodeMirror

**Files:**
- Modify: `blog-migrator/ui/index.html`

### Context
Add `✎ Edit HTML` button to the HTML panel toolbar, a `<div id="html-editor">` alongside the iframe, and JS to show/hide/save. When saving, reload iframe via `srcdoc` (shows enriched content, not the original from the static file server).

- [ ] **Step 1: Add HTML editor buttons to toolbar**

Find in the HTML panel section the existing buttons (Scan, Generate MD, etc.). Add after the existing buttons in the HTML panel toolbar:

```html
<button id="btn-edit-html" onclick="toggleHtmlEditMode()" title="Edit the enriched HTML copy">✎ Edit HTML</button>
<button id="btn-save-html" onclick="saveHtml()" style="display:none" class="success" title="Save enriched HTML">💾 Save HTML</button>
<button id="btn-cancel-html" onclick="cancelHtmlEdit()" style="display:none" title="Cancel editing">✕</button>
```

- [ ] **Step 2: Add `<div id="html-editor">` alongside the iframe**

Find:
```html
<iframe id="orig-frame" src="about:blank"></iframe>
```

Add immediately after:
```html
<div id="html-editor" style="display:none;height:100%"></div>
```

- [ ] **Step 3: Add HTML editor state variables**

Find `let mdEditor = null;`. Add after:
```javascript
let htmlEditMode = false;
let htmlEditor = null;
```

- [ ] **Step 4: Add HTML editor functions**

Add after `cancelEdit()` function:

```javascript
async function toggleHtmlEditMode() {
  htmlEditMode ? cancelHtmlEdit() : enterHtmlEditMode();
}

async function enterHtmlEditMode() {
  if (!currentSlug) return;
  const r = await fetch(`${API}/api/posts/${encodeURIComponent(currentSlug)}/html`);
  if (!r.ok) { alert('Could not load HTML source'); return; }
  const raw = await r.text();
  if (!htmlEditor) {
    htmlEditor = CodeMirror($('html-editor'), {
      mode: 'htmlmixed',
      theme: 'material-darker',
      lineNumbers: true,
      lineWrapping: false,
      value: raw,
    });
  } else {
    htmlEditor.setValue(raw);
  }
  $('orig-frame').style.display = 'none';
  $('html-editor').style.display = 'block';
  htmlEditor.refresh();
  htmlEditMode = true;
  $('btn-edit-html').textContent = '✎ Editing HTML';
  $('btn-edit-html').classList.add('editing');
  $('btn-save-html').style.display = '';
  $('btn-cancel-html').style.display = '';
}

function cancelHtmlEdit() {
  $('html-editor').style.display = 'none';
  $('orig-frame').style.display = '';
  htmlEditMode = false;
  $('btn-edit-html').textContent = '✎ Edit HTML';
  $('btn-edit-html').classList.remove('editing');
  $('btn-save-html').style.display = 'none';
  $('btn-cancel-html').style.display = 'none';
}

async function saveHtml() {
  if (!currentSlug || !htmlEditMode) return;
  const content = htmlEditor.getValue();
  const r = await fetch(`${API}/api/posts/${encodeURIComponent(currentSlug)}/save-html`, {
    method: 'POST',
    body: content,
    headers: { 'Content-Type': 'text/html; charset=utf-8' },
  });
  if (!r.ok) { alert('Save failed'); return; }
  cancelHtmlEdit();
  $('orig-frame').srcdoc = content;
}
```

- [ ] **Step 5: Cancel HTML edit on post switch**

Find the existing post-switch handler where `cancelEdit()` is called (look for `if (editMode) cancelEdit()`). Add immediately after:
```javascript
if (htmlEditMode) cancelHtmlEdit();
```

- [ ] **Step 6: Manual smoke test**

Open a post in Sparge. In the HTML panel:
- Click ✎ Edit HTML — CodeMirror appears with HTML syntax highlighting
- Make a small edit (e.g. add a comment at the end)
- Click 💾 Save HTML — editor closes, iframe updates to show saved content
- Click ✕ Cancel — editor closes without saving
- Switch to another post — editor closes cleanly

- [ ] **Step 7: Commit**

```bash
git add blog-migrator/ui/index.html
git commit -m "feat(ui): add CodeMirror HTML editor for enriched HTML copy"
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| CodeMirror 5 loaded from CDN (xml, js, css, htmlmixed, markdown) | Task 3 |
| CDN load order: xml/js/css before htmlmixed | Task 3 |
| `material-darker` theme | Task 3 |
| `.CodeMirror { height: 100% }` CSS | Task 3 |
| MD `<textarea>` → `<div>` | Task 4 |
| `mdEditor` state var, CodeMirror init on first edit | Task 4 |
| `mdEditor.getValue()` in `saveContent()` | Task 4 |
| `GET /api/posts/{slug}/html` — enriched fallback to original | Task 1 |
| `POST /api/posts/{slug}/save-html` — writes to ENRICHED_DIR | Task 2 |
| `✎ Edit HTML` button | Task 5 |
| `💾 Save HTML` + `✕` buttons | Task 5 |
| `<div id="html-editor">` alongside iframe | Task 5 |
| `enterHtmlEditMode()` fetches `/html`, inits CodeMirror | Task 5 |
| `cancelHtmlEdit()` restores iframe | Task 5 |
| `saveHtml()` POSTs `/save-html`, reloads iframe via `srcdoc` | Task 5 |
| Cancel HTML edit on post switch | Task 5 |
| Original HTML never written to | Task 2 (`_api_save_html` writes only to ENRICHED_DIR) |

**Placeholder scan:** None — all steps have concrete code.

**Type consistency:** `mdEditor` / `htmlEditor` used consistently throughout Tasks 4 and 5. `currentSlug` referenced in Tasks 4 and 5 — already defined as a module-level var in the existing JS.
