# Archive Room Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle `ui/index.html` from GitHub-dark to the Archive Room aesthetic — parchment background, ink-black primary, muted-slate accent (`#4a6a8a`), Georgia serif logo — with no changes to layout, behaviour, or server code.

**Architecture:** All palette changes are in the single `<style>` block in `ui/index.html`. CSS custom properties are introduced at `:root` as a unified token system, then all old dark hex values are replaced. One custom `<style>` block overrides CodeMirror's default theme for the light editor. One small JS addition wires the ☀/☾ toggle to `localStorage` and calls `editor.setOption('theme', ...)` on active editors.

**Tech Stack:** Vanilla CSS custom properties, CodeMirror 5 (`default` theme for light, `material-darker` for dark), highlight.js `github.min.css` (already light — no change).

**Spec:** `docs/superpowers/specs/2026-04-09-archive-room-redesign.md`

**Verify throughout:** Start the server before Task 1 and keep it running. After every task, open `http://localhost:9000/ui/` and confirm the visual change matches the spec.

```bash
cd ~/claude/sparge && python3 server.py
```

---

### Task 1: Add CSS custom properties and swap core background/chrome/border colours

**Files:**
- Modify: `ui/index.html` — `:root` block + global colour replacements

This task defines the palette tokens and does a bulk replace of the most pervasive dark values. After this task the app will look broken (light chrome, dark text still referencing old colours) — that is expected. Subsequent tasks clean up each component.

- [ ] **Step 1: Add `:root` token block**

Inside `ui/index.html`, find the opening `<style>` tag (around line 22) and add this block immediately after it, before the `* { box-sizing... }` reset:

```css
:root {
  --bg:           #f4f0e8;
  --chrome:       #ede7d9;
  --border:       #c8baa0;
  --border-light: #ddd4c0;
  --ink:          #2a2218;
  --sepia:        #5a4a30;
  --muted:        #8a7a5a;
  --accent:       #4a6a8a;
  --accent-tint:  #ecf0f4;
  --approve:      #2a6a2a;
  --approve-bg:   #e8f4e8;
  --warn:         #c87020;
  --error:        #8a2a2a;
}
```

- [ ] **Step 2: Replace body and main background colours**

Find and replace these exact values in the `<style>` block:

| Find | Replace with |
|---|---|
| `background:#0d1117` | `background:var(--bg)` |
| `background:#161b22` | `background:var(--chrome)` |
| `border-bottom:1px solid #30363d` | `border-bottom:1px solid var(--border)` |
| `border-right:1px solid #30363d` | `border-right:1px solid var(--border)` |
| `border-left:1px solid #30363d` | `border-left:1px solid var(--border)` |
| `border-top:1px solid #30363d` | `border-top:1px solid var(--border)` |
| `border:1px solid #30363d` | `border:1px solid var(--border)` |
| `color:#c9d1d9` | `color:var(--sepia)` |
| `color:#e6edf3` | `color:var(--ink)` |
| `color:#8b949e` | `color:var(--muted)` |

Do this replacement carefully — use your editor's find/replace with exact string matching. These are the most common values and appear 30–50 times each.

- [ ] **Step 3: Update `body` rule**

Find the `body` rule (around line 27) and update it:

```css
body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
       background:var(--bg); color:var(--sepia);
       display:flex; flex-direction:column; height:100vh; overflow:hidden; font-size:13px; }
```

- [ ] **Step 4: Verify server starts and page loads**

```bash
curl -s http://localhost:9000/ui/ | grep -c "Sparge"
```
Expected output: `1` (server responds, page loads)

Open `http://localhost:9000/ui/` — the page will look partially restyled. The background should be parchment. Expect some elements still dark; that's fine.

- [ ] **Step 5: Commit**

```bash
cd ~/claude/sparge
git add ui/index.html
git commit -m "style: add CSS tokens and bulk-replace core background/border colours"
```

---

### Task 2: Topbar, logo, and tab navigation

**Files:**
- Modify: `ui/index.html` — `#topbar`, `#logo`, `.ttab` CSS rules

- [ ] **Step 1: Update topbar border and logo**

Find the `#topbar` rule and update `border-bottom` to `2px`:

```css
#topbar { flex-shrink:0; background:var(--chrome); border-bottom:2px solid var(--ink);
          padding:0 16px; display:flex; align-items:stretch; height:44px; }
```

Find the `#logo` rule and update it:

```css
#logo { display:flex; align-items:center; gap:6px; font-weight:700; font-size:16px;
        font-family:Georgia,'Times New Roman',serif; font-style:italic;
        color:var(--ink); padding-right:16px; border-right:1px solid var(--border); margin-right:4px; }
#logo em { color:var(--ink); font-style:normal; }
```

(The `em` inside logo was previously GitHub blue — it should now match ink, keeping the italic logo as the sole identity marker.)

- [ ] **Step 2: Update tab styles**

Find the `.ttab` rules:

```css
.ttab { padding:0 14px; cursor:pointer; border-bottom:2px solid transparent;
        color:var(--muted); display:flex; align-items:center; font-size:13px; transition:all .15s; }
.ttab:hover { color:var(--ink); }
.ttab.active { color:var(--accent); border-bottom-color:var(--accent); font-weight:600; }
```

