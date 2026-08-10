# Edit Mode Redesign — Three-Partition Full-Screen Editor

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the two separate per-panel edit modes with a unified full-screen editor: left sidebar becomes edit controls, middle becomes the CodeMirror editor, right becomes live preview with scroll sync and save/discard guard on navigation.

**Architecture:** A single `editState` ('html' | 'md' | null) and `editDirty` flag replace the existing `editMode` + `htmlEditMode` booleans. A new `#edit-sidebar` element swaps with `#nav` on enter/exit. The HTML panel hosts the CodeMirror editor; the MD panel hosts the live preview (iframe srcdoc for HTML, `marked.js` div for MD). A custom modal handles unsaved-changes prompts on all navigation paths.

**Tech Stack:** Vanilla JS, CodeMirror 5 (already loaded), marked.js 9 (new CDN), Python pytest for server integration tests, browser-runnable HTML for JS unit tests

**Spec:** `blog-migrator/docs/superpowers/specs/2026-04-05-edit-mode-redesign.md` — read it before starting.

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `blog-migrator/ui/index.html` | **MODIFY** | All state, HTML, CSS, and JS changes |
| `blog-migrator/ui/tests/edit-mode-unit.html` | **CREATE** | Browser-runnable JS unit tests (pure functions) |
| `blog-migrator/tests/test_edit_flow.py` | **CREATE** | Python integration tests for all save/retrieve paths |

---

## Task 1: Add marked.js CDN + `#md-preview` div

**Files:**
- Modify: `blog-migrator/ui/index.html`

### Context
`marked.js` renders Markdown to HTML client-side for the live MD preview. The `#md-preview` div sits inside `#md-panel-body` alongside the existing `#md-wrap`, `#md-editor`, and `#md-empty` divs.

- [ ] **Step 1: Add marked.js CDN tag**

In `blog-migrator/ui/index.html`, find the CodeMirror CDN block (around line 233). Add immediately after the last CodeMirror script tag, before `</head>`:

```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/9.1.6/marked.min.js"></script>
```

- [ ] **Step 2: Add `#md-preview` div in MD panel**

Find `<div id="md-wrap"></div>` (inside `#md-panel-body`). Add immediately before it:

```html
<div id="md-preview" style="display:none;padding:16px 20px;overflow:auto;height:100%;box-sizing:border-box;font-family:sans-serif;font-size:14px;line-height:1.6;color:#24292e;background:#fff"></div>
```

- [ ] **Step 3: Verify marked.js loaded**

Open http://localhost:9000. Open browser console. Run: `typeof marked` — expect `"object"`.

- [ ] **Step 4: Commit**

```bash
git add blog-migrator/ui/index.html
git commit -m "feat(ui): add marked.js CDN for MD live preview"
```

---

## Task 2: State refactor — `editState` + `editDirty` + pure helpers

**Files:**
- Modify: `blog-migrator/ui/index.html`
- Create: `blog-migrator/ui/tests/edit-mode-unit.html`

### Context
Replace `let editMode = false` and `let htmlEditMode = false` with unified state. Extract scroll math as pure functions so they can be unit-tested without a browser.

- [ ] **Step 1: Create JS unit test file**

Create `blog-migrator/ui/tests/edit-mode-unit.html`:

```html
<!DOCTYPE html>
<html>
<head><title>Edit Mode Unit Tests</title>
<style>
  body { font-family: monospace; padding: 20px; background: #0d1117; color: #c9d1d9; }
  .pass { color: #3fb950; } .fail { color: #f85149; }
  h2 { color: #58a6ff; }
</style>
</head>
<body>
<h2>Edit Mode Unit Tests</h2>
<pre id="out"></pre>
<script>
// ── Pure functions under test (copy from index.html after implementation) ──────
function scrollPercent(scrollTop, scrollHeight, clientHeight) {
  const max = scrollHeight - clientHeight;
  return max <= 0 ? 0 : Math.min(1, Math.max(0, scrollTop / max));
}

function scrollFromPercent(pct, scrollHeight, clientHeight) {
  const max = scrollHeight - clientHeight;
  return max <= 0 ? 0 : Math.round(pct * max);
}

function debounce(fn, ms) {
  let t; return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

// ── Test runner ────────────────────────────────────────────────────────────────
let passed = 0, failed = 0;
const out = document.getElementById('out');
function assert(label, actual, expected) {
  const ok = JSON.stringify(actual) === JSON.stringify(expected);
  out.innerHTML += `<span class="${ok?'pass':'fail'}">${ok?'✓':'✗'} ${label}`;
  if (!ok) out.innerHTML += `\n  expected: ${JSON.stringify(expected)}\n  actual:   ${JSON.stringify(actual)}`;
  out.innerHTML += '</span>\n';
  ok ? passed++ : failed++;
}

// scrollPercent tests
assert('scrollPercent: top of page',    scrollPercent(0,   1000, 500), 0);
assert('scrollPercent: bottom of page', scrollPercent(500, 1000, 500), 1);
assert('scrollPercent: mid page',       scrollPercent(250, 1000, 500), 0.5);
assert('scrollPercent: no scroll room', scrollPercent(0,   400,  500), 0);
assert('scrollPercent: clamped > 1',    scrollPercent(999, 1000, 500), 1);
assert('scrollPercent: clamped < 0',    scrollPercent(-10, 1000, 500), 0);

// scrollFromPercent tests
assert('scrollFromPercent: 0%',   scrollFromPercent(0,   1000, 500), 0);
assert('scrollFromPercent: 100%', scrollFromPercent(1,   1000, 500), 500);
assert('scrollFromPercent: 50%',  scrollFromPercent(0.5, 1000, 500), 250);
assert('scrollFromPercent: no room', scrollFromPercent(0.5, 400, 500), 0);

// Round-trip test
const pct = scrollPercent(123, 800, 400);
assert('round-trip scrollTop→pct→scrollTop', scrollFromPercent(pct, 800, 400), 123);

out.innerHTML += `\n<strong class="${failed?'fail':'pass'}">${passed} passed, ${failed} failed</strong>`;
</script>
</body>
</html>
```

