# Sparge — User Guide Design Spec
**Date:** 2026-04-10
**Topic:** User guide documentation with Playwright-captured screenshots
**Status:** Approved, ready for implementation planning

---

## Overview

Create a beautiful, comprehensive user guide for Sparge targeting **technical bloggers** —
comfortable with computers, not necessarily developers. The guide lives in the repo at
`docs/user-guide/`, publishes to GitHub Pages without restructuring, and ships with a
Playwright script (`npm run docs:screenshots`) that regenerates all screenshots when the UI
changes. Prose is hand-crafted once; images are fully automated.

---

## Section 1: File Structure

```
docs/user-guide/
  README.md                      ← overview, what Sparge is, index of all pages
  features.md                    ← complete feature inventory (all capabilities)
  01-installation.md
  02-first-project.md            ← includes config panel (top-right button)
  03-ingesting-posts.md
  04-the-pipeline.md
  05-working-with-posts.md
  06-html-editor.md
  07-markdown-editor.md
  08-issues-panel.md
  09-filtering-and-search.md
  10-staging-and-publishing.md
  11-checks-and-validation.md    ← reference: all checks/autocorrects by pipeline stage
  images/
    README-hero.png
    01-first-launch.png
    02-new-project-form.png
    ...                          ← {page-number}-{subject}.png
  SCREENSHOT-GUIDE.md            ← regeneration key: how to run, what each image captures
```

---

## Section 2: Page Content Plan

### README.md — Overview & Index
What Sparge is, who it's for, one-sentence description of the pipeline, links to all pages.
One hero screenshot of the full app with a post open.

### features.md — Features & Capabilities
Complete feature inventory — every capability with a one-line description and a clipped
screenshot. Groups:
- **Pipeline:** ingest, enrich, scan, generate MD, validate, stage, publish
- **Editors:** CodeMirror HTML + MD editors, autosync scroll, drag divider, syntax highlighting
- **Navigation:** search bar (title/body/both), issue-type filter buttons, author filter, reviewed filter
- **Post management:** flag, note, review checkbox, copy title button (⎘) + floating tooltip
- **Project management:** create project, native folder picker, config panel, project delete
- **Appearance:** dark/light theme toggle (persisted in localStorage)

Acts as a quick reference — "does Sparge do X?" answered here.

### 01-installation.md — Installation
Download the `.dmg` / `.exe` / `.AppImage`. First launch. What you see on opening (empty
projects screen). No terminal required.

### 02-first-project.md — Creating Your First Project
Projects screen → New Project form → path fields + native 📁 folder picker →
created project card → **config panel** (top-right button: view project paths, why they're
locked after creation — set once at creation time, immutable thereafter).

### 03-ingesting-posts.md — Ingesting Posts
Local ingest (from disk, HTML files already present) vs remote (from live blog URL).
Platform detection, URL discovery, preview individual posts, running the ingest job,
progress bar, completion state.

### 04-the-pipeline.md — Understanding the Pipeline
Full pipeline diagram: `Ingest → Enrich → Scan → Generate MD → Validate → Stage → Publish`.
Explain what happens at each stage. Show per-post state indicators in the post list
(badges, icons, colours) and what they mean.

### 05-working-with-posts.md — Working With Posts
Post list view, clicking a post opens the split-pane view. Pipeline action buttons
(Scan, Generate MD). Post metadata: flagging, user notes, review checkbox.
Copy title button (⎘) with floating tooltip. Drag divider to resize panes.

### 06-html-editor.md — The HTML Editor
Left pane. CodeMirror editor with syntax highlighting. Editing the HTML source directly.
Save and revert. Issue highlights — how problem areas are highlighted in-editor when
issues are selected. Autosync scroll with the Markdown pane.

### 07-markdown-editor.md — The Markdown Editor
Right pane. Generated Markdown. Editing the MD. The staging workflow: stage edits,
view staged diff, accept or reject. Validation results shown inline. Autosync scroll.

### 08-issues-panel.md — The Issues Panel
HTML issues vs MD issues — two separate lists. Issue types (what each one means in plain
language). Severity levels. Dismiss an issue (suppress for this post), undismiss.
Issue highlighting in the editor when an issue is selected. Issue breakdown stats panel.

### 09-filtering-and-search.md — Filtering & Search
Search bar: search by title, body text, or both — server-side body search.
Issue-type scoping buttons (filter post list to posts with a specific issue type).
Author filter. Reviewed filter. Combining multiple filters simultaneously.

### 10-staging-and-publishing.md — Staging & Publishing
Stage button: saves a `.md.staged` alongside the current `.md`. Review the staged version.
Accept-staged: promotes staged → live MD, re-validates. Reject-staged: discards changes.
What "published" means: copying the final `.md` to the Jekyll publishing repo.

### 11-checks-and-validation.md — Checks, Validations & Autocorrects
Complete reference table of everything Sparge detects and fixes, grouped by pipeline stage.

**At Ingest (autocorrects — applied silently):**
- `<br/>` → `\n` normalisation inside `<pre>` blocks
- Code block fixes: one-liner DRL/XML reformatting, span-tokenised code → `<pre><code>`,
  `<p><br/>DRL</p>` → `<pre><code>`, line-number table → `<pre><code>`
