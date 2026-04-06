# CodeMirror Editors Design

## Goal

Replace the plain `<textarea>` MD editor with CodeMirror (markdown mode), and add a new CodeMirror HTML editor to the HTML panel for editing the enriched HTML copy. Both editors share one CDN load, use the `material-darker` theme to match the existing dark UI.

## Context

- MD panel already has an edit mode (`btn-edit-md`, `textarea#md-editor`, `toggleEditMode()`, `saveContent()`)
- HTML panel shows a rendered iframe (`orig-frame`) loading the original HTML from the static file server
- Enriched HTML lives in `~/sparge-projects/{id}/enriched/{slug}.html` (written by Scan)
- No bundler — all JS loaded via `<script>` tags (same pattern as highlight.js)

## Part 1: CodeMirror loading

Add to `<head>` in `blog-migrator/ui/index.html`:

```html
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.css">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/theme/material-darker.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/xml/xml.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/javascript/javascript.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/css/css.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/htmlmixed/htmlmixed.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/markdown/markdown.min.js"></script>
```

`htmlmixed` depends on `xml`, `javascript`, and `css` — all must load first.

## Part 2: MD editor upgrade

**HTML change:** Replace `<textarea id="md-editor" ...>` with `<div id="md-editor" style="display:none;height:100%"></div>`

**JS change:** Add `let mdEditor = null;` near other state vars.

In `enterEditMode()`:
- If `mdEditor` is null: initialise `CodeMirror($('md-editor'), { mode:'markdown', theme:'material-darker', lineNumbers:true, lineWrapping:true, value: raw })`; store as `mdEditor`
- Else: `mdEditor.setValue(raw)`
- Show `#md-editor` div, call `mdEditor.refresh()`

In `cancelEdit()`: hide `#md-editor`, `mdEditor.setValue('')`

In `saveContent()`: replace `$('md-editor').value` with `mdEditor.getValue()`

**CSS:** Add `.CodeMirror { height: 100%; font-size: 13px; }` to keep it filling the panel.

## Part 3: HTML editor + endpoints

### New server endpoints (`blog-migrator/server.py`)

**`GET /api/posts/{slug}/html`**
- Reads `ENRICHED_DIR/{slug}.html` if exists, else `POSTS_DIR/{slug}.html`
- Returns raw HTML as `text/html; charset=utf-8`
- 404 if neither exists

**`POST /api/posts/{slug}/save-html`**
- Writes request body to `ENRICHED_DIR/{slug}.html`
- Creates `ENRICHED_DIR` if not exists
- Returns updated post state (same as `save-md`)

Register in `do_GET`:
```python
elif rest.endswith('/html') and '/' not in rest[:-5]:
    self._api_post_html(rest[:-5])
```

Register in `do_POST`:
```python
elif rest.endswith('/save-html'):
    self._api_save_html(rest[:-len('/save-html')], body)
```

### New UI elements in HTML panel toolbar

Add alongside existing scan/generate buttons:
```html
<button id="btn-edit-html" onclick="toggleHtmlEditMode()">✎ Edit HTML</button>
<button id="btn-save-html" onclick="saveHtml()" style="display:none">💾 Save HTML</button>
<button id="btn-cancel-html" onclick="cancelHtmlEdit()" style="display:none">✕</button>
```

Add inside `html-panel` div, alongside iframe:
```html
<div id="html-editor" style="display:none;height:100%"></div>
```

### New JS state and functions

```javascript
let htmlEditMode = false;
let htmlEditor = null;

async function toggleHtmlEditMode() {
  htmlEditMode ? cancelHtmlEdit() : enterHtmlEditMode();
}

async function enterHtmlEditMode() {
  const r = await fetch(`${API}/api/posts/${encodeURIComponent(currentSlug)}/html`);
  if (!r.ok) return;
  const raw = await r.text();
  if (!htmlEditor) {
    htmlEditor = CodeMirror($('html-editor'), {
      mode: 'htmlmixed', theme: 'material-darker',
      lineNumbers: true, lineWrapping: false, value: raw
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
    method: 'POST', body: content,
    headers: { 'Content-Type': 'text/html; charset=utf-8' }
  });
  if (!r.ok) return;
  cancelHtmlEdit();
  // Reload iframe with saved content via srcdoc
  $('orig-frame').srcdoc = content;
}
```

### Cleanup on post switch

In the existing post-switch handler (where `cancelEdit()` is called), also call `cancelHtmlEdit()`.

## Files changed

| File | Change |
|---|---|
| `blog-migrator/ui/index.html` | CDN tags; replace textarea with div; upgrade MD JS; add HTML editor HTML + JS |
| `blog-migrator/server.py` | `_api_post_html()` and `_api_save_html()` methods; routing |

## What does NOT change

- `save-md` endpoint and MD save flow unchanged (only how content is read: `getValue()` vs `.value`)
- Scroll sync between panels unchanged (uses iframe, not editor)
- Scan/generate/validate flows unchanged
- Original HTML never written to
