# Edit Mode Redesign — Full-Screen Three-Partition Editor

## Goal

Replace the two separate per-panel edit modes with a unified full-screen editor experience. When editing HTML or MD, the existing three-partition layout is repurposed: left sidebar becomes edit controls, middle becomes the CodeMirror editor, right becomes a live preview. Linked scroll sync between editor and preview.

## Context

- Current nav sidebar (`#nav`, 252px) holds the post list, filters, and stats
- Current `#html-panel` shows the rendered HTML iframe
- Current `#md-panel` shows the rendered Markdown
- `editMode` (MD) and `htmlEditMode` (HTML) currently track separate edit states in `index.html`
- `selectPost()` already calls both cancel functions when switching posts

## Layout in Edit Mode

```
┌─────────────────────────────────────────────────────────────────┐
│ ┌──────────────┐ ┌──────────────────┐ ┌────────────────────┐   │
│ │ Edit sidebar │ │ CodeMirror       │ │ Live preview       │   │
│ │ (replaces    │ │ (replaces HTML   │ │ (replaces MD       │   │
│ │  #nav)       │ │  iframe)         │ │  rendered text)    │   │
│ │              │ │                  │ │                    │   │
│ │ ✎ EDITING    │ │  1 <article>     │ │  What is a Rule    │   │
│ │   HTML/MD    │ │  2 <h2>What…     │ │  Engine            │   │
│ │              │ │  3 <p>Drools…    │ │                    │   │
│ │ slug-name    │ │  4               │ │  Drools is a Rule  │   │
│ │              │ │  5 <figure…>     │ │  Engine but…       │   │
│ │ 💾 Save      │ │                  │ │                    │   │
│ │ ✕ Discard    │ │                  │ │  ▶ Watch on YouTube│   │
│ │              │ │                  │ │                    │   │
│ │ ← Back to   │ │                  │ │  ↕ synced scroll   │   │
│ │   review     │ │                  │ │                    │   │
│ └──────────────┘ └──────────────────┘ └────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Architecture

### New unified state

Replace `editMode` + `htmlEditMode` with:

```javascript
let editState = null;  // null | 'html' | 'md'
let editDirty = false; // true after first CodeMirror change
```

### New HTML element

Add `<div id="edit-sidebar">` (hidden by default) alongside `#nav`. When entering edit mode: hide `#nav`, show `#edit-sidebar`. On exit: reverse.

```html
<div id="edit-sidebar" style="display:none;width:252px;flex-shrink:0;background:#161b22;
     border-right:1px solid #30363d;display:none;flex-direction:column;padding:16px;gap:12px">
  <div id="edit-sidebar-mode" style="font-size:10px;color:#58a6ff;font-weight:bold;letter-spacing:.5px"></div>
  <div id="edit-sidebar-slug" style="font-size:11px;color:#8b949e;word-break:break-all;line-height:1.5"></div>
  <div style="border-top:1px solid #30363d;padding-top:10px;display:flex;flex-direction:column;gap:6px">
    <button onclick="saveEdit()" id="btn-edit-save" class="success" style="padding:6px">💾 Save</button>
    <button onclick="discardEdit()" id="btn-edit-discard" style="background:#2d0f0f;border-color:#f85149;color:#f85149;padding:6px">✕ Discard changes</button>
  </div>
  <div style="margin-top:auto">
    <button onclick="exitEditMode()" style="width:100%;padding:6px">← Back to review</button>
    <div style="font-size:10px;color:#484f58;margin-top:6px;text-align:center">Prompts if unsaved changes</div>
  </div>
</div>
```

### CodeMirror editors (reused from previous work)

- `mdEditor` (markdown mode) — already initialised lazily
- `htmlEditor` (htmlmixed mode) — already initialised lazily

Both editors register a `change` handler that sets `editDirty = true` and triggers the live preview update (debounced 300ms).

### Live preview

| Edit mode | Preview element | Update mechanism |
|---|---|---|
| HTML | `<iframe id="orig-frame">` | `iframe.srcdoc = htmlEditor.getValue()` |
| MD | `<div id="md-preview">` (new) | `div.innerHTML = marked.parse(mdEditor.getValue())` |

`marked.js` loaded from CDN (added to `<head>`).

### Scroll sync

Percentage-based: `scrollPct = scrollTop / (scrollHeight - clientHeight)`.