- [ ] **Step 2: Open the test file in browser and verify all pass**

Open `file:///Users/mdproctor/mdproctor.github.io/blog-migrator/ui/tests/edit-mode-unit.html`
Expected: all 11 tests show ✓ in green.

- [ ] **Step 3: Replace state variables in `index.html`**

Find (around line 726):
```javascript
let editMode = false;
let mdEditor = null;
let htmlEditMode = false;
let htmlEditor = null;
```

Replace with:
```javascript
// Edit mode state
let editState = null;   // null | 'html' | 'md'
let editDirty = false;  // true after first unsaved change
let mdEditor   = null;
let htmlEditor = null;

// Pure helpers — also in ui/tests/edit-mode-unit.html
function scrollPercent(scrollTop, scrollHeight, clientHeight) {
  const max = scrollHeight - clientHeight;
  return max <= 0 ? 0 : Math.min(1, Math.max(0, scrollTop / max));
}
function scrollFromPercent(pct, scrollHeight, clientHeight) {
  const max = scrollHeight - clientHeight;
  return max <= 0 ? 0 : Math.round(pct * max);
}
function debounce(fn, ms) {
  let t; return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}
```

- [ ] **Step 4: Update `toggleEditMode()` to use `editState`**

Replace the existing `toggleEditMode()` function:
```javascript
function toggleEditMode() {
  if (!currentSlug) return;
  editState === 'md' ? exitEditMode() : enterEditMode('md');
}
```

Replace the existing `toggleHtmlEditMode()` function:
```javascript
async function toggleHtmlEditMode() {
  editState === 'html' ? exitEditMode() : enterEditMode('html');
}
```

- [ ] **Step 5: Update `selectPost()` dirty check**

Find in `selectPost()`:
```javascript
  if (editMode) cancelEdit();
  if (htmlEditMode) cancelHtmlEdit();
```

Replace with (full guard to be implemented in Task 6):
```javascript
  if (editState) { exitEditMode(); }
```

- [ ] **Step 6: Run full test suite to verify no regressions**

```bash
python3 -m pytest blog-migrator/tests/ -q
```
Expected: 216 passed, ~29 skipped

- [ ] **Step 7: Commit**

```bash
git add blog-migrator/ui/index.html blog-migrator/ui/tests/edit-mode-unit.html
git commit -m "feat(ui): refactor edit state to editState/editDirty + pure scroll helpers"
```

---

## Task 3: Add `#edit-sidebar` HTML + CSS

**Files:**
- Modify: `blog-migrator/ui/index.html`

### Context
The edit sidebar sits alongside `#nav` in the DOM — both are siblings inside `<body>`. When entering edit mode, `#nav` hides and `#edit-sidebar` shows (both 252px wide), keeping the three-column layout intact.

- [ ] **Step 1: Add CSS for edit sidebar**

Find the `#nav` CSS block (around line 70). Add after it:

```css
#edit-sidebar {
  display: none;
  width: 252px;
  flex-shrink: 0;
  background: #161b22;
  border-right: 1px solid #30363d;
  flex-direction: column;
  padding: 16px;
  gap: 12px;
  overflow-y: auto;
}
#edit-sidebar-mode { font-size:10px; color:#58a6ff; font-weight:bold; letter-spacing:.06em; text-transform:uppercase; }
#edit-sidebar-slug { font-size:11px; color:#8b949e; word-break:break-all; line-height:1.5; }
#edit-sidebar-dirty { font-size:10px; color:#e3b341; display:none; }
.edit-sidebar-divider { border-top:1px solid #30363d; }
```

- [ ] **Step 2: Add `#edit-sidebar` HTML element**

Find `<div id="nav">` (around line 272). Add immediately before it:

```html
<div id="edit-sidebar">
  <div id="edit-sidebar-mode">✎ Editing</div>
  <div id="edit-sidebar-slug"></div>
  <div id="edit-sidebar-dirty">● Unsaved changes</div>
  <div class="edit-sidebar-divider"></div>
  <button id="btn-edit-save" onclick="saveEditContent()" class="success" style="padding:7px">💾 Save</button>
  <button id="btn-edit-discard" onclick="discardEdit()" style="background:#2d0f0f;border-color:#f85149;color:#f85149;padding:7px">✕ Discard changes</button>
  <div style="margin-top:auto">
    <button onclick="exitEditMode()" style="width:100%;padding:7px">← Back to review</button>
    <div style="font-size:10px;color:#484f58;margin-top:6px;text-align:center">Prompts if unsaved changes</div>
  </div>
</div>
```

- [ ] **Step 3: Verify sidebar exists but is hidden**

Open http://localhost:9000. In devtools console: `document.getElementById('edit-sidebar').style.display` — expect `""` (hidden via CSS `display:none`).