- [ ] **Step 3: Visual check**

Open `http://localhost:9000/ui/`. The topbar should show:
- Parchment background with a heavier ink-black bottom border
- "Sparge" logo in Georgia italic, ink colour (not blue)
- Active tab underlined in slate blue (`#4a6a8a`)

- [ ] **Step 4: Commit**

```bash
git add ui/index.html
git commit -m "style: topbar, logo (Georgia serif), and tab accent colour"
```

---

### Task 3: Post list sidebar — selected state and row styling

**Files:**
- Modify: `ui/index.html` — `#nav`, `.pi`, `.pi-*` rules

- [ ] **Step 1: Update nav background**

Find `#nav` rule — background is already `var(--chrome)` from Task 1. Update the border:

```css
#nav { width:252px; flex-shrink:0; background:var(--chrome); border-right:1px solid var(--border);
       display:flex; flex-direction:column; overflow:hidden; }
```

- [ ] **Step 2: Update post item rows**

Find `.pi` and update:

```css
.pi { padding:5px 9px; border-bottom:1px solid var(--border-light); cursor:pointer; transition:background .1s;
      border-left:2px solid transparent; }
.pi:hover { background:var(--bg); }
.pi.selected { background:var(--accent-tint); border-left:2px solid var(--accent); padding-left:7px; }
```

- [ ] **Step 3: Update post item text**

Find `.pi-date` and `.pi-title`:

```css
.pi-date { font-size:8px; color:var(--muted); margin-bottom:2px;
           font-family:'SFMono-Regular',Consolas,monospace; }
.pi-title { font-size:11px; color:var(--sepia); line-height:1.3; margin-bottom:4px;
            display:flex; align-items:baseline; gap:4px; }
.pi.selected .pi-title { color:var(--ink); font-weight:600; }
.pi-copy { opacity:0; cursor:pointer; font-size:10px; color:var(--muted); flex-shrink:0;
           transition:opacity .15s; user-select:none; }
.pi:hover .pi-copy { opacity:1; }
.pi-copy:hover { color:var(--ink); }
```

- [ ] **Step 4: Visual check**

Scroll the post list. Unselected rows should be compact with sepia titles. The selected post should have a slate left border and faint blue-grey tint. Hover should lighten the row.

- [ ] **Step 5: Commit**

```bash
git add ui/index.html
git commit -m "style: post list rows — archive selected state, slate accent border"
```

---

### Task 4: Filters, stats panel, and nav section labels

**Files:**
- Modify: `ui/index.html` — `.filter-zone`, `.fb`, `.scope-btn`, `.srow`, `#nav-stats` rules

- [ ] **Step 1: Update filter buttons**

Find `.fb` and update:

```css
.fb { background:none; border:1px solid transparent; border-radius:2px;
      padding:3px 2px; font-size:9px; color:var(--muted); cursor:pointer; text-align:center; }
.fb:hover { background:var(--bg); color:var(--ink); }
.fb.active { background:var(--accent); border-color:var(--accent); color:var(--bg); }
```

Find `.scope-btn`:

```css
.scope-btn { background:none; border:1px solid transparent; border-radius:2px;
             padding:3px 2px; font-size:9px; color:var(--muted); cursor:pointer; text-align:center; }
.scope-btn:hover { background:var(--bg); color:var(--ink); }
```

- [ ] **Step 2: Update stats panel labels and value colours**

Find `.srow`, `.sl`, `.sv` rules:

```css
.sl { font-size:11px; color:var(--muted); }
.sv { font-size:11px; font-weight:600; }
.sv.g { color:var(--approve) }
.sv.b { color:var(--accent) }
.sv.o { color:var(--warn) }
.sv.m { color:var(--muted) }
```

Find `#nav-stats h3`:

```css
#nav-stats h3 { font-size:9px; text-transform:uppercase; letter-spacing:.1em;
                color:var(--muted); margin-bottom:8px;
                font-family:'SFMono-Regular',Consolas,monospace; }
```

Find `.gl` (the uppercase section labels used throughout):

```css
.gl { font-size:9px; text-transform:uppercase; letter-spacing:.08em; color:var(--muted);
      font-family:'SFMono-Regular',Consolas,monospace; }
```

- [ ] **Step 3: Update progress bar**

Find `#pfill`:

```css
#pfill { height:100%; border-radius:2px; transition:width .4s;
         background:linear-gradient(90deg, var(--approve) 0%, var(--accent) 100%); }
```

Find `#pbar`:

```css
#pbar { height:3px; background:var(--border); border-radius:2px; margin-top:8px; overflow:hidden; }
```

- [ ] **Step 4: Update expand arrow and issue filter rows**

Find `.expand-arrow`:

```css
.expand-arrow { font-size:13px; color:var(--muted); display:inline-block;
                transition:transform 0.15s; flex-shrink:0; line-height:1; }
```

Find `.itr` (issue type rows in breakdown):