- HTML edit: CodeMirror `.on('scroll')` → apply percent to iframe `contentWindow.scrollY`
- MD edit: CodeMirror `.on('scroll')` → apply percent to `#md-preview` scrollTop
- Preview scroll → apply percent back to CodeMirror (`scrollTo(x, y)`)
- Mutual sync guard (bool flag) prevents feedback loops

## Exit flow paths

All paths go through `exitEditMode()`:

| Path | Condition | Behaviour |
|---|---|---|
| 💾 Save | — | POST save endpoint → on success: `editDirty=false`, `exitEditMode()` |
| ✕ Discard | — | `confirm('Discard all changes?')` → yes: `exitEditMode()` |
| ← Back to review | `editDirty === false` | Exit immediately |
| ← Back to review | `editDirty === true` | Modal: [Save] [Discard] [Cancel] |
| Navigate to different post | `editDirty === false` | Switch post immediately |
| Navigate to different post | `editDirty === true` | Modal: [Save] [Discard] [Cancel] → then switch |

`exitEditMode()`:
1. Set `editState = null`, `editDirty = false`
2. Hide `#edit-sidebar`, show `#nav`
3. Restore `#html-panel` to iframe, `#md-panel` to rendered MD
4. Re-render the current post in review mode

## Save/Discard modal

```javascript
// Returns: 'save' | 'discard' | 'cancel'
async function promptUnsaved() {
  // Uses a custom modal overlay (not browser confirm()) for styling consistency
}
```

Custom modal (not `window.confirm()`) so it's styled consistently with the dark UI.

## CDN addition

```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/9.1.6/marked.min.js"></script>
```

## Files changed

| File | Change |
|---|---|
| `blog-migrator/ui/index.html` | `#edit-sidebar` HTML; `editState`/`editDirty` state; unified enter/exit; live preview; scroll sync; modal; marked.js CDN |
| `blog-migrator/server.py` | No changes needed (GET /html + POST /save-html already added) |
| `blog-migrator/tests/test_server_api.py` | Integration tests for complete save/retrieve cycle |
| `blog-migrator/tests/test_edit_flow.py` | New: Python integration tests for all exit flow paths via HTTP |
| `blog-migrator/ui/tests/edit-mode.test.js` | New: pure-function JS unit tests (scroll sync math, dirty tracking, debounce) |

## Execution flow paths — complete list (all must be tested)

### Enter edit mode
1. Enter HTML edit mode — nav hides, edit sidebar shows, CodeMirror htmlmixed in middle, live iframe preview in right
2. Enter MD edit mode — nav hides, edit sidebar shows, CodeMirror markdown in middle, marked.js div in right

### Save
3. Save HTML (clean) — POST /save-html → 200 → exit edit mode → restore nav
4. Save HTML (server error) — POST /save-html → 500 → stay in edit mode, show error
5. Save MD (clean) — POST /save-md → 200 → exit edit mode → restore nav

### Discard
6. Discard (confirm OK) — modal confirms → exit edit mode → restore nav
7. Discard (confirm Cancel) — modal cancels → stay in edit mode, no change

### Back to review
8. Back to review, no unsaved changes — exit immediately
9. Back to review, unsaved → Save — modal [Save] → save then exit
10. Back to review, unsaved → Discard — modal [Discard] → exit without saving
11. Back to review, unsaved → Cancel — modal [Cancel] → stay in edit mode

### Navigate away
12. Switch post, no unsaved changes — switch immediately
13. Switch post, unsaved → Save — modal [Save] → save → switch post
14. Switch post, unsaved → Discard — modal [Discard] → switch post
15. Switch post, unsaved → Cancel — modal [Cancel] → stay on current post in edit mode

### Live preview
16. HTML edit: CodeMirror change → debounced (300ms) → iframe.srcdoc updated
17. MD edit: CodeMirror change → debounced (300ms) → marked.parse → div.innerHTML

### Scroll sync
18. HTML edit: editor scroll → iframe scrolls proportionally
19. HTML edit: iframe scroll → editor scrolls proportionally
20. MD edit: editor scroll → preview div scrolls proportionally
21. MD edit: preview div scroll → editor scrolls proportionally
22. Scroll sync guard prevents feedback loops

### Dirty tracking
23. Enter edit mode — `editDirty = false`
24. First CodeMirror change — `editDirty = true`
25. Save — `editDirty = false`
26. Discard — `editDirty = false`

## What does NOT change

- Scan, Generate MD, Validate MD actions unchanged
- The Scan button still runs enrichment + validation
- `GET /html` and `POST /save-html` endpoints unchanged
- The existing staged/accept/reject workflow unchanged
- Author filter, post list, stats unchanged