- [ ] **Step 4: Commit**

```bash
git add blog-migrator/ui/index.html
git commit -m "feat(ui): add #edit-sidebar HTML and CSS"
```

---

## Task 4: `enterEditMode(mode)` — unified entry function

**Files:**
- Modify: `blog-migrator/ui/index.html`

### Context
One function handles both HTML and MD. It hides `#nav`, shows `#edit-sidebar`, loads content into the CodeMirror editor in the HTML panel, and sets up the live preview in the MD panel. The existing `enterEditMode()` and `enterHtmlEditMode()` functions are replaced.

- [ ] **Step 1: Remove old enter/cancel functions**

Delete the following functions entirely (they will be replaced):
- `enterEditMode()` (the async MD function, around line 736)
- `cancelEdit()` (around line 766)
- `enterHtmlEditMode()` (around line 780)
- `cancelHtmlEdit()` (around line 806)
- `saveHtml()` (around line 816)

Also remove from `#html-panel` header: the `btn-save-html` and `btn-cancel-html` buttons (they move into the sidebar). Keep `btn-edit-html`.

Also remove from `#md-panel`: the `#md-edit-bar` div (the old Save/Cancel bar).

- [ ] **Step 2: Add `enterEditMode(mode)` function**

Add after the debounce helper (from Task 2):

```javascript
async function enterEditMode(mode) {
  if (!currentSlug) return;

  // Load content
  let raw;
  if (mode === 'html') {
    const r = await fetch(`/api/posts/${encodeURIComponent(currentSlug)}/html`);
    if (!r.ok) { alert('Could not load HTML source'); return; }
    raw = await r.text();
  } else {
    const p = allPosts.find(x => x.slug === currentSlug);
    if (!p?.md?.generated_at) { alert('Generate MD first before editing'); return; }
    const r = await fetch(`/${cfg.output?.md_dir || 'mark-proctor'}/${currentSlug}.md?v=${Date.now()}`);
    if (!r.ok) { alert('Could not load Markdown'); return; }
    raw = await r.text();
  }

  editState = mode;
  editDirty = false;

  // Show edit sidebar, hide nav
  $('nav').style.display = 'none';
  const sb = $('edit-sidebar');
  sb.style.display = 'flex';
  $('edit-sidebar-mode').textContent = mode === 'html' ? '✎ Editing HTML' : '✎ Editing MD';
  $('edit-sidebar-slug').textContent = currentSlug;
  $('edit-sidebar-dirty').style.display = 'none';

  // Middle panel: CodeMirror editor
  const editorEl = $('html-editor');
  $('orig-frame').style.display = 'none';
  editorEl.style.display = 'block';

  if (mode === 'html') {
    if (!htmlEditor) {
      htmlEditor = CodeMirror(editorEl, { mode:'htmlmixed', theme:'material-darker', lineNumbers:true, lineWrapping:false, value:raw });
    } else { htmlEditor.setValue(raw); }
    htmlEditor.refresh();
    setupEditorLivePreview(htmlEditor, 'html');
    setupEditorScrollSync(htmlEditor, 'html');
  } else {
    if (!mdEditor) {
      mdEditor = CodeMirror(editorEl, { mode:'markdown', theme:'material-darker', lineNumbers:true, lineWrapping:true, value:raw });
    } else { mdEditor.setValue(raw); }
    mdEditor.refresh();
    setupEditorLivePreview(mdEditor, 'md');
    setupEditorScrollSync(mdEditor, 'md');
  }

  // Right panel: live preview
  $('md-wrap').style.display = 'none';
  $('md-empty').style.display = 'none';
  $('md-editor').style.display = 'none'; // old MD editor hidden
  const prev = $('md-preview');
  prev.style.display = 'block';
  if (mode === 'html') {
    updateHtmlPreview(mode === 'html' ? htmlEditor : mdEditor, mode);
  } else {
    updateMdPreview(mdEditor.getValue());
  }

  // Update header buttons
  if (mode === 'html') {
    $('btn-edit-html').textContent = '✎ Editing HTML';
    $('btn-edit-html').classList.add('editing');
  } else {
    $('btn-edit-md').textContent = '✎ Editing';
    $('btn-edit-md').classList.add('editing');
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add blog-migrator/ui/index.html
git commit -m "feat(ui): unified enterEditMode(mode) — shows edit sidebar and CodeMirror editor"
```

---

## Task 5: Live preview (debounced)

**Files:**
- Modify: `blog-migrator/ui/index.html`

### Context
CodeMirror fires a `change` event on every keystroke. We debounce (300ms) and update the preview. For HTML: set `iframe.srcdoc`. For MD: `marked.parse()` → div innerHTML. `editDirty` is set on first change.

- [ ] **Step 1: Add live preview helper functions**

Add after `enterEditMode()`:

```javascript
const _livePreviewDebounced = {
  html: null,
  md:   null,
};

function updateHtmlPreview(content) {
  // Show in md-preview as a rendered iframe-equivalent
  const prev = $('md-preview');
  prev.innerHTML = '';
  const fr = document.createElement('iframe');
  fr.style.cssText = 'width:100%;height:100%;border:none;background:#fff';
  fr.srcdoc = content;
  prev.appendChild(fr);
}

function updateMdPreview(content) {
  $('md-preview').innerHTML = marked.parse(content);
}

function setupEditorLivePreview(editor, mode) {
  // Remove any previous listener by replacing with a fresh one
  if (_livePreviewDebounced[mode]) {
    // CodeMirror doesn't have removeEventListener, use off()
    try { editor.off('change', _livePreviewDebounced[mode]); } catch(e) {}
  }
  const handler = debounce(() => {
    editDirty = true;
    $('edit-sidebar-dirty').style.display = 'block';
    const content = editor.getValue();
    if (mode === 'html') updateHtmlPreview(content);
    else updateMdPreview(content);
  }, 300);
  _livePreviewDebounced[mode] = handler;
  editor.on('change', handler);
}
```

