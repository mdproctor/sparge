# Sparge UI Redesign — Archive Room

**Date:** 2026-04-09  
**Status:** Approved for implementation  
**Scope:** Full visual redesign of `ui/index.html` — palette, typography, components. No layout, feature, or behaviour changes.

---

## Problem

The current Sparge UI is a GitHub-dark clone: `#0d1117` background, `#1f6feb` blue accent, Inter-adjacent system font, dense badge system. It carries no identity and is indistinguishable from a VS Code extension or GitHub admin panel. The research finding: AI defaults to "statistical average design" — the median of every Tailwind SaaS template. Breaking out requires a domain metaphor, an explicit palette constraint, and a typographic choice that carries personality.

---

## Design Direction: Archive Room (Refined)

Sparge is a preservation tool — it rescues old blog posts from rotting CDNs and transforms them into permanent Markdown. The aesthetic mirrors that function: aged parchment, ink black, library card catalog conventions. The metaphor is restrained, not theatrical — the parchment and serif logo carry the identity while all UI conventions remain contemporary and efficient.

### What this is NOT

- Not the tactile version (no ruled-paper lines, no corner notches, no double borders)
- Not a light-mode experiment — this IS the mode (no dark toggle for the shell)
- Not a layout change — 3-column structure unchanged
- Not a density change — compact rows preserved

---

## Palette

| Token | Value | Usage |
|---|---|---|
| `--bg` | `#f4f0e8` | Main background, content panels |
| `--chrome` | `#ede7d9` | Sidebar, topbar, action bars |
| `--border` | `#c8baa0` | All dividers, card borders, panel separators |
| `--ink` | `#2a2218` | Primary text, topbar border, primary buttons |
| `--sepia` | `#5a4a30` | Secondary text, unselected post titles |
| `--muted` | `#8a7a5a` | Labels, dates, placeholder text |
| `--accent` | `#4a6a8a` | Selected state, active tab/filter, links, MD heading colour |
| `--accent-tint` | `#ecf0f4` | Selected post row background |
| `--approve` | `#2a6a2a` | Approve button, MD-ok badge |
| `--approve-bg` | `#e8f4e8` | MD-ok badge background |
| `--warn` | `#c87020` | Unsaved changes indicator, warning badges |
| `--error` | `#8a2a2a` | Error badges, issue panel errors |

No grays. No blues outside `--accent`. The previous `#1f6feb`, `#0d1117`, `#161b22`, `#30363d` are completely removed.

---

## Typography

| Role | Font | Size | Weight | Colour |
|---|---|---|---|---|
| Logo "Sparge" | Georgia, serif, italic | 15–16px | 700 | `--ink` |
| Section labels | `SF Mono`, monospace | 8–9px | 400 | `--muted` |
| Labels style | `letter-spacing: .1em`, `text-transform: uppercase` | — | — | — |
| UI body | system-ui, -apple-system, sans-serif | 12–13px | 400 | `--sepia` |
| Post titles | system-ui | 11–12px | 600 (selected), 400 (rest) | `--ink` / `--sepia` |
| Dates | `SF Mono` | 8–9px | 400 | `--muted` |
| Code / MD panels | `SF Mono`, Consolas, monospace | 10–11px | 400 | `--ink` |
| Markdown headings (rendered) | — | — | — | `--accent` |

Georgia is available on all platforms (macOS, Windows, Linux). No web fonts required — no CDN dependency for the identity.

---

## Component Specs

### Topbar

- Background: `--chrome`
- Bottom border: `2px solid --ink` (heavier than current 1px — the dividing line between identity and content)
- Logo: `font-family: Georgia, serif; font-style: italic; font-weight: 700; color: --ink`
- Tab underline active: `2px solid --accent`, text `--accent`
- Tab inactive: text `--muted`

### Post List (sidebar)

- Background: `--chrome`
- Right border: `1px solid --border`
- Row padding: `5px 9px` (current density preserved)
- Row bottom border: `1px solid #ddd4c0` (lighter than `--border`)
- **Selected row:** `background: --accent-tint`, `border-left: 2px solid --accent`, `padding-left: 7px` (compensates for border width)
- **Unselected row:** `border-left: 2px solid transparent`
- Date: `font-family: SF Mono; font-size: 8px; color: --muted`
- Title: `font-size: 11px; color: --ink (selected) / --sepia (rest)`

### Filters / Tab pills

- Active: `background: --accent; color: --bg; border-radius: 2px`
- Inactive: `color: --muted; border: 1px solid --border; border-radius: 2px`

### Buttons

| Type | Background | Border | Text |
|---|---|---|---|
| Primary (Scan, Save) | `--ink` | none | `--bg` |
| Secondary (Edit, Discard) | transparent | `1px solid --border` | `--sepia` |
| Approve | `--approve` | none | `--bg` |
| Approve hover | `#1a4a1a` | none | `--bg` |
| Danger | `#8a2a2a` | none | `--bg` |

- Border radius: `2px` throughout (not 6px — rounder corners feel too modern for the archive aesthetic)
- Font size: `10–11px`