```css
.itr { display:flex; justify-content:space-between; align-items:center;
       padding:2px 5px; border-radius:2px; cursor:pointer; margin-bottom:1px; }
.itr:hover { background:var(--bg); }
.itr.active { background:var(--accent-tint); }
.itr-label { font-size:10px; color:var(--muted); }
.itr.active .itr-label { color:var(--accent); }
.itr-count.err { color:var(--error); }
.itr-count.warn { color:var(--warn); }
```

- [ ] **Step 5: Visual check**

The sidebar stats section and filter area should now show warm parchment tones with slate-accent active states. No GitHub blue anywhere.

- [ ] **Step 6: Commit**

```bash
git add ui/index.html
git commit -m "style: filters, nav stats panel, section labels — archive palette"
```

---

### Task 5: Buttons, action bar, and post crumb

**Files:**
- Modify: `ui/index.html` — `button`, `#post-action-bar`, `#post-crumb` rules

- [ ] **Step 1: Update global button styles**

Find the `button` base rule and update:

```css
button { background:var(--chrome); color:var(--sepia); border:1px solid var(--border);
         border-radius:2px; padding:5px 12px; cursor:pointer; font-size:11px;
         display:flex; align-items:center; gap:5px; white-space:nowrap; transition:all .15s; }
button:hover { background:var(--bg); border-color:var(--muted); color:var(--ink); }
button:disabled { opacity:.35; cursor:default; }
button.active { background:var(--accent); border-color:var(--accent); color:var(--bg); }
button.success { background:var(--approve-bg); border-color:var(--approve); color:var(--approve); }
button.success:hover { background:var(--approve); color:var(--bg); }
button.warn { background:#f4e8e0; border-color:var(--warn); color:var(--warn); }
```

- [ ] **Step 2: Update action bar**

Find `#post-action-bar`:

```css
#post-action-bar {
  flex-shrink:0; background:var(--chrome); border-bottom:1px solid var(--border);
  padding:5px 14px; display:flex; align-items:center; gap:6px;
}
```

- [ ] **Step 3: Update post crumb**

Find `#post-crumb` rules:

```css
#post-crumb { flex:1; min-width:0; font-size:11px; color:var(--muted);
              display:flex; align-items:center; gap:5px;
              overflow:hidden; white-space:nowrap; }
#post-crumb strong { color:var(--ink); font-weight:600; }
#post-crumb .crumb-date { color:var(--muted); margin-left:6px;
                           font-family:'SFMono-Regular',Consolas,monospace; font-size:9px; }
.crumb-copy { cursor:pointer; font-size:11px; color:var(--muted); flex-shrink:0; user-select:none; }
.crumb-copy:hover { color:var(--ink); }
```

- [ ] **Step 4: Update separator**

Find `.sep`:

```css
.sep { width:1px; height:22px; background:var(--border); flex-shrink:0; }
```

- [ ] **Step 5: Update the MD edit button active state**

Find `#btn-edit-md.editing`:

```css
#btn-edit-md.editing { background:var(--accent-tint); border-color:var(--accent); color:var(--accent); }
```

- [ ] **Step 6: Visual check**

Click a post. The action bar should show parchment chrome, ink-black title, sepia date. Buttons should have 2px radius (less rounded than before). Approve button will get its colour in Task 7 (badge update).

- [ ] **Step 7: Commit**

```bash
git add ui/index.html
git commit -m "style: buttons (2px radius), action bar, post crumb — archive palette"
```

---

### Task 6: Panel headers and content panels

**Files:**
- Modify: `ui/index.html` — `.ph`, `.panel`, `#md-wrap`, `#md-empty`, `.fm-card` rules

- [ ] **Step 1: Update panel header labels**

Find `.ph` and `.ph+.ph`:

```css
.ph { flex:1; padding:5px 14px; font-size:8px; text-transform:uppercase;
      letter-spacing:.1em; color:var(--muted); display:flex; align-items:center; gap:8px;
      font-family:'SFMono-Regular',Consolas,monospace; background:var(--chrome); }
.ph+.ph { border-left:1px solid var(--border); }
```

Find `#panel-heads`:

```css
#panel-heads { display:flex; flex-shrink:0; background:var(--chrome); border-bottom:1px solid var(--border); }
```

- [ ] **Step 2: Update Markdown render panel**

Find `#md-wrap` and its child selectors:

```css
#md-wrap { padding:24px 32px; max-width:800px; margin:0 auto; line-height:1.7; }
#md-wrap h1,#md-wrap h2 { border-bottom:1px solid var(--border); padding-bottom:.3em;
                           margin:1.5em 0 .6em; color:var(--ink); }
#md-wrap h3,#md-wrap h4 { margin:1.2em 0 .4em; color:var(--accent); }
#md-wrap p  { margin:.7em 0; color:var(--sepia); }
#md-wrap a  { color:var(--accent); }
#md-wrap code { background:var(--chrome); border:1px solid var(--border); border-radius:2px;
                padding:2px 6px; font-size:.875em; color:var(--sepia); }
#md-wrap pre { background:var(--chrome); border:1px solid var(--border); border-radius:2px;
               padding:0; overflow-x:auto; margin:1em 0; }
#md-wrap pre code { background:none; border:none; padding:16px; display:block;
                    color:var(--ink); font-size:.875em; }
#md-wrap blockquote { border-left:3px solid var(--border); margin:1em 0;
                      padding:.5em 1em; color:var(--muted); }
#md-wrap ul,#md-wrap ol { margin:.7em 0 .7em 1.5em; }
#md-wrap li { margin:.3em 0; }
#md-wrap img { max-width:100%; border-radius:2px; margin:1em 0; border:1px solid var(--border); }
#md-wrap table { border-collapse:collapse; width:100%; margin:1em 0; }
#md-wrap th,#md-wrap td { border:1px solid var(--border); padding:6px 13px; }
#md-wrap th { background:var(--chrome); }
```