- [ ] **Step 2: Manual smoke test — live preview**

Open a post, click ✎ Edit HTML. Type a character anywhere — the right panel should update within 300ms. Open ✎ Edit MD — same.

- [ ] **Step 3: Commit**

```bash
git add blog-migrator/ui/index.html
git commit -m "feat(ui): debounced live preview — HTML iframe srcdoc + MD marked.parse"
```

---

## Task 6: Edit mode scroll sync

**Files:**
- Modify: `blog-migrator/ui/index.html`

### Context
When in edit mode, scroll the preview when the editor scrolls, and vice versa. Uses `scrollPercent` / `scrollFromPercent` from Task 2. A `syncingEdit` flag prevents feedback loops. Replaces the review-mode scroll sync (which uses the existing `setupScrollSync()`).

- [ ] **Step 1: Add `setupEditorScrollSync(editor, mode)` function**

Add after `setupEditorLivePreview()`:

```javascript
let _syncingEdit = false;

function setupEditorScrollSync(editor, mode) {
  const prev = $('md-preview');

  // Editor → preview
  editor.on('scroll', () => {
    if (_syncingEdit) return;
    _syncingEdit = true;
    const info = editor.getScrollInfo();
    const pct = scrollPercent(info.top, info.height, info.clientHeight);
    if (mode === 'html') {
      // For HTML preview, the iframe contains the rendered page
      const fr = prev.querySelector('iframe');
      if (fr) {
        try {
          const doc = fr.contentDocument || fr.contentWindow?.document;
          if (doc) {
            const h = doc.body.scrollHeight, ch = fr.clientHeight;
            fr.contentWindow.scrollTo(0, scrollFromPercent(pct, h, ch));
          }
        } catch(e) {}
      }
    } else {
      prev.scrollTop = scrollFromPercent(pct, prev.scrollHeight, prev.clientHeight);
    }
    requestAnimationFrame(() => requestAnimationFrame(() => { _syncingEdit = false; }));
  });

  // Preview → editor
  const onPreviewScroll = () => {
    if (_syncingEdit) return;
    _syncingEdit = true;
    const pct = scrollPercent(prev.scrollTop, prev.scrollHeight, prev.clientHeight);
    const info = editor.getScrollInfo();
    editor.scrollTo(0, scrollFromPercent(pct, info.height, info.clientHeight));
    requestAnimationFrame(() => requestAnimationFrame(() => { _syncingEdit = false; }));
  };
  // Remove and re-add to avoid stacking listeners across mode switches
  prev.removeEventListener('scroll', prev._editScrollHandler);
  prev._editScrollHandler = onPreviewScroll;
  prev.addEventListener('scroll', onPreviewScroll, { passive: true });
}
```

- [ ] **Step 2: Manual smoke test — scroll sync**

Open a long post in edit mode. Scroll the editor — preview should scroll. Scroll the preview — editor should scroll. No feedback loops (no rapid oscillation).

- [ ] **Step 3: Commit**

```bash
git add blog-migrator/ui/index.html
git commit -m "feat(ui): edit mode scroll sync — editor↔preview with loop guard"
```

---

## Task 7: `exitEditMode()` + `discardEdit()` + `saveEditContent()`

**Files:**
- Modify: `blog-migrator/ui/index.html`

### Context
`exitEditMode()` restores the review layout. `saveEditContent()` POSTs the appropriate endpoint, then calls `exitEditMode()`. `discardEdit()` confirms and calls `exitEditMode()`.

- [ ] **Step 1: Add `exitEditMode()`**

Add after `setupEditorScrollSync()`:

```javascript
function exitEditMode() {
  if (!editState) return;
  const mode = editState;
  editState = null;
  editDirty = false;

  // Restore nav sidebar
  $('nav').style.display = '';
  $('edit-sidebar').style.display = 'none';

  // Restore HTML panel: show iframe, hide editor
  $('orig-frame').style.display = '';
  $('html-editor').style.display = 'none';

  // Restore MD panel: hide preview, show rendered MD
  $('md-preview').style.display = 'none';
  $('md-wrap').style.display = '';

  // Reset header buttons
  $('btn-edit-html').textContent = '✎ Edit HTML';
  $('btn-edit-html').classList.remove('editing');
  $('btn-edit-md').textContent = '✎ Edit';
  $('btn-edit-md').classList.remove('editing');

  // Re-render the current post in review mode
  if (currentSlug) {
    const p = allPosts.find(x => x.slug === currentSlug);
    if (p) { loadMd(p); renderPanelBadges(p); }
  }
}
```

- [ ] **Step 2: Add `saveEditContent()`**