- imgur geo-blocked domains → Wayback Machine fallback
- `<a href>` image links localised to disk
- Wayback fallback for all failed image downloads

**At Scan — HTML checks (flagged as issues, not auto-fixed):**
| Check | What it detects |
|-------|----------------|
| `data_uri` | Inline base64 images (bloat, won't render in Jekyll) |
| `tracking_pixel` | 1×1 images from known tracking domains |
| `broken_local_ref` | `<img src="../../assets/...">` that don't resolve |
| `external_image` | Images still pointing to remote URLs |
| `empty_embed` | YouTube/embed containers with no content |
| `unreplaced_gist` | `<script src="gist.github.com/...">` not inlined |
| `wordpress_chrome` | WordPress metadata, admin bars, share buttons |
| `missing_image_signal` | Text like "as shown below" with no following image |
| `code_no_newlines` | Code blocks with `<br/>` instead of newlines (Case A/B) |
| `potential_code_block` | `<p>` blocks that look like unformatted code |
| `linenumber_table_code` | Two-column line-number + code tables |
| `imgur_image` | Images hosted on geo-blocked imgur domains |

**At Enrich (autocorrects — applied on first enrichment):**
- YouTube embed `<iframe>` → local thumbnail + link
- Gist `<script>` tags → fetched and inlined as `<pre><code>`
- Code class names normalised (e.g. `brush: java` → `language-java`)
- Same code block fixes as ingest (idempotent)

**At Generate MD — Markdown validation (flagged as issues):**
| Check | What it detects |
|-------|----------------|
| Missing images | Images present in HTML but absent from MD |
| Fence breaks | Unclosed or malformed code fences |
| Garbling | UTF-8 double-encoding artifacts (`ÃÂÃÂ` patterns) |
| Code block integrity | Fences with no language tag or truncated content |
| Cross-validation | MD content cross-checked against HTML source |

---

## Section 3: Screenshot System

**Script:** `electron-tests/docs-screenshots.js` — new Playwright script alongside existing
E2E tests. Run via `npm run docs:screenshots`. Launches Electron, navigates each UI state,
captures clips, saves to `docs/user-guide/images/`.

**Capture strategy:**
- **Element-level clips** — `locator.screenshot()` for panels, buttons, forms. Playwright
  clips to element bounds automatically. Preferred method.
- **Region clips** — `page.screenshot({ clip: {x, y, width, height} })` for multi-element
  areas. Coordinates recorded in `SCREENSHOT-GUIDE.md`.
- **Device scale factor 2x** — all captures at retina resolution (`deviceScaleFactor: 2`),
  displayed at half-width in Markdown. Crisp on retina screens.

**Fixture project:** Script seeds a small fixture project (5–10 posts in mixed pipeline
states: 2 with HTML issues, 1 with MD issues, 1 fully clean, 1 staged) automatically on
launch. Screenshots always show realistic content, never empty states.

**Native OS dialogs** (folder picker): Cannot be captured by Playwright. These screenshots
are taken manually once and committed. Noted in `SCREENSHOT-GUIDE.md` as
`manual — retake if UI changes`.

**Image format:** PNG, display width `700` in Markdown. Retina source is 1400px wide.

**Naming convention:** `{page-number}-{subject}.png`
Examples: `05-post-list.png`, `05-split-pane-open.png`, `08-issues-panel-html.png`.
Multiple screenshots per page get descriptive suffixes.

---

## Section 4: SCREENSHOT-GUIDE.md

Lives at `docs/user-guide/SCREENSHOT-GUIDE.md`. Records:
- How to run: `npm run docs:screenshots`
- Fixture project description
- For each image: file name, which page uses it, what it captures, capture method
  (element selector or clip coordinates), any manual steps
- Manual screenshots flagged explicitly

Format:
```markdown
| File | Page | Captures | Method |
|------|------|----------|--------|
| README-hero.png | README | Full app, post open | region (0,0,1200,800) |
| 02-folder-picker.png | 02 | Native folder picker | manual |
| ...  | ...  | ...      | ...    |
```

---

## Section 5: Prose Style

**Audience:** Technical bloggers — explain Sparge concepts clearly, no terminal hand-holding,
no need to explain what a blog post is.

**Rules:**
- **Present tense, active voice** — "Click **Scan** to analyse the post"
- **Show before explain** — screenshot first, prose after
- **No jargon without definition** — "enrichment" and "staging" explained on first use
- **Short paragraphs** — max 3 sentences
- **Named UI elements in bold** — "the **Issues Panel**", "the **Scan** button"
- **Pipeline stages in code style** — `` `Ingest → Enrich → Scan → Generate MD` ``
- **Callout boxes** for tips and warnings:
  ```markdown
  > **Note:** Paths are locked after project creation.
  ```
- **Every screenshot gets a caption** — italic, one sentence, directly below the image:
  ```markdown
  ![Post list with mixed pipeline states](images/05-post-list.png)
  *The post list shows pipeline state at a glance — badges indicate which stage each post has reached.*
  ```

These rules are reproduced in `SCREENSHOT-GUIDE.md` so future additions match the existing tone.
