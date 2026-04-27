# Screenshot Guide

## How to regenerate all screenshots

```bash
npm run docs:screenshots
```

The Electron app opens, navigates through each screen, captures screenshots, then closes. Takes approximately 30–60 seconds. All images saved to `docs/user-guide/images/`.

**Prerequisites:**
- Quarkus JAR must be built: `cd server && mvn package -DskipTests`
- Electron binary must be installed: `node node_modules/electron/install.js`

## Fixture project

The script creates a temporary project in your system's temp directory (e.g. `/tmp/sparge-docs-fixture/` on macOS) using HTML posts from `electron-tests/fixtures/docs-posts/`. The fixture contains 5 posts in various pipeline states.

## Prose style rules

- Present tense, active voice
- Screenshot before prose (show then explain)
- Named UI elements in **bold**
- Pipeline stages in `code style`
- Callout boxes: `> **Note:** ...`
- Every screenshot gets an italic caption
- Max 3 sentences per paragraph
- No jargon without definition on first use

## Image index

| File | Used in | Captures | Method | Notes |
|------|---------|----------|--------|-------|
| README-hero.png | README | Full app, post list | full window | |
| 01-first-launch.png | 01 | Projects screen, empty state | element: body | |
| 02-new-project-form.png | 02 | New project creation form | element: form | |
| 02-folder-picker.png | 02 | Native OS folder picker | **MANUAL** | Retake if UI changes |
| 02-config-panel.png | 02 | Config panel showing locked paths | element: #cfg-panel | |
| 03-ingest-panel.png | 03 | Projects screen / ingest entry | full window | |
| 04-post-list-mixed-states.png | 04 | Post list with state badges | element: .posts | |
| 05-split-pane-open.png | 05 | HTML + MD editors side by side | full window | |
| 05-action-buttons.png | 05 | Scan / Generate MD buttons | element: #post-action-bar | |
| 05-post-metadata.png | 05 | Flag, note, review, copy title | element: #nav-stats | |
| 06-html-editor.png | 06 | CodeMirror HTML editor | element: #html-panel | |
| 06-issue-highlight.png | 06 | Issue highlighted in editor | element: #html-panel | |
| 07-md-editor.png | 07 | Markdown editor with generated MD | element: #md-panel | |
| 07-validation-issues.png | 07 | MD validation issues | element: #md-panel | |
| 08-issues-panel.png | 08 | Issues panel, HTML issues listed | element: #issue-panel | |
| 08-issue-highlighted.png | 08 | Editor with issue highlighted | element: #html-panel | |
| 08-dismiss-flow.png | 08 | Dismiss button on hover | element: #issue-panel | |
| 08-issue-breakdown.png | 08 | Issue breakdown stats | element: #html-breakdown | |
| 09-search-active.png | 09 | Search with query, filtered list | full window | |
| 09-filter-buttons.png | 09 | Issue-type filter buttons active | full window | |
| 09-filtered-list.png | 09 | Post list after filtering | element: .posts | |
| 10-staged-state.png | 10 | MD pane showing staged state | element: #md-panel | |
| 10-accept-reject.png | 10 | Accept / Reject staged buttons | element: #btn-staged area | |
| features-drag-divider.png | features | Drag divider between panes | element: #divider | |
| features-theme-toggle.png | features | Dark/light theme toggle | element: toolbar | |
| features-search-scope.png | features | Search scope selector | element: search bar | |

## Manual screenshots

| File | Instructions |
|------|-------------|
| 02-folder-picker.png | Launch app → New Project → click 📁 next to any path field → screenshot the dialog |