```javascript
async function saveEditContent() {
  if (!editState || !currentSlug) return;
  const btn = $('btn-edit-save');
  const orig = btn.textContent;
  btn.textContent = '⏳ Saving…'; btn.disabled = true;

  const editor = editState === 'html' ? htmlEditor : mdEditor;
  const content = editor.getValue();
  const url = editState === 'html'
    ? `/api/posts/${encodeURIComponent(currentSlug)}/save-html`
    : `${API}/api/posts/${encodeURIComponent(currentSlug)}/save-md`;
  const headers = editState === 'html'
    ? { 'Content-Type': 'text/html; charset=utf-8' }
    : {};

  try {
    const r = await fetch(url, { method: 'POST', body: content, headers });
    if (r.ok) {
      editDirty = false;
      exitEditMode();
      await reloadPost(currentSlug);
    } else {
      btn.textContent = '✗ Failed'; btn.disabled = false;
      setTimeout(() => { btn.textContent = orig; btn.disabled = false; }, 2000);
    }
  } catch(e) {
    btn.textContent = '✗ Error'; btn.disabled = false;
    setTimeout(() => { btn.textContent = orig; btn.disabled = false; }, 2000);
  }
}
```

- [ ] **Step 3: Add `discardEdit()`**

```javascript
function discardEdit() {
  if (!editState) return;
  if (editDirty && !confirm('Discard all unsaved changes?')) return;
  editDirty = false;
  exitEditMode();
}
```

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest blog-migrator/tests/ -q
```
Expected: 216 passed, ~29 skipped

- [ ] **Step 5: Manual smoke test — enter, edit, save**

1. Open a post, click ✎ Edit HTML
2. Edit sidebar appears, nav hides
3. Make a small edit, see dirty indicator
4. Click 💾 Save → saves, returns to review mode, nav restores

- [ ] **Step 6: Commit**

```bash
git add blog-migrator/ui/index.html
git commit -m "feat(ui): exitEditMode, saveEditContent, discardEdit — complete exit flows"
```

---

## Task 8: Unsaved changes modal + all navigation guards

**Files:**
- Modify: `blog-migrator/ui/index.html`

### Context
`window.confirm()` is ugly and blocks the thread. Replace with a custom styled modal for the "Save / Discard / Cancel" prompt. All navigation paths that can happen while editing must call `promptUnsaved()`.

- [ ] **Step 1: Add modal HTML**

Find the closing `</body>` tag. Add immediately before it:

```html
<div id="unsaved-modal" style="display:none;position:fixed;inset:0;background:#000a;z-index:9999;align-items:center;justify-content:center">
  <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:24px;max-width:360px;width:90%;display:flex;flex-direction:column;gap:16px">
    <div style="font-size:14px;color:#c9d1d9;font-weight:600">Unsaved changes</div>
    <div style="font-size:13px;color:#8b949e">You have unsaved changes. What would you like to do?</div>
    <div style="display:flex;gap:8px;justify-content:flex-end">
      <button id="um-cancel"  style="padding:6px 14px">Cancel</button>
      <button id="um-discard" style="padding:6px 14px;background:#2d0f0f;border-color:#f85149;color:#f85149">Discard</button>
      <button id="um-save"    style="padding:6px 14px" class="success">💾 Save</button>
    </div>
  </div>
