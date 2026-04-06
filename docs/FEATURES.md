# Blog Migrator — Feature Notes for End-User Documentation

Working notes capturing key functionality and behaviours as they are built.
Not polished prose yet — a reference for writing the real docs later.

---

## What the tool is

A local web application for migrating a WordPress/Blogger blog archive to
clean, self-contained HTML and then to Jekyll-compatible Markdown. Runs
entirely on localhost — no cloud services required. The tool remembers the
state of every post across sessions so you can work incrementally.

---

## Setup & Configuration

- Single `config.json` file — the only thing users need to edit for a new project
- Key fields: `serve_root` (absolute path to repo), `source.posts_dir`, `source.assets_dir`, `output.md_dir`, `filter.author`, `server.port`
- Paths in config are relative to `serve_root` except `serve_root` itself
- Config panel accessible via ⚙ Config button (top-right of top bar)
- Changes to config require a server restart to take effect (paths are loaded once at startup)
- Start the server: `python3 blog-migrator/server.py` from the repo root
- UI opens at `http://localhost:{port}/ui/`

---

## Layout

```
[ Top bar: navigation + global config ]
    [ Review tab ]  [ Overview tab ]               [ ⚙ Config ]

[ Left nav ]  |  [ Post action bar: title + per-post actions ]
              |  [ Panel headers ]
              |  [ HTML panel ] | [ MD panel ]
              |  [ Issue panel (toggleable) ]
```

### Top bar — global only
Navigation between Review and Overview modes, plus Config. Nothing here is
scoped to a specific post.

### Post action bar — current document only
Everything here acts on the currently selected post:
- Post title and date/author
- 🔍 Scan HTML — run all HTML issue checks on this post
- ↺ Generate MD — generate (or regenerate) Markdown
- 📋 Review Staged — appears only when a staged version exists; opens diff view
- ✓ Validate MD — run 31 validation checks comparing MD to original HTML
- 🚩 Flag — mark post for manual attention (prompts for a note)
- ⚡ Issues — toggle the bottom issue panel
- ⟺ Sync — toggle scroll synchronisation between HTML and MD panels
- ☰ Single — toggle between split view and single-panel view

---

## Per-post state

Each post is tracked independently across five dimensions:

### HTML
| State | Meaning |
|---|---|
| Unscanned | HTML downloaded but never checked for issues |
| Clean | Scanned, zero issues detected |
| Has issues | Scanned, N problems found |

### Assets
| State | Meaning |
|---|---|
| Unchecked | Not yet verified |
| Complete | All images/CSS/fonts localised; renders without JS |
| Incomplete | N images still external or unrecovered |

### Markdown
| State | Meaning |
|---|---|
| None | Not yet generated |
| Current | Generated and HTML hasn't changed since |
| Stale | HTML was modified after MD was generated |
| Staged | A new version exists (`.md.staged`) awaiting accept/reject |

### MD Validation
| State | Meaning |
|---|---|
| Unvalidated | MD exists but checks haven't run |
| Clean | All 31 checks passed |
| Warnings | N warnings (possible content loss, heading mismatch, etc.) |
| Errors | N errors (code blocks dropped, duplicate paragraphs, etc.) |

### Review
| State | Meaning |
|---|---|
| Unreviewed | Not manually approved |
| Flagged | Marked as problematic (with optional note) |
| Reviewed | Manually approved |

---

## Left navigation panel

- Lists all posts; each item shows HTML status badge + MD status badge
- Clicking a post loads it in the review panels
- Selection remembers scroll position — returning to a post restores where you left off
- Badge priority (MD): Staged > Stale > Issues > Reviewed > Generated > None

### Filters
| Filter | Shows |
|---|---|
| All | Every post |
| HTML ⚠ | Posts with HTML issues detected |
| MD ⚠ | Posts with MD validation issues |
| Stale | Posts where HTML changed after MD was generated (not staged) |
| 📋 Staged | Posts with a staged version awaiting review |
| No MD | Posts not yet converted |

**Important:** Both bulk operations (Gen scope, Scan scope) apply to the
current filter — not to all posts. If you're filtered to "No MD", Gen scope
only generates those posts.

### Bulk operations
- **⚙ Gen scope** — generates MD for posts in current filter that don't have MD yet (skips existing)
- **🔍 Scan scope** — runs HTML scan on every post in current filter
- Both show slug-by-slug progress and disable each other while running

---

## HTML Scanning

Checks run when you click "🔍 Scan HTML" or "🔍 Scan scope":