### Action Bar

- Background: `--chrome`
- Bottom border: `1px solid --border`
- Post title: `font-size: 11px; color: --ink; font-weight: 600`
- Date / URL: `font-size: 9px; font-family: SF Mono; color: --muted`

### Panel Headers

Replace current GitHub-style tab bars with mono uppercase labels:

```
HTML SOURCE          MARKDOWN
```

- `font-family: SF Mono; font-size: 8px; letter-spacing: .1em; text-transform: uppercase; color: --muted`
- Background: `--chrome`, `border-bottom: 1px solid --border`

### Badges / Status Indicators

| Badge | Background | Border | Text |
|---|---|---|---|
| MD ok | `--approve-bg` | `1px solid --approve` | `--approve` |
| Approved | `--accent-tint` | `1px solid --accent` | `--accent` |
| HTML warn | `#f4e8e0` | `1px solid #c87020` | `--warn` |
| Error | `#f4e0e0` | `1px solid #8a2a2a` | `--error` |
| None | `#f0ece4` | `1px solid --border` | `--muted` |

### Stats Panel (nav sidebar)

- Section heading: mono uppercase, `--muted`
- Values: `font-weight: 600`
  - Green values: `--approve`
  - Blue values: `--accent`
  - Amber values: `--warn`
  - Muted values: `--muted`
- Progress bar: gradient `--approve → --accent` (same as current, but on parchment background)

### Issue Panel

- Background: `--bg`
- Border top: `1px solid --border`
- Error rows: `color: --error`, `border-left: 3px solid --error`, `background: rgba(138, 42, 42, 0.04)`
- Warning rows: `color: --warn`, `border-left: 3px solid --warn`

### Diff Modal

- Background: `--chrome` (not dark)
- Border: `1px solid --border`
- Box shadow: `0 4px 24px rgba(42, 34, 24, 0.3)` (warm shadow, not black)
- Added lines: `background: #e8f4e8; color: --approve`
- Deleted lines: `background: #f4e8e8; color: --error`

### Config Panel

- Background: `--chrome`
- Border left: `2px solid --ink`
- Input fields: `background: --bg; border: 1px solid --border`
- Input focus: `border-color: --accent`

---

## Editor Mode (CodeMirror)

### Default: Light (warm cream)

- CodeMirror theme: custom, not an existing preset
- Editor background: `#f0e8d4` (slightly warmer/darker than main parchment — distinguishes edit area)
- Panel header: `#e8dcc4`, `border-bottom: 1px solid #c8a87a`
- Syntax colours (HTML mode):
  - Tags: `#8a4a20`
  - Attributes: `#5a3090`
  - Strings: `#2a6a2a`
  - Text content: `#2a1a08`
  - Comments: `#a08050`
- Syntax colours (Markdown mode):
  - Headings: `--accent` (`#4a6a8a`)
  - Body text: `--ink`
  - Code spans: `#8a4a20`
  - Links: `--accent`

### Toggle: Dark

- Toggle button in edit sidebar: `☀ / ☾` icon, switches `data-editor-theme` attribute on `#panels`
- Dark theme: keep `material-darker` (already loaded via CDN — no new dependency needed)
- Preference persisted in `localStorage` key `sparge.editor.theme`
- Default: `light`

---

## Edit Mode Sidebar

- Background: `--chrome`
- Border right: `1px solid --border`
- Mode label: mono uppercase, `--accent`
- Slug: mono, `--muted`
- Unsaved indicator: `--warn` with `●` dot
- Editor theme toggle: small button at bottom of sidebar

---

## Removed / Replaced

| Old | Replacement |
|---|---|
| `#0d1117` background | `--bg` `#f4f0e8` |
| `#161b22` chrome | `--chrome` `#ede7d9` |
| `#30363d` borders | `--border` `#c8baa0` |
| `#1f6feb` blue accent | `--accent` `#4a6a8a` |
| `#1c2d3f` selected bg | `--accent-tint` `#ecf0f4` |
| `border-radius: 6px` buttons | `border-radius: 2px` |
| GitHub-style tab bars | mono uppercase panel labels |
| `material-darker` CodeMirror | custom light theme (dark toggle retained) |
| `.gl` uppercase chrome labels | same pattern, new colours |

---

## What Stays Unchanged

- All HTML structure, IDs, class names
- All JavaScript behaviour
- All layout dimensions (sidebar width, panel split, topbar height)
- All server endpoints and state management
- Highlight.js syntax highlighting (colours will need updating to match light theme)
- All CodeMirror JavaScript modes (xml, htmlmixed, markdown)

---

## Implementation Notes

- All colour changes are CSS-only — find/replace token values in the `<style>` block
- The custom light CodeMirror theme should be injected as a `<style>` block after the CodeMirror CSS imports, scoped to `.cm-light .CodeMirror { ... }`
- Add `data-editor-theme="light"` to `<body>` or `#panels`; toggle dark by swapping to `"dark"` and switching CodeMirror instance theme
- No new CDN dependencies
- `highlight.js` theme: `github.min.css` is already a light theme and works correctly — no change needed here