- [ ] **Step 3: Update front-matter card**

Find `.fm-card` and children:

```css
.fm-card { background:var(--chrome); border:1px solid var(--border); border-radius:2px;
           padding:16px 20px; margin-bottom:20px; }
.fm-card h1 { font-size:20px; color:var(--ink); border:none; margin-bottom:6px; }
.fm-card .fm-meta { font-size:12px; color:var(--muted); font-family:'SFMono-Regular',Consolas,monospace; }
.fm-card .fm-tags { margin-top:8px; display:flex; gap:6px; flex-wrap:wrap; }
.fm-tag { background:var(--accent-tint); border:1px solid var(--accent); color:var(--accent);
          border-radius:2px; padding:2px 10px; font-size:11px; }
```

- [ ] **Step 4: Update empty state**

Find `#md-empty`:

```css
#md-empty { display:flex; flex-direction:column; align-items:center; justify-content:center;
            height:100%; gap:12px; color:var(--muted); text-align:center; padding:40px; }
```

- [ ] **Step 5: Update divider**

Find `#divider`:

```css
#divider { width:4px; background:var(--border); cursor:col-resize; flex-shrink:0; }
#divider:hover { background:var(--accent); }
```

- [ ] **Step 6: Visual check**

Open a post with Markdown. The MD panel should render with ink headings, sepia body, slate links. The panel headers ("HTML" / "MARKDOWN" labels) should be small mono uppercase in warm grey.

- [ ] **Step 7: Commit**

```bash
git add ui/index.html
git commit -m "style: panel headers (mono uppercase), MD render panel — archive palette"
```

---

### Task 7: Badges, floating tooltip, and issue panel

**Files:**
- Modify: `ui/index.html` — `.badge`, `.b-*`, `#issue-panel`, `.irow`, `#float-tip` rules

- [ ] **Step 1: Update badge colours**

Find the badge CSS block (`.badge`, `.b-ok`, `.b-warn`, `.b-err`, `.b-none`, `.b-blue`, `.b-stale`):

```css
.badge { font-size:9px; padding:1px 6px; border-radius:2px; font-weight:600; }
.b-ok   { background:var(--approve-bg); color:var(--approve); border:1px solid var(--approve) }
.b-warn { background:#f4e8e0; color:var(--warn); border:1px solid var(--warn) }
.b-err  { background:#f4e0e0; color:var(--error); border:1px solid var(--error) }
.b-none { background:var(--chrome); color:var(--muted); border:1px solid var(--border) }
.b-blue { background:var(--accent-tint); color:var(--accent); border:1px solid var(--accent) }
.b-stale{ background:#f4e8e0; color:var(--warn); border:1px solid var(--warn) }
```

- [ ] **Step 2: Update floating tooltip**

Find `#float-tip`:

```css
#float-tip {
  position:fixed; display:none;
  background:var(--chrome); border:1px solid var(--border);
  color:var(--ink); padding:5px 10px; border-radius:2px;
  font-size:11px; line-height:1.4;
  white-space:normal; word-break:break-word; max-width:480px;
  z-index:9999; pointer-events:none;
  box-shadow:0 4px 16px rgba(42,34,24,.25);
}
```

- [ ] **Step 3: Update issue panel**

Find `#issue-panel` and related selectors:

```css
#issue-panel { flex-shrink:0; border-top:1px solid var(--border); background:var(--bg);
               display:flex; flex-direction:column; height:200px; }
#issue-panel-hdr { display:flex; align-items:center; gap:10px; padding:5px 14px;
                   border-bottom:1px solid var(--border-light); flex-shrink:0; }
#issue-panel-hdr span { font-size:9px; text-transform:uppercase; letter-spacing:.08em;
                         color:var(--muted); flex:1; font-family:'SFMono-Regular',Consolas,monospace; }
.issue-col-hd { padding:3px 12px; font-size:9px; text-transform:uppercase; letter-spacing:.05em;
                color:var(--muted); font-family:'SFMono-Regular',Consolas,monospace; }
.issue-col+.issue-col { border-left:1px solid var(--border-light); }
```

Find `.irow` rules:

```css
.irow { padding:3px 12px; font-size:11px; font-family:monospace; border-left:3px solid transparent; }
.irow.err  { color:var(--error); border-left-color:var(--error); background:rgba(138,42,42,.04); }
.irow.warn { color:var(--warn); border-left-color:var(--warn); background:rgba(200,112,32,.04); }
.irow.clickable { cursor:pointer; }
.irow.clickable:hover { filter:brightness(.95); background-color:rgba(42,34,24,.04); }
.irow.highlighted.err  { background:rgba(138,42,42,.13); outline:1px solid rgba(138,42,42,.4); }
.irow.highlighted.warn { background:rgba(200,112,32,.13); outline:1px solid rgba(200,112,32,.4); }
.no-iss { padding:6px 12px; font-size:11px; color:var(--muted); font-style:italic; }
```

Find `.irow-tooltip`:

```css
.irow-tooltip { position:fixed; background:var(--chrome); border:1px solid var(--error);
                color:var(--error); font-size:11px; padding:3px 8px; border-radius:2px;
                pointer-events:none; z-index:9999; white-space:nowrap; }
```

Find `.md-absent-marker`:

```css
.md-absent-marker { border-top:2px dashed var(--error); border-bottom:2px dashed var(--error);
                    padding:3px 12px; margin:6px 0; background:rgba(138,42,42,.04);
                    font-size:10px; color:var(--error); font-style:italic; cursor:default; }
#md-wrap .md-hl { outline:3px solid var(--error) !important; outline-offset:2px;
                  background:rgba(138,42,42,.1) !important; border-radius:2px; scroll-margin-top:60px; }
#md-wrap mark.md-hl { display:inline; background:rgba(138,42,42,.23) !important;
                       outline:2px solid var(--error) !important; outline-offset:1px; }
```

Find `#issue-resize-handle`:

```css
#issue-resize-handle { height:5px; flex-shrink:0; cursor:ns-resize; background:var(--chrome);
                       display:flex; align-items:center; justify-content:center; }
#issue-resize-handle:hover, #issue-resize-handle.dragging { background:var(--border); }
#issue-resize-handle::after { content:''; display:block; width:32px; height:2px;
                              background:var(--muted); border-radius:1px; }
```

- [ ] **Step 4: Visual check**

Open a post and trigger the issue panel. Error rows should be dark red on faint rose background. Warning rows amber. Badges in the post list should use the new warm palette. No orange, no GitHub green.

- [ ] **Step 5: Commit**

```bash
git add ui/index.html
git commit -m "style: badges, issue panel, floating tooltip — archive error/warn colours"
```

---

### Task 8: Diff modal, config panel, and tab bar

**Files:**
- Modify: `ui/index.html` — `#diff-modal`, `#cfg-overlay`, `#tabbar` rules

- [ ] **Step 1: Update diff modal**

Find `#diff-modal`, `#diff-box`, `#diff-hdr` and related:

```css
#diff-modal { display:none; position:fixed; inset:0; background:rgba(42,34,24,.65);
              z-index:1000; align-items:center; justify-content:center; }
#diff-box { background:var(--chrome); border:1px solid var(--border); border-radius:4px;
            width:90vw; height:82vh; display:flex; flex-direction:column;
            box-shadow:0 8px 32px rgba(42,34,24,.3); }
#diff-hdr { flex-shrink:0; padding:12px 20px; border-bottom:1px solid var(--border);
            display:flex; align-items:flex-start; justify-content:space-between; gap:16px; }
#diff-hdr h3 { font-size:15px; color:var(--ink); margin-bottom:3px; }
#diff-stats .add { color:var(--approve) }
#diff-stats .del { color:var(--error) }
#diff-stats { font-size:12px; color:var(--muted); }
#diff-close { background:none; border:none; color:var(--muted); cursor:pointer;
              font-size:18px; line-height:1; padding:2px 6px; flex-shrink:0; }
#diff-close:hover { color:var(--ink); }
.dcl { flex:1; padding:4px 12px; font-size:9px; text-transform:uppercase;
       letter-spacing:.06em; color:var(--muted); font-family:'SFMono-Regular',Consolas,monospace; }
.dcl+.dcl { border-left:1px solid var(--border); }
#diff-left-wrap,#diff-right-wrap { flex:1; overflow:auto; min-width:0;
  font-family:'SFMono-Regular',Consolas,monospace; font-size:12px; line-height:1.6; }
#diff-right-wrap { border-left:1px solid var(--border); }
.dr { padding:1px 12px; white-space:pre-wrap; word-break:break-word; min-height:1.6em; }
.dr.add   { background:var(--approve-bg); color:var(--approve); }
.dr.del   { background:#f4e0e0; color:var(--error); }
.dr.ctx   { color:var(--muted); }
.dr.empty { background:var(--bg); }
.dr.skip  { color:var(--muted); background:var(--bg); font-style:italic;
            border-top:1px solid var(--border-light); border-bottom:1px solid var(--border-light); }
#diff-ftr { flex-shrink:0; padding:12px 20px; border-top:1px solid var(--border);
            display:flex; justify-content:flex-end; align-items:center; gap:10px; }
#diff-ftr span { flex:1; font-size:12px; color:var(--muted); }
#btn-keep    { background:var(--chrome); color:var(--sepia); border:1px solid var(--border); }
#btn-keep:hover { background:var(--bg); }
#btn-replace { background:var(--approve-bg); color:var(--approve); border-color:var(--approve); }
#btn-replace:hover { background:var(--approve); color:var(--bg); }
```