</div>
```

- [ ] **Step 2: Add `promptUnsaved()` function**

Add before `exitEditMode()`:

```javascript
function promptUnsaved() {
  // Returns a promise that resolves to 'save' | 'discard' | 'cancel'
  return new Promise(resolve => {
    const modal = $('unsaved-modal');
    modal.style.display = 'flex';
    const cleanup = result => {
      modal.style.display = 'none';
      $('um-save').onclick = null;
      $('um-discard').onclick = null;
      $('um-cancel').onclick = null;
      resolve(result);
    };
    $('um-save').onclick    = () => cleanup('save');
    $('um-discard').onclick = () => cleanup('discard');
    $('um-cancel').onclick  = () => cleanup('cancel');
  });
}
```

- [ ] **Step 3: Guard `exitEditMode()` with modal when dirty**

Update `exitEditMode()` — it currently exits immediately. Add the guard at the start:

```javascript
async function exitEditMode() {
  if (!editState) return;
  if (editDirty) {
    const choice = await promptUnsaved();
    if (choice === 'cancel') return;
    if (choice === 'save') {
      await saveEditContent();
      return; // saveEditContent calls exitEditMode() after save
    }
    // choice === 'discard': fall through
  }
  // ... rest of existing exitEditMode() body unchanged
```

Note: `exitEditMode()` must now be `async`. Update its declaration accordingly.

- [ ] **Step 4: Guard `selectPost()` when editing**

Find in `selectPost()`:
```javascript
  if (editState) { exitEditMode(); }
```

Replace with:
```javascript
  if (editState) {
    if (editDirty) {
      const choice = await promptUnsaved();
      if (choice === 'cancel') return;
      if (choice === 'save') {
        await saveEditContent();
        // After save, editState is null, continue with selectPost
      } else {
        // discard
        editDirty = false;
        exitEditModeImmediate(); // see below
      }
    } else {
      exitEditModeImmediate();
    }
  }
```

Add `exitEditModeImmediate()` — a synchronous version of the restore logic (no modal):

```javascript
function exitEditModeImmediate() {
  if (!editState) return;
  editState = null; editDirty = false;
  $('nav').style.display = '';
  $('edit-sidebar').style.display = 'none';
  $('orig-frame').style.display = '';
  $('html-editor').style.display = 'none';
  $('md-preview').style.display = 'none';
  $('md-wrap').style.display = '';
  $('btn-edit-html').textContent = '✎ Edit HTML';
  $('btn-edit-html').classList.remove('editing');
  $('btn-edit-md').textContent = '✎ Edit';
  $('btn-edit-md').classList.remove('editing');
}
```

Update `exitEditMode()` to call `exitEditModeImmediate()` for the restore logic (remove duplication):

```javascript
async function exitEditMode() {
  if (!editState) return;
  if (editDirty) {
    const choice = await promptUnsaved();
    if (choice === 'cancel') return;
    if (choice === 'save') { await saveEditContent(); return; }
  }
  exitEditModeImmediate();
  if (currentSlug) {
    const p = allPosts.find(x => x.slug === currentSlug);
    if (p) { loadMd(p); renderPanelBadges(p); }
  }
}
```

- [ ] **Step 5: Guard keyboard navigation (arrow keys)**

Find the keyboard handler (around line 1466):
```javascript
  if (goNext&&idx<posts.length-1) { e.preventDefault(); selectPost(posts[idx+1].slug); }
  if (goPrev&&idx>0)              { e.preventDefault(); selectPost(posts[idx-1].slug); }
```

`selectPost()` is already `async` and now handles the guard — no change needed here.

- [ ] **Step 6: Run tests**

```bash
python3 -m pytest blog-migrator/tests/ -q
```
Expected: 216 passed, ~29 skipped

- [ ] **Step 7: Manual smoke test — all navigation guards**

Run through these flows (requires running server at localhost:9000):

**Flow 1** — Enter HTML edit, type something, click ✕ Discard: modal appears → Discard → review mode  
**Flow 2** — Enter HTML edit, type something, click ✕ Discard → Cancel: stays in edit mode  
**Flow 3** — Enter HTML edit, type something, click ← Back to review → Save: saves and exits  
**Flow 4** — Enter HTML edit, type something, click ← Back to review → Discard: discards and exits  
**Flow 5** — Enter HTML edit, type something, click a different post: modal appears → Cancel: stays on same post  
**Flow 6** — Enter HTML edit, type something, click a different post → Discard: switches post  
**Flow 7** — Enter HTML edit (no changes), click ← Back to review: exits immediately, no modal  

- [ ] **Step 8: Commit**

```bash
git add blog-migrator/ui/index.html
git commit -m "feat(ui): unsaved-changes modal + navigation guards for all exit paths"
```

---

## Task 9: Python integration tests

**Files:**
- Create: `blog-migrator/tests/test_edit_flow.py`

### Context
Tests the complete save/retrieve cycle for both HTML and MD via HTTP. Requires the server to be running — tests skip automatically if not.

- [ ] **Step 1: Create `blog-migrator/tests/test_edit_flow.py`**

```python
"""
Integration tests for the edit mode save/retrieve cycle.

Tests the complete flow:
  1. Fetch raw HTML/MD via API
  2. Save modified content
  3. Verify the modification is retrievable

Requires server running on localhost:9000.
Tests are automatically skipped if server is not reachable.
"""
import json
import sys
from pathlib import Path

import pytest
import requests

MIGRATOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(MIGRATOR_ROOT / 'scripts'))

SERVER = 'http://localhost:9000'
API    = SERVER + '/api'
SESSION = requests.Session()
SESSION.headers['Content-Type'] = 'application/json'

MARKER_HTML = '<!-- edit-flow-integration-test -->'
MARKER_MD   = '\n\n<!-- edit-flow-integration-test -->'


@pytest.fixture(scope='module')
def server():
    """Skip all tests if server is not running."""
    try:
        requests.get(f'{API}/projects', timeout=3).raise_for_status()
    except Exception:
        pytest.skip('Server not running on localhost:9000')


@pytest.fixture(scope='module')
def test_slug(server):
    """Return the slug of the first available post."""
    posts = SESSION.get(f'{API}/posts').json()
    if not posts:
        pytest.skip('No posts in active project')
    return posts[0]['slug']