| Issue type | Level | What it means |
|---|---|---|
| `data_placeholder` | ERROR | `<img src="data:...">` — lazy-loaded image not recovered |
| `missing_local_image` | ERROR | Local image file referenced but missing from disk |
| `empty_embed` | ERROR | `<iframe>` with no src — embed not recovered |
| `unreplaced_gist` | ERROR | GitHub Gist `<script>` tag not replaced with inline code |
| `noscript_remnant` | WARN | Orphaned `<noscript>` tag with external image URL |
| `external_image` | WARN | `<img>` pointing at http URL (not yet localised) |
| `tracking_pixel` | WARN | 1×1 tracking image from known analytics domain |
| `wordpress_chrome` | WARN | WordPress UI elements (bylines, share widgets) in article |
| `missing_image_signal` | WARN | Text like "as shown below" with no image following |

Issues are shown in the bottom panel and will eventually support in-browser
highlighting (clicking an issue will scroll to and highlight the element).

**Key behaviour:** HTML is never modified by scanning — only read. Issues are
stored in `state.json` with CSS selectors for future highlighting.

---

## Markdown Generation

### Normal flow (no existing MD)
Click ↺ Generate MD → converter runs → MD written to disk → validation runs
automatically → issues stored → badges update.

### Regeneration flow (MD already exists)
1. Existing MD is fetched
2. A dry-run generates new content without writing
3. If identical: shows "✓ No change"
4. If different: **diff modal** appears with three options

### The diff modal
Side-by-side view, left = saved version, right = newly generated.
- Deleted lines: red, left side
- Added lines: green, right side
- Context lines: grey, identical on both sides
- Unchanged stretches collapsed with "⋯ N unchanged lines ⋯"
- Both columns scroll in sync (locked scroll)
- Keyboard: Escape closes without action; nav keys blocked while modal is open

**Three options:**
| Button | Action |
|---|---|
| Keep Existing | Discard new version, keep current MD unchanged |
| 📋 Stage for Review | Write new version as `.md.staged`, mark post as Staged. Current MD untouched. Close modal. |
| Replace with New | Write new version immediately, run validation, update badges |

---

## The Staged Workflow

Designed for **bulk HTML fix scenarios**: when you fix images or embeds
across many posts at once, many MDs go stale simultaneously. Staging lets you
collect all pending decisions in one place and review them at your own pace.

### Files
- `SLUG.md` — current production Markdown (served to Jekyll)
- `SLUG.md.staged` — pending new version (stored alongside, never served)

### Workflow
```
HTML improved across many posts
    ↓
Gen scope on stale posts → diff modal for each
    ↓
Choose "Stage for Review" for each one (fast)
    ↓
Filter to "📋 Staged" to see all pending reviews
    ↓
Click each post → "📋 Review Staged" button → diff opens in staged mode
    ↓
Accept (promotes staged → MD) or Reject (deletes staged file)
```

### Staged diff modal
Same side-by-side view, but different buttons:
- **✕ Reject Staged** — deletes `.md.staged`, clears staged flag, keeps current MD
- **✓ Accept Staged** — promotes `.md.staged` → `.md`, runs validation, updates state

### Notes to document
- Staged files are ignored by Jekyll (`.md.staged` extension not processed)
- Accepting a staged version re-runs validation on the new content
- Rejecting does not regenerate — it simply discards the staged version
- A post can be both Stale and Staged (staged takes visual priority)

---

## MD Validation (31 checks)

Run automatically after every Generate, or manually via ✓ Validate MD.
Cross-checks compare the MD against the original HTML file.