- [ ] **Step 2: Update config panel**

Find `#cfg-overlay`, `#cfg-panel` and related:

```css
#cfg-overlay { display:none; position:fixed; inset:0; background:rgba(42,34,24,.5);
               z-index:100; justify-content:flex-end; }
#cfg-overlay.open { display:flex; }
#cfg-panel { background:var(--chrome); border-left:2px solid var(--ink); width:380px;
             height:100%; overflow-y:auto; padding:24px;
             box-shadow:-8px 0 32px rgba(42,34,24,.2); display:flex; flex-direction:column; }
#cfg-panel h2 { font-size:15px; color:var(--ink); margin-bottom:18px; }
.cfg-sec h3 { font-size:9px; text-transform:uppercase; letter-spacing:.08em;
              color:var(--muted); margin-bottom:10px; font-family:'SFMono-Regular',Consolas,monospace; }
.cfg-f label { display:block; font-size:11px; color:var(--muted); margin-bottom:4px; }
.cfg-f input { width:100%; background:var(--bg); border:1px solid var(--border); border-radius:2px;
               padding:7px 10px; color:var(--ink); font-size:12px; font-family:monospace; }
.cfg-f input:focus { outline:none; border-color:var(--accent); }
.cfg-note { font-size:10px; color:var(--muted); margin-top:3px; }
#cfg-ftr { margin-top:auto; padding-top:16px; border-top:1px solid var(--border); display:flex; gap:8px; }
```

- [ ] **Step 3: Update tab bar (single-page mode)**

Find `#tabbar` and `.tab`:

```css
#tabbar { flex-shrink:0; background:var(--chrome); border-bottom:1px solid var(--border);
          padding:0 16px; display:none; }
.tab { padding:8px 20px; font-size:13px; cursor:pointer;
       border-bottom:2px solid transparent; color:var(--muted); transition:all .15s; }
.tab:hover { color:var(--ink); }
.tab.active { color:var(--accent); border-bottom-color:var(--accent); font-weight:600; }
```

- [ ] **Step 4: Visual check**

Open the diff modal (edit a post, make a change, save). The modal should use parchment chrome, warm shadow. Added lines green, deleted lines dark-red. Open config panel — parchment background, ink-black left border.

- [ ] **Step 5: Commit**

```bash
git add ui/index.html
git commit -m "style: diff modal, config panel, tab bar — archive palette"
```

---

### Task 9: Edit sidebar reskin

**Files:**
- Modify: `ui/index.html` — `#edit-sidebar`, `#edit-sidebar-*` rules

- [ ] **Step 1: Update edit sidebar container**

Find `#edit-sidebar`:

```css
#edit-sidebar {
  display: none;
  width: 252px;
  flex-shrink: 0;
  background: var(--chrome);
  border-right: 1px solid var(--border);
  flex-direction: column;
  padding: 16px;
  gap: 12px;
  overflow-y: auto;
}
```

- [ ] **Step 2: Update edit sidebar labels**

Find `#edit-sidebar-mode`, `#edit-sidebar-slug`, `#edit-sidebar-dirty`, `.edit-sidebar-divider`:

```css
#edit-sidebar-mode { font-size:9px; color:var(--accent); font-weight:700;
                     letter-spacing:.08em; text-transform:uppercase;
                     font-family:'SFMono-Regular',Consolas,monospace; }
#edit-sidebar-slug { font-size:11px; color:var(--muted); word-break:break-all; line-height:1.5;
                     font-family:'SFMono-Regular',Consolas,monospace; }
#edit-sidebar-dirty { font-size:10px; color:var(--warn); display:none; font-weight:600; }
.edit-sidebar-divider { border-top:1px solid var(--border); }
```

- [ ] **Step 3: Visual check**

Enter edit mode on a post. The left sidebar should transform: parchment background, "✎ EDITING HTML" label in slate (`--accent`), slug in mono warm grey. The border separating it from the editor should be `--border` tan.

- [ ] **Step 4: Commit**

```bash
git add ui/index.html
git commit -m "style: edit sidebar — slate accent mode label, archive chrome"
```

---

### Task 10: CodeMirror light theme

**Files:**
- Modify: `ui/index.html` — add custom CodeMirror theme CSS after the CodeMirror stylesheet links

The `default` theme in CodeMirror 5 gives a white background. We'll override it with warm parchment colours by writing a custom theme block scoped to `body[data-editor-theme="light"]`.

- [ ] **Step 1: Add `data-editor-theme` attribute to `<body>`**

Find the `<body>` opening tag and add the attribute:

```html
<body data-editor-theme="light">
```

- [ ] **Step 2: Add custom CodeMirror light theme CSS**

After the CodeMirror stylesheet `<link>` tags (after line ~346), add a new `<style>` block:

```html
<style id="cm-light-theme">
/* CodeMirror light theme — archive-room warm parchment */
body[data-editor-theme="light"] .CodeMirror {
  background: #f0e8d4;
  color: #2a1a08;
}
body[data-editor-theme="light"] .CodeMirror-gutters {
  background: #e8dcc4;
  border-right: 1px solid #c8a87a;
  color: #8a6a3a;
}
body[data-editor-theme="light"] .CodeMirror-cursor {
  border-left: 1px solid #2a1a08;
}
body[data-editor-theme="light"] .CodeMirror-selected {
  background: #d8c8a8;
}
body[data-editor-theme="light"] .CodeMirror-activeline-background {
  background: #e8dcc4;
}
/* HTML/XML syntax — htmlmixed mode */
body[data-editor-theme="light"] .cm-tag    { color: #8a4a20; }
body[data-editor-theme="light"] .cm-attribute { color: #5a3090; }
body[data-editor-theme="light"] .cm-string { color: #2a6a2a; }
body[data-editor-theme="light"] .cm-comment { color: #a08050; font-style: italic; }
body[data-editor-theme="light"] .cm-bracket { color: #8a4a20; }
body[data-editor-theme="light"] .cm-atom   { color: #5a3090; }
/* Markdown mode */
body[data-editor-theme="light"] .cm-header { color: #4a6a8a; font-weight: bold; }
body[data-editor-theme="light"] .cm-link   { color: #4a6a8a; }
body[data-editor-theme="light"] .cm-url    { color: #4a6a8a; }
body[data-editor-theme="light"] .cm-code   { color: #8a4a20; background: #e8dcc4; }
body[data-editor-theme="light"] .cm-em     { font-style: italic; color: #5a3090; }
body[data-editor-theme="light"] .cm-strong { font-weight: bold; color: #2a1a08; }
body[data-editor-theme="light"] .cm-quote  { color: #8a6a3a; font-style: italic; }
</style>
```

- [ ] **Step 3: Change default CodeMirror theme from `material-darker` to `default`**

Find the two `CodeMirror(...)` calls in `enterEditMode` (around lines 946 and 955). Change `theme:'material-darker'` to `theme:'default'` in both:

```javascript
htmlEditor = CodeMirror($('html-editor'), { mode:'htmlmixed', theme:'default', lineNumbers:true, lineWrapping:false, value:raw });
```

```javascript
mdEditor = CodeMirror($('html-editor'), { mode:'markdown', theme:'default', lineNumbers:true, lineWrapping:true, value:raw });
```

- [ ] **Step 4: Visual check**

Enter edit mode. The editor panel should show warm cream background (`#f0e8d4`), HTML tags in rust brown, attributes in purple, strings in green, comments in tan-italic. Markdown headings should be slate blue. The gutter should be slightly darker cream.

- [ ] **Step 5: Commit**

```bash
git add ui/index.html
git commit -m "style: CodeMirror light theme — warm parchment with sepia/slate syntax colours"
```

---

### Task 11: Editor dark theme toggle

**Files:**
- Modify: `ui/index.html` — edit sidebar HTML + JS toggle function

- [ ] **Step 1: Add toggle button to edit sidebar HTML**

Find the `#edit-sidebar` div in the HTML body (not the CSS). It currently contains elements like `#edit-sidebar-mode`, `#edit-sidebar-slug`, `#edit-sidebar-dirty`. Add the toggle button as the last child before the closing `</div>`:

```html
<div class="edit-sidebar-divider"></div>
<div style="display:flex; align-items:center; justify-content:space-between; margin-top:auto; padding-top:4px;">
  <span style="font-size:8px; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); font-family:'SFMono-Regular',Consolas,monospace;">Editor</span>
  <button id="btn-editor-theme" onclick="toggleEditorTheme()" title="Toggle editor theme" style="padding:3px 8px; font-size:10px;">☀ Light</button>
</div>
```

- [ ] **Step 2: Add `toggleEditorTheme` JS function**

Find the section with other utility functions (near the top of the `<script>` block). Add this function:

```javascript
// ── Editor theme toggle ──────────────────────────────────────────────────────
const EDITOR_THEME_KEY = 'sparge.editor.theme';

function getEditorTheme() {
  return localStorage.getItem(EDITOR_THEME_KEY) || 'light';
}

function applyEditorTheme(theme) {
  document.body.setAttribute('data-editor-theme', theme);
  const btn = $('btn-editor-theme');
  if (btn) btn.textContent = theme === 'light' ? '☀ Light' : '☾ Dark';
  const cmTheme = theme === 'light' ? 'default' : 'material-darker';
  if (htmlEditor) htmlEditor.setOption('theme', cmTheme);
  if (mdEditor)   mdEditor.setOption('theme', cmTheme);
}

function toggleEditorTheme() {
  const next = getEditorTheme() === 'light' ? 'dark' : 'light';
  localStorage.setItem(EDITOR_THEME_KEY, next);
  applyEditorTheme(next);
}
```

- [ ] **Step 3: Apply saved theme on page load**

Find the DOMContentLoaded or init section near the top of the script. Add a call to restore preference on startup (it runs before any editor is created, so it only needs to set the `<body>` attribute and button label):

```javascript
// Restore editor theme preference (editors pick up theme on creation)
applyEditorTheme(getEditorTheme());
```

- [ ] **Step 4: Update `enterEditMode` to use saved theme**

In `enterEditMode`, when creating each editor, use `getEditorTheme()` to set the initial theme instead of hardcoding `'default'`:

```javascript
const cmTheme = getEditorTheme() === 'light' ? 'default' : 'material-darker';

htmlEditor = CodeMirror($('html-editor'), { mode:'htmlmixed', theme:cmTheme, lineNumbers:true, lineWrapping:false, value:raw });
```

```javascript
mdEditor = CodeMirror($('html-editor'), { mode:'markdown', theme:cmTheme, lineNumbers:true, lineWrapping:true, value:raw });
```

- [ ] **Step 5: Visual check**

Enter edit mode. The sidebar should show a `☀ Light` button at the bottom. Click it — the button should change to `☾ Dark`, the editor background should switch to the dark material theme. Reload the page, enter edit mode — dark preference persists. Click again to restore light. Reload — light persists.

- [ ] **Step 6: Commit**

```bash
git add ui/index.html
git commit -m "feat: editor theme toggle — light/dark, persisted in localStorage"
```

---

### Task 12: Final sweep — remaining dark values and visual QA

**Files:**
- Modify: `ui/index.html` — any remaining hardcoded dark values missed in earlier tasks

- [ ] **Step 1: Search for remaining dark hex values**

Run a grep to find any remaining old-palette hex values still in the `<style>` block:

```bash
grep -n "#0d1117\|#161b22\|#30363d\|#1f6feb\|#1c2d3f\|#21262d\|#484f58\|#c9d1d9\|#e6edf3\|#8b949e\|#58a6ff\|#3fb950\|#f85149\|#e3b341" ~/claude/sparge/ui/index.html | grep -v "^[0-9]*:.*//\|script\|STORE_KEY\|highlight\|material"
```

For each match, replace with the appropriate token from the spec. Common mappings for any remaining values:

| Old value | Replacement |
|---|---|
| `#21262d` | `var(--chrome)` (slightly darker chrome) |
| `#484f58` | `var(--muted)` |
| `#1c2128` | `var(--border-light)` as background tint |
| `#58a6ff` | `var(--accent)` |
| `#3fb950` | `var(--approve)` |
| `#f85149` | `var(--error)` |
| `#e3b341` | `var(--warn)` |
| `#0d2b0d` diff add bg | `var(--approve-bg)` |
| `#2d0d0d` diff del bg | `#f4e0e0` |

- [ ] **Step 2: Check the scope action buttons in filter zone**

Find `.scope-col-header` and update:

```css
.scope-col-header { font-size:8px; color:var(--muted); text-align:center;
                    text-transform:uppercase; letter-spacing:.05em; padding-bottom:2px;
                    font-family:'SFMono-Regular',Consolas,monospace; }
```

- [ ] **Step 3: Full visual walkthrough**

Walk through these scenarios and confirm each looks correct:

1. Load `http://localhost:9000/ui/` — post list visible, parchment background, no dark elements
2. Select a post — slate left border, accent-tint background, content panels show HTML + MD
3. Hover over issue row in breakdown — correct highlight
4. Open diff modal (edit + save a post) — parchment modal, warm shadow, correct diff colours
5. Open config panel (⚙ button) — parchment panel, ink left border
6. Enter HTML edit mode — edit sidebar shows, editor is warm cream, "☀ Light" toggle visible
7. Toggle to dark — editor goes dark, preference persists on reload
8. Enter MD edit mode — same behaviour
9. Exit edit mode — normal three-column view restores

- [ ] **Step 4: Run existing tests to confirm no regressions**

```bash
cd ~/claude/sparge && python3 -m pytest tests/ -q
```

Expected: all tests pass (CSS changes don't affect server behaviour)

- [ ] **Step 5: Commit**

```bash
git add ui/index.html
git commit -m "style: final sweep — remove remaining dark palette values, QA pass"
```

---

## Self-Review

**Spec coverage:**
- ✅ Full palette (all 13 tokens) — Tasks 1–9
- ✅ Typography (Georgia logo, SF Mono labels, body system-ui) — Tasks 2, 4, 6, 8, 9
- ✅ Post list selected state (accent border + tint) — Task 3
- ✅ Filters / tab pills — Task 4
- ✅ Buttons (2px radius, all variants) — Task 5
- ✅ Action bar — Task 5
- ✅ Panel headers (mono uppercase) — Task 6
- ✅ Badges — Task 7
- ✅ Issue panel, floating tooltip — Task 7
- ✅ Diff modal — Task 8
- ✅ Config panel — Task 8
- ✅ Edit sidebar — Task 9
- ✅ CodeMirror light theme (custom CSS + syntax colours) — Task 10
- ✅ CodeMirror dark toggle (localStorage, `setOption`) — Task 11
- ✅ highlight.js: spec says no change needed — confirmed, `github.min.css` is already light
- ✅ Final QA sweep — Task 12

**No placeholders:** All CSS blocks are complete. All JS functions are fully written.

**Type consistency:** `htmlEditor`, `mdEditor` global names consistent across Tasks 10, 11. `$('btn-editor-theme')` matches the `id="btn-editor-theme"` added in Task 11 Step 1. `applyEditorTheme()` is called from `toggleEditorTheme()` and page init — both defined in Task 11 Step 2.