class TestHtmlEditCycle:
    """Complete HTML edit → save → retrieve cycle."""

    def test_fetch_html_returns_content(self, server, test_slug):
        r = SESSION.get(f'{API}/posts/{test_slug}/html')
        assert r.status_code == 200
        assert len(r.text) > 100
        assert '<' in r.text

    def test_save_and_retrieve_html(self, server, test_slug):
        # Fetch original
        original = SESSION.get(f'{API}/posts/{test_slug}/html').text
        assert MARKER_HTML not in original

        # Save with marker
        modified = original + MARKER_HTML
        r = SESSION.post(
            f'{API}/posts/{test_slug}/save-html',
            data=modified.encode('utf-8'),
            headers={'Content-Type': 'text/html; charset=utf-8'},
        )
        assert r.status_code == 200

        # Verify marker is retrievable
        retrieved = SESSION.get(f'{API}/posts/{test_slug}/html').text
        assert MARKER_HTML in retrieved

    def test_save_html_returns_post_state(self, server, test_slug):
        original = SESSION.get(f'{API}/posts/{test_slug}/html').text
        r = SESSION.post(
            f'{API}/posts/{test_slug}/save-html',
            data=original.encode('utf-8'),
            headers={'Content-Type': 'text/html; charset=utf-8'},
        )
        data = r.json()
        assert 'slug' in data
        assert data['slug'] == test_slug

    def test_save_html_never_touches_original(self, server, test_slug):
        """Original HTML file must remain unchanged after saving enriched copy."""
        import sparge_home as _sh
        from pathlib import Path
        proj_dir = _sh.get_projects_dir() / 'kie-mark-proctor'
        cfg_path = proj_dir / 'config.json'
        if not cfg_path.exists():
            pytest.skip('Cannot locate project config')
        cfg = json.loads(cfg_path.read_text())
        serve_root = Path(cfg['serve_root'])
        posts_dir  = serve_root / cfg['source']['posts_dir']
        original_path = posts_dir / (test_slug + '.html')
        if not original_path.exists():
            pytest.skip('Original HTML file not accessible in test')
        original_mtime = original_path.stat().st_mtime

        # Save something
        current = SESSION.get(f'{API}/posts/{test_slug}/html').text
        SESSION.post(
            f'{API}/posts/{test_slug}/save-html',
            data=(current + '<!-- mtime-test -->').encode(),
            headers={'Content-Type': 'text/html; charset=utf-8'},
        )

        # Original file mtime must not have changed
        assert original_path.stat().st_mtime == original_mtime, \
            'Original HTML file was modified — it should never be touched'

    def test_restore_original_after_test(self, server, test_slug):
        """Cleanup: remove test marker from enriched copy."""
        current = SESSION.get(f'{API}/posts/{test_slug}/html').text
        clean = current.replace(MARKER_HTML, '').replace('<!-- mtime-test -->', '')
        SESSION.post(
            f'{API}/posts/{test_slug}/save-html',
            data=clean.encode('utf-8'),
            headers={'Content-Type': 'text/html; charset=utf-8'},
        )
        retrieved = SESSION.get(f'{API}/posts/{test_slug}/html').text
        assert MARKER_HTML not in retrieved


class TestMdEditCycle:
    """Complete MD edit → save → retrieve cycle."""

    def test_save_and_retrieve_md(self, server, test_slug):
        # Only run if post has MD
        posts = SESSION.get(f'{API}/posts').json()
        post = next((p for p in posts if p['slug'] == test_slug), None)
        if not post or not post.get('md', {}).get('generated_at'):
            pytest.skip('Test post has no MD generated')

        # Fetch original MD
        cfg = SESSION.get(f'{API}/config').json()
        md_dir = cfg.get('output', {}).get('md_dir', 'mark-proctor')
        r = requests.get(f'{SERVER}/{md_dir}/{test_slug}.md')
        if r.status_code != 200:
            pytest.skip('Cannot fetch MD file')
        original_md = r.text
        assert MARKER_MD not in original_md

        # Save with marker
        modified = original_md + MARKER_MD
        r = SESSION.post(
            f'{API}/posts/{test_slug}/save-md',
            data=modified.encode('utf-8'),
            headers={'Content-Type': 'text/plain'},
        )
        assert r.status_code == 200

        # Verify marker is in saved file
        retrieved = requests.get(f'{SERVER}/{md_dir}/{test_slug}.md?v=1').text
        assert MARKER_MD in retrieved

        # Restore
        SESSION.post(
            f'{API}/posts/{test_slug}/save-md',
            data=original_md.encode('utf-8'),
            headers={'Content-Type': 'text/plain'},
        )

    def test_save_md_returns_post_state(self, server, test_slug):
        posts = SESSION.get(f'{API}/posts').json()
        post = next((p for p in posts if p['slug'] == test_slug), None)
        if not post or not post.get('md', {}).get('generated_at'):
            pytest.skip('Test post has no MD generated')

        cfg = SESSION.get(f'{API}/config').json()
        md_dir = cfg.get('output', {}).get('md_dir', 'mark-proctor')
        r = requests.get(f'{SERVER}/{md_dir}/{test_slug}.md')
        if r.status_code != 200:
            pytest.skip('Cannot fetch MD file')

        result = SESSION.post(
            f'{API}/posts/{test_slug}/save-md',
            data=r.text.encode('utf-8'),
            headers={'Content-Type': 'text/plain'},
        )
        data = result.json()
        assert 'slug' in data
        assert data['slug'] == test_slug


class TestUnsavedStateTracking:
    """Verify dirty tracking via the html endpoint (server-side)."""

    def test_enriched_copy_reflects_save(self, server, test_slug):
        """After save-html, GET /html returns the saved content."""
        original = SESSION.get(f'{API}/posts/{test_slug}/html').text
        unique = f'<!-- unique-{id(original)} -->'
        SESSION.post(
            f'{API}/posts/{test_slug}/save-html',
            data=(original + unique).encode('utf-8'),
            headers={'Content-Type': 'text/html; charset=utf-8'},
        )
        assert unique in SESSION.get(f'{API}/posts/{test_slug}/html').text

        # Restore
        SESSION.post(
            f'{API}/posts/{test_slug}/save-html',
            data=original.encode('utf-8'),
            headers={'Content-Type': 'text/html; charset=utf-8'},
        )
```

- [ ] **Step 2: Run integration tests (server must be running)**

```bash
python3 -m pytest blog-migrator/tests/test_edit_flow.py -v
```
Expected: all pass or skip (skip = server not running, which is fine in CI)

- [ ] **Step 3: Run full test suite**

```bash
python3 -m pytest blog-migrator/tests/ -q
```
Expected: 216 passed, ~29 skipped (test_edit_flow tests skip without running server)

- [ ] **Step 4: Commit**

```bash
git add blog-migrator/tests/test_edit_flow.py
git commit -m "test(edit-flow): integration tests for HTML/MD save/retrieve cycle + original immutability"
```

---

## Task 10: Final wiring — remove old edit buttons from panel headers

**Files:**
- Modify: `blog-migrator/ui/index.html`

### Context
The old `✎ Edit HTML` / `✎ Edit MD` buttons stay in the panel headers (`#panel-heads`) as entry points. The old `btn-save-html` / `btn-cancel-html` buttons in the HTML panel header are now redundant (Save/Discard moved to sidebar). The `#md-edit-bar` inside MD panel is gone. Clean up.