### MD-only checks (always run)
| Check | What it catches |
|---|---|
| `orphaned_placeholder` | `@@CODEBLOCK_000@@` left unreplaced in MD |
| `stray_digit_after_fence` | Digit immediately after closing fence (e.g. ` ```0`) |
| `unbalanced_fences` | Odd number of ` ``` ` markers — block never closed |
| `empty_code_blocks` | ` ``` ` immediately followed by ` ``` ` |
| `missing_front_matter` | No `---` block at start |
| `unclosed_front_matter` | Opening `---` with no closing `---` |
| `missing_fm_field` | Required field (title/date/author) absent |
| `bad_date_format` | Date not YYYY-MM-DD |
| `empty_body` | Body under 20 characters |
| `wordpress_junk` | Bylines, "View all posts", share markup in MD body |
| `html_entities_in_body` | `&amp;`, `&lt;` etc. not decoded (outside code blocks) |
| `relative_image_path` | `../../assets/` paths (should be `/legacy/assets/`) |
| `broken_links` | `[text]()` — empty href |
| `excessive_blank_lines` | 3+ consecutive blank lines |
| `prose_in_code` | Multiple English sentences inside a code block |
| `duplicate_paragraph` | Same paragraph appearing twice (double-processing bug) |
| `excessive_line_length` | Line > 8000 chars |
| `many_missing_images` | More than 10 missing-image placeholders |
| `unknown_fence_language` | Unrecognised language tag on a code fence |

### Cross-checks (require original HTML)
| Check | What it catches |
|---|---|
| `code_blocks_dropped` | HTML has `<pre>` blocks but MD has none |
| `code_block_count_mismatch` | Count differs by more than 1 |
| `code_content_missing` | Code start/end not found in MD |
| `language_tag_missing` | HTML `language-X` class not reflected in MD fence |
| `word_count_low` | MD words < 35% of HTML words |
| `heading_missing` | h2/h3 text from HTML not found in MD |
| `lists_dropped` | HTML has `<ul>`/`<ol>` but MD has no list items |
| `links_dropped` | External link count dropped > 70% |
| `table_dropped` | HTML `<table>` has no representation in MD |
| `truncated_at_end` | Last substantial HTML paragraph not in MD |
| `images_dropped` | HTML has content images but MD has none |
| `youtube_links_dropped` | HTML has YouTube embed figures but MD has none |
| `technical_terms_missing` | Key terms (Drools, KIE, jBPM etc.) in HTML but not MD |
| `blockquotes_dropped` | HTML `<blockquote>` but no `>` lines in MD |
| `content_phrase_missing` | Sample HTML paragraph phrases not found in MD |
| `chrome_leakage` | WordPress sidebar text ("Leave a Reply" etc.) in MD |

**Note on angle-bracket links:** html2text sometimes produces `](<https://...>)` format.
The validator handles both `](https://` and `](<https://` when counting links.

---

## Scroll synchronisation

When ⟺ Sync is active (highlighted), scrolling either panel scrolls the other.

### How it works (heading-anchored proportional scroll)
1. After the HTML iframe loads, h2/h3 headings are extracted from both panels
2. Headings are matched by normalised text (lowercase, first 6 words)
3. Matched pairs become anchor points: `{md: pixelOffset, html: pixelOffset}`
4. Fixed anchors: `(0, 0)` at top, `(mdMax, htmlMax)` at bottom
5. When one panel scrolls, the position is interpolated between the nearest anchors
6. Within each section between headings, scroll is proportional to section height

**Result:** headings always align; prose between headings scrolls proportionally.
This is the best achievable alignment without word-level content mapping.

**Clicking ⟺ Sync** immediately snaps the MD panel to match the current HTML
panel position (doesn't wait for next scroll event).

**Sync is suppressed** in single-panel mode (only one panel visible).

---

## Scroll position memory

Navigating to a new post automatically saves the scroll position of both panels
for the post you're leaving. Returning to that post restores both positions.

This works across:
- Keyboard navigation (Cmd+← / Cmd+→, J/K)
- Clicking posts in the nav

---

## Keyboard shortcuts

| Key | Action |
|---|---|
| `Cmd+→` or `J` | Next post in current filter scope |
| `Cmd+←` or `K` | Previous post in current filter scope |
| `Tab` | Toggle split ↔ single panel layout |
| `1` | Switch to Original HTML panel (single-panel mode) |
| `2` | Switch to Markdown panel (single-panel mode) |
| `Escape` | Close diff modal / close config panel |

**Notes:**
- Navigation keys are blocked while the diff modal is open (prevents nav drift
  between `pendingSlug` and `currentSlug`)
- Shortcuts are suppressed when an `<input>` or `<textarea>` has focus

---

## Overview tab

Table of all posts showing status across dimensions. Clicking a row switches
to Review mode and loads that post. Columns:

| Column | Values |
|---|---|
| Date | YYYY-MM-DD |
| Title | Truncated to 60 chars |
| HTML | Unscanned / N issues / Clean |
| Markdown | Not generated / 📋 Staged / Stale / N issues / Reviewed / Generated |

---

## State persistence

All state lives in `blog-migrator/state.json`. It is:
- Written atomically on every state change
- Never deleted or overwritten between sessions — fully persistent
- Bootstrapped on server startup from the source directory (new HTML files get
  entries; existing entries have their HTML hash refreshed)
- Safe to edit manually if needed (valid JSON object keyed by slug)

The state file is **not** committed to git (it's in the blog-migrator working
directory, not the repo root). Users should back it up if they want to preserve
review progress.

---

## Things to come back and document (future features)

- [ ] Asset localisation scanning — the Assets column exists in the overview and the state model supports it (`assets.total/localised/broken`) but there is currently no scan button or implementation that populates it. Needs a "Scan Assets" button and a server endpoint that checks each image src against the local assets directory and counts external/missing ones.
- [ ] Issue highlighting in iframe — issue rows in the bottom panel have CSS selectors stored but clicking them does not scroll to or highlight the element. Needs postMessage to the iframe to inject a highlight style.
- [ ] Manual text editing of MD directly in the viewer (planned)
- [ ] In-browser issue highlighting (red border injected into iframe via CSS selector)
- [ ] Asset localisation checking (scan for external images not yet downloaded)
- [ ] Ingestion from URL / RSS / sitemap (first-stage pipeline)
- [ ] Author-grouped navigation
- [ ] "Generate All" generating already-existing MD (bulk regeneration with staging)
- [ ] Bulk accept/reject staged (approve all staged at once)
- [ ] How to configure for a new blog project (step-by-step)