- [ ] **Step 1: Remove `btn-save-html` and `btn-cancel-html` from HTML panel header**

Find in `#panel-heads`:
```html
          <button id="btn-save-html" onclick="saveHtml()" style="display:none" class="success" title="Save enriched HTML">💾 Save HTML</button>
          <button id="btn-cancel-html" onclick="cancelHtmlEdit()" style="display:none" title="Cancel HTML editing">✕</button>
```

Delete both lines. The Save/Discard are now in `#edit-sidebar`.

- [ ] **Step 2: Verify `#md-edit-bar` is gone**

The `#md-edit-bar` div should already have been removed in Task 4 Step 1. Confirm:
```bash
grep -n "md-edit-bar" blog-migrator/ui/index.html
```
Expected: no matches (or only comments).

- [ ] **Step 3: Run full test suite**

```bash
python3 -m pytest blog-migrator/tests/ -q
```
Expected: same as before

- [ ] **Step 4: Full manual smoke test — all 26 flow paths**

With Sparge running at localhost:9000 and a post with HTML content, verify:

```
Flow 1:  HTML edit → Save             : saves, returns to review
Flow 2:  HTML edit → Save (server err): shows error, stays in edit
Flow 3:  MD edit   → Save             : saves, returns to review
Flow 4:  HTML edit → Discard (OK)     : discards, returns to review
Flow 5:  HTML edit → Discard (Cancel) : stays in edit mode
Flow 6:  Back to review (clean)       : exits immediately, no modal
Flow 7:  Back to review (dirty→Save)  : modal Save → saves → exits
Flow 8:  Back to review (dirty→Disc.) : modal Discard → exits
Flow 9:  Back to review (dirty→Cancel): stays in edit mode
Flow 10: Switch post (clean)          : switches immediately
Flow 11: Switch post (dirty→Save)     : modal Save → save → switch
Flow 12: Switch post (dirty→Disc.)    : modal Discard → switch post
Flow 13: Switch post (dirty→Cancel)   : stays on current post
Flow 14: HTML → live preview updates  : type → preview updates ≤300ms
Flow 15: MD   → live preview updates  : type → preview updates ≤300ms
Flow 16: editDirty=false on entry     : dirty indicator hidden
Flow 17: editDirty=true on first edit : dirty indicator shown
Flow 18: editDirty=false after save   : dirty indicator hidden
Flow 19: HTML scroll sync (ed→preview): editor scroll → preview scrolls
Flow 20: HTML scroll sync (prev→ed)   : preview scroll → editor scrolls
Flow 21: MD scroll sync (ed→preview)  : editor scroll → preview scrolls
Flow 22: MD scroll sync (prev→ed)     : preview scroll → editor scrolls
Flow 23: Nav restored after exit      : post list visible again
Flow 24: Panels restored after exit   : iframe + MD view restored
Flow 25: Enter MD edit: no MD yet     : shows alert "Generate MD first"
Flow 26: marked.js renders MD         : headers, bold, code highlighted
```

- [ ] **Step 5: Commit**

```bash
git add blog-migrator/ui/index.html
git commit -m "fix(ui): remove redundant panel header edit buttons — controls now in edit sidebar"
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| `editState` + `editDirty` replace old booleans | Task 2 |
| `scrollPercent()` + `scrollFromPercent()` pure helpers | Task 2 |
| JS unit tests for pure functions | Task 2 |
| `#edit-sidebar` HTML + CSS | Task 3 |
| marked.js CDN | Task 1 |
| `#md-preview` div | Task 1 |
| `enterEditMode(mode)` unified | Task 4 |
| Live preview HTML (iframe srcdoc) | Task 5 |
| Live preview MD (marked.parse) | Task 5 |
| Debounced 300ms | Task 5 |
| `editDirty = true` on first change | Task 5 |
| Edit mode scroll sync (editor→preview) | Task 6 |
| Edit mode scroll sync (preview→editor) | Task 6 |
| Scroll sync loop guard | Task 6 |
| `exitEditMode()` with modal guard | Task 7+8 |
| `exitEditModeImmediate()` | Task 8 |
| `saveEditContent()` for both HTML+MD | Task 7 |
| `discardEdit()` with confirm | Task 7 |
| Custom `promptUnsaved()` modal | Task 8 |
| `selectPost()` guard | Task 8 |
| Python integration tests (HTML cycle) | Task 9 |
| Python integration tests (MD cycle) | Task 9 |
| Original immutability test | Task 9 |
| Remove old panel header buttons | Task 10 |
| All 26 flow paths smoke tested | Task 10 |

**Placeholder scan:** None — all steps have concrete code or commands.

**Type consistency:** `editState` used consistently as `null | 'html' | 'md'` across all tasks. `saveEditContent()` referenced in Tasks 7 and 8. `exitEditModeImmediate()` defined in Task 8 and called in both `exitEditMode()` and `selectPost()`.
