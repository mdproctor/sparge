# Sparge — Comprehensive Handoff Document

*Written April 2026. For a future Claude continuing this work with Mark Proctor.*

---

## Who is Mark Proctor

Mark is the lead architect of the KIE/Drools project (Red Hat/JBoss Java rule engines: Drools, jBPM, OptaPlanner, Kogito). He is technically very strong — comfortable reading and discussing code at any level of detail, opinionated about UX, and has a clear vision of what he wants even when he can't always articulate it in the first message. He often types quickly with typos — interpret charitably. He iterates through design by looking at working things and reacting ("this doesn't feel right", "why are these two separate?"), not by reading specs upfront.

**Communication style:**
- Short messages, often incomplete sentences — fill in the intent from context
- Says "yes" or "go ahead" to approve plans, then expects full implementation
- When he says something "doesn't work", check whether the server needs restarting before debugging
- He cares deeply about UX clarity: if something confuses him, the design is wrong, not the user
- He wants tests for everything. If he asks you to build something, write the tests too without being asked.

**His working environment:**
- macOS, Python 3.13, zsh
- Working directory: `/Users/mdproctor/claude/sparge/` (Sparge tool)
- Blog data directory: `/Users/mdproctor/mdproctor.github.io/` (GitHub Pages blog + KIE archive)
- Server runs on port 9000

---

## The Journey — How We Got Here

### Origin: A Simple Migration Request

This started as "convert my archived blog posts to Markdown for Jekyll". Mark had ~1,800 posts from blog.kie.org stored in `/Users/mdproctor/mdproctor.github.io/legacy/` and wanted to publish a selection (his 577 posts) to his GitHub Pages blog at mdproctor.github.io.

### Phase 1 — App 1: HTML Archive Reviewer

Built `legacy/review-issues.html` — a local web app for reviewing the raw HTML archive. Key work done:
- Extracted posts from blog.kie.org using wget mirror + BeautifulSoup
- Recovered missing images: 5-approach hierarchy (local data-src, Wayback CDX API with date-targeting, ederign.me mirror site, cross-platform sources, Amazon ISBNs for book covers)
- Playwright-based iframe recovery for YouTube/Vimeo embeds
- Tracking pixel removal, syntax highlighting injection (highlight.js with custom DRL language)
- Discovered: Wayback CDX API requires date-targeted queries (not just "latest snapshot") to avoid getting wrong-era images. ederign.me is a KIE blog mirror that needs title-based matching because post dates differ. This knowledge is captured in `docs/archive-cleaning.md` (to be written fully).

### Phase 2 — App 2: HTML→Markdown Reviewer

Built `mark-proctor/viewer.html` — a side-by-side HTML+MD review tool. Key work:
- `scripts/convert_post.py`: HTML→MD converter using html2text + BeautifulSoup
- Critical bug fixed: `@@CODEBLOCK_000@@` placeholder system (zero-padded, delimited) prevents partial string replacement bugs where `FENCE_1.replace()` matches `FENCE_10`
- `scripts/md_validator.py`: 31 validation checks (16 MD-only + 15 cross-validation against original HTML)
- Staged workflow: dry-run comparison on every navigation, side-by-side LCS diff modal
- Scroll sync: heading-anchored proportional sync between HTML and MD panels

### Phase 3 — Making It a Real Tool

The decision: instead of a one-off migration script, build a reusable tool that anyone could use for any blog. This led to "Blog Migrator" → renamed to **Sparge**.

**Name origin:** Sparging in brewing = rinsing grain (raw material) through hot water to extract pure wort, discarding spent husks. Perfect metaphor: raw web content (grain) goes in, noise is stripped (WordPress chrome, JS, tracking), clean Markdown (wort) comes out. Verified clear in all major software namespaces as of April 2026.

### Phase 4 — Multi-Project Architecture

Moved from single-project to multi-project:
- `projects/` directory with per-project `config.json` + `state.json`
- `projects.json` index
- Server hot-switches between projects without restart
- Projects page (`ui/projects.html`) as entry point
- Import modal with 3 modes: New Project, Append, Wipe+Reimport

### Phase 5 — The 3-Stage Pipeline

Major architectural shift: source/cleaned/assets directory split.
- **source/**: original HTML as fetched, original URLs, NEVER modified
- **cleaned/**: working copies, assets rewritten to `/assets/posts/{slug}/` or `/assets/global/`
- **assets/**: per-post folders + global/ for shared images
- **md/**: generated Markdown
- URL-based real-time dedup + hash-based consolidation pass
- This only applies to new-schema projects; legacy projects (including the current KIE one) use the old structure

---

## What Sparge Is Now

A local web application for ingesting any WordPress/Blogger/Ghost blog, cleaning the HTML, and transforming it to portable Markdown. Runs entirely on localhost. Config-driven, no cloud services.

**Entry point:** `python3 server.py` from `/Users/mdproctor/claude/sparge/`  
**UI:** `http://localhost:9000/` → Projects page  
**Tests:** `python3 -m pytest tests/` → 315 tests

---

## Current Architecture

### Directory Structure

```
sparge/
  server.py                  ← Unified HTTP server (stdlib only, port 9000)
  config.json                ← Root default config (legacy schema, seldom used)
  projects.json              ← Index of all projects
  projects/
    kie-mark-proctor/        ← The real KIE project (legacy schema)
      config.json            ← Points to /Users/mdproctor/mdproctor.github.io/legacy/
      state.json             ← Per-post state for 577 posts
    kie-fresh/               ← Test project (new schema, empty — awaiting first import)
      config.json            ← Points to /Users/mdproctor/claude/kie-fresh/
      state.json             ← {}
  scripts/
    config.py                ← Mutable cfg dict, hot-switchable between projects
    state.py                 ← Per-post state (5 dimensions + staged workflow)
    ingest.py                ← Platform detect, discover, extract, localise assets
    asset_store.py           ← Per-post folder + global/, URL index, dedup
    consolidate.py           ← Hash-based consolidation pass
    scan_html.py             ← 9 HTML issue detectors with CSS selectors
    scan_assets.py           ← Image localisation checker
    convert_post.py          ← HTML→Markdown (older code, hardcoded paths — see issues)
    md_validator.py          ← 31 MD validation checks
  ui/
    projects.html            ← Landing page: project list, create, import modal
    index.html               ← Per-project review: split HTML/MD, all actions
  tests/
    conftest.py              ← Shared fixtures, mock_blog_server session fixture
    fixtures/
      mock_blog.py           ← 20-article mock WordPress blog on random port
    test_md_validator.py     ← 80 tests (all 31 validator checks)
    test_scan_html.py        ← 57 tests (all 9 HTML issue detectors)
    test_ingest.py           ← 50 tests (detect, discover, preview, ingest, dates)
    test_ingest_integration.py ← 42 integration tests (full pipeline with mock blog)
    test_asset_store.py      ← 31 tests (URL dedup, global routing, collisions)
    test_consolidate.py      ← 13 tests (hash dedup, HTML rewriting, idempotency)
    test_server_api.py       ← 33 tests (HTTP API: projects CRUD, ingest, wipe)
    test_security.py         ← 23 tests (XSS, file://, sitemap injection, etc.)
  docs/
    FEATURES.md              ← Working notes for future end-user documentation
    HANDOFF.md               ← This file
```

### Two Config Schemas

**Legacy schema** (current KIE project, original structure):
```json
{
  "serve_root": "/Users/mdproctor/mdproctor.github.io",
  "source": { "posts_dir": "legacy/posts/mark-proctor", "assets_dir": "legacy/assets" },
  "output": { "md_dir": "mark-proctor" }
}
```
`_posts_dir` = `_cleaned_dir` (no separation). Source IS the cleaned version.

**New schema** (kie-fresh and future projects):
```json
{
  "serve_root": "/Users/mdproctor/claude/kie-fresh",
  "data": {
    "source_dir": "source", "cleaned_dir": "cleaned",
    "assets_dir": "assets", "md_dir": "md"
  }
}
```
`_source_dir` ≠ `_cleaned_dir`. Full 3-stage pipeline.

### Per-Post State (5 Dimensions)

Each post in state.json tracks independently:
1. **HTML** (`html.hash`, `html.issues[]`, `html.checked_at`) — scan results, CSS selectors for highlighting
2. **Assets** (`assets.total`, `assets.localised`, `assets.broken`, `assets.checked_at`)
3. **Markdown** (`md.generated_at`, `md.html_hash`, `md.staged`, `md.staged_at`) — stale = html_hash changed after generation
4. **MD validation** (`md.issues[]`, `md.validated_at`)
5. **Review** (`flagged`, `user_note`, `reviewed`)

**Staged workflow:** When Generate MD finds a diff (dry-run), user can Stage instead of immediately Replace. Writes `.md.staged` alongside `.md`. Later: Review Staged → Accept (promotes) or Reject (deletes staged).

---

## Server API Reference

```
GET  /                                  → redirect to /ui/projects.html
GET  /api/projects                      → list all projects with stats
POST /api/projects                      → create project
DELETE /api/projects/{id}               → remove from index (data kept)
GET  /api/projects/{id}/newest-date     → {date: YYYY-MM-DD|null, count: int}
POST /api/projects/{id}/activate        → switch active project
POST /api/projects/{id}/wipe           → delete data dirs, reset state (new schema only)
POST /api/consolidate                   → hash-based asset consolidation

GET  /api/posts                         → all posts in active project
GET  /api/posts/{slug}                  → single post state
PATCH /api/posts/{slug}                 → update flagged/user_note/reviewed
POST /api/posts/{slug}/scan             → scan HTML + assets
POST /api/posts/{slug}/generate-md      → generate MD (dry=1 for dry-run)
POST /api/posts/{slug}/validate-md      → run 31-check validator
POST /api/posts/{slug}/save-md          → write manually-edited MD
POST /api/posts/{slug}/stage            → write .md.staged
GET  /api/posts/{slug}/staged           → return staged content
POST /api/posts/{slug}/accept-staged    → promote staged → MD
POST /api/posts/{slug}/reject-staged    → delete staged

POST /api/ingest/detect                 → detect platform from URL
POST /api/ingest/discover               → discover all post URLs
POST /api/ingest/preview                → extract one post (no write)
POST /api/ingest/run                    → start background ingest job
GET  /api/ingest/status                 → {running, done, total, current, errors[]}
POST /api/ingest/cancel                 → stop ingest job

GET  /api/config                        → active project config
POST /api/config                        → update config
GET  /*                                 → static file from serve_root
```

---

## What Actually Works vs. What's Stubbed

### Fully Working
- ✅ Projects page: list, create (local paths), delete, Import modal (all 3 modes)
- ✅ Import Append mode: discovers all URLs, filters by date using `filter_urls_after()`
- ✅ Import Wipe mode: deletes data dirs, resets state, then re-imports
- ✅ Full ingest pipeline: detect platform → discover via sitemap/WP API/RSS → extract article → strip junk → localise assets → write source/ and cleaned/ + sidecars
- ✅ Asset organisation: per-post folders, global/ for shared (URL-based), consolidation (hash-based)
- ✅ HTML scanning: 9 checks with CSS selectors (for future highlighting)
- ✅ Issue highlighting: clicking an issue row injects CSS into iframe, highlights element, scrolls to it
- ✅ MD generation with dry-run freshness check and diff modal
- ✅ Staged workflow: Stage → Review → Accept/Reject
- ✅ Manual MD editing: Edit mode in MD panel, saves via /api/posts/{slug}/save-md
- ✅ MD validation: 31 checks, cross-validation against HTML
- ✅ Scroll sync (heading-anchored proportional) with ⊙ Source/Cleaned toggle
- ✅ Scroll position memory per post
- ✅ Keyboard navigation: Cmd+←/→ or J/K; Tab=layout toggle; 1/2=panel switch
- ✅ Bulk operations: Gen scope, Scan scope, Validate scope, Accept/Reject all staged
- ✅ Consolidate button: runs hash-based asset deduplication

### Partially Working / Caveat
- ⚠️ **⊙ Source button** — only shows for new-schema projects. The KIE legacy project will never show it. Correct behaviour but may confuse users who don't know about schemas.
- ⚠️ **convert_post.py** — reads from `POSTS_DIR` (which = `CLEANED_DIR` for new schema, original dir for legacy). Has hardcoded `ROOT = Path('/Users/mdproctor/mdproctor.github.io')` at the top. This means MD generation for new-schema projects that store data outside this path will fail. Needs updating.
- ⚠️ **kie-fresh project** — created and configured but never actually used to import. The import modal and 3-stage pipeline are built and tested against the mock blog, but haven't been validated against the real KIE blog yet.
- ⚠️ **Legacy KIE project** (577 posts) — still using old schema. Only ~12 posts have been reviewed in the new tool. The bulk of the migration work is still ahead.

### Not Yet Built
- ❌ **Post-ingest summary page** — after importing, show a breakdown (N posts, N images recovered, N failed, timeline chart). Mark mentioned wanting this.
- ❌ **Author-grouped navigation** — for multi-author projects, grouping the nav list by author.
- ❌ **Playwright/browser UI tests** — Phase B future work (click Open → see review, ← back to projects, etc.)
- ❌ **End-user documentation** — FEATURES.md has working notes but no polished docs.
- ❌ **GitHub repo** — git is initialised, initial commit done, but no remote added.
- ❌ **Full documentation of the 5-approach image recovery** — the most valuable knowledge from Phase 1, partially in FEATURES.md, should be in `docs/archive-cleaning.md`.

---

## Known Issues and Technical Debt

### Architectural
1. **convert_post.py has hardcoded paths** — `ROOT = Path('/Users/mdproctor/mdproctor.github.io')` makes MD generation non-portable. For new-schema projects pointing elsewhere, this will break. Fix: make ROOT a parameter or derive from cfg.

2. **Legacy-to-new-schema migration gap** — the 577 KIE posts exist in the old flat directory structure (`legacy/posts/mark-proctor/*.html`). To use the new 3-stage pipeline for them, you'd need to run a migration that:
   - Copies each HTML to `source/` preserving original URLs
   - Runs the localise step to create `cleaned/` versions
   - Reorganises assets into per-post folders
   This is non-trivial because the existing HTML files have already had their paths rewritten (they reference `/legacy/assets/...` not original URLs). The "original URL" information is lost for the ~12 posts that convert_post.py processed (it used to write back to the source HTML — we stopped that, but damage is done for those files).

3. **state.json at root level** — there's still a `state.json` at `/Users/mdproctor/claude/sparge/state.json` left from before the multi-project architecture. It's not used but is confusing. Can be deleted.

4. **Test isolation requires server restart** — if tests activate a temporary project and cleanup fails to re-activate kie-mark-proctor, subsequent tests see no active project. Fixed in `_cleanup()` but the server must be restarted between test runs if any previous run was interrupted. Always `kill $(lsof -ti :9000)` before running tests.

### Code Quality
5. **ingest.py year range** — `extract_date_from_url()` only accepts years 2000–2030. The KIE blog has posts from 2006 (fine) but if ever applied to older archives this needs extending.

6. **projects.json modified by tests** — `TestIngestPipelineViaApi` directly writes to `projects.json` to register temporary test projects. This is a bit of an antipattern — ideally the server API would handle it. Works in practice but makes tests order-sensitive.

7. **mock_blog_server fixture in conftest** — the session-scoped `mock_blog_server` fixture is defined in `conftest.py` and used by both `test_ingest_integration.py` and `test_server_api.py`. If tests that use the fixture run in parallel (they don't currently), the same port would be shared. Not a problem with pytest's default sequential execution.

---

## The 31 MD Validation Checks

### MD-Only (always run)
`orphaned_placeholder`, `stray_digit_after_fence`, `unbalanced_fences`, `empty_code_blocks`, `missing_front_matter`, `unclosed_front_matter`, `missing_fm_field`, `bad_date_format`, `empty_body`, `wordpress_junk`, `html_entities_in_body`, `relative_image_path`, `broken_links`, `excessive_blank_lines`, `prose_in_code`, `duplicate_paragraph`, `excessive_line_length`, `many_missing_images`, `unknown_fence_language`

### Cross-Validation (require original HTML)
`code_blocks_dropped`, `code_block_count_mismatch`, `code_content_missing`, `language_tag_missing`, `word_count_low`, `heading_missing`, `lists_dropped`, `links_dropped`, `table_dropped`, `truncated_at_end`, `images_dropped`, `youtube_links_dropped`, `technical_terms_missing`, `blockquotes_dropped`, `content_phrase_missing`, `chrome_leakage`

**Key threshold:** word count < 35% of HTML word count = WARN (content loss). Links dropped > 70% = WARN. html2text produces `](<https://...>)` angle-bracket format — the validator handles both.

---

## The 9 HTML Scan Checks

`data_placeholder` (ERROR) — unrecovered lazy-load image
`missing_local_image` (ERROR) — referenced local file doesn't exist
`empty_embed` (ERROR) — iframe with no src
`unreplaced_gist` (ERROR) — GitHub Gist script tag not inlined
`noscript_remnant` (WARN) — orphaned noscript after lazy-load recovery
`external_image` (WARN) — img still pointing at http:// (not localised)
`tracking_pixel` (WARN) — 1×1 image from known tracking domain
`wordpress_chrome` (WARN) — UI elements leaked into article
`missing_image_signal` (WARN) — text says "as shown below" but no image follows

All issues include CSS selectors for in-browser highlighting (clicking an issue row in the panel highlights the element with a red outline in the iframe).

---

## The Ingest Pipeline

### Platform Detection
Tries in order: `/wp-json/` endpoint → WordPress; domain contains `blogger.com`/`blogspot.com` → Blogger; meta generator tag → Ghost; otherwise → generic.

### URL Discovery (cascading)
1. `sitemap.xml` → parse `<loc>` tags
2. `sitemap_index.xml` → follow child sitemaps (prefers `post-sitemap.xml`)
3. WordPress REST API: `/wp-json/wp/v2/posts?per_page=100&page=N`
4. Blogger Atom feed
5. Generic RSS/Atom: `/feed/`, `/rss.xml`, `/atom.xml`

**Security filters applied to sitemap:** `file://`, `ftp://`, non-http schemes rejected. Path traversal (`../`) rejected. Only `http://` and `https://` URLs pass `_is_post_url()`.

### Article Extraction
- Finds `<article>` → fallback `<div class="entry-content">` → `<main>` → `<body>`
- Strips: nav, header, footer, `.sidebar`, `#comments`, `.author-box`, `.sharedaddy`, `[class*="addtoany"]`, `[class*="wpDiscuz"]`
- Extracts metadata from: JSON-LD `<script>`, Open Graph tags, `article:*` meta tags, `<time datetime>`, byline text
- **Security sanitisation** applied to all surviving tags: strips `on*` event handlers, `javascript:` hrefs, external CSS `url()` references, `<style>` tags inside article

### Asset Localisation (new schema)
Uses `AssetStore` — a URL→path index backed by `.url-index.json`:
- First-seen URL → `assets/posts/{slug}/{filename}`
- Same URL from 2nd post → returns existing path (no re-download)
- Filename collision within post → numeric suffix (`diagram-2.png`)
- After `_localise_with_store()`: `src="http://..."` → `src="/assets/posts/{slug}/img.jpg"`
- Sidecar `.json` written to BOTH `source/` and `cleaned/` (needed for `init_from_source()`)

### Consolidation (hash-based)
Run via `POST /api/consolidate` or the "⟳ Consolidate" button in the nav:
- Scans all `assets/posts/*/` for identical SHA-256 hashes across different posts
- Promotes to `assets/global/`, rewrites all `cleaned/*.html` references
- Idempotent: second run promotes nothing

---

## Append Mode and Date Extraction

`extract_date_from_url(url)` extracts YYYY-MM-DD from:
1. `/2024/03/15/slug/` → `2024-03-15`
2. `/2024-03-15-slug` → `2024-03-15`
3. `/2024/03/slug` (WordPress month-only) → `2024-03-01`

`filter_urls_after(urls, after_date)`:
- Keeps URLs with extracted date > after_date (strictly after, not equal)
- Keeps URLs with no extractable date (safe default — can't rule them out)

`GET /api/projects/{id}/newest-date` reads `state.json`, finds max `date` field across all posts. Used to populate the Append mode cutoff in the Import modal.

---

## Security Tests Summary

The `test_security.py` file has 23 tests that caught real bugs:
- **`onerror` attributes** — were NOT stripped before our fix; now stripped by `_strip_junk()`
- **`file://` URL** — ingest gracefully returns error, doesn't read local filesystem
- **Sitemap URL injection** — `file://`, `ftp://`, `javascript:`, `../` URLs filtered by `_is_post_url()`
- **Path traversal in sitemap** — `/../../../etc/passwd` style URLs rejected
- **External CSS `url()`** — stripped from article content
- **`<style>` tags** — stripped from article
- **http→https normalisation bug** — `_normalise_url()` was force-upgrading `http://` to `https://`, breaking local test servers. Fixed: `http://` preserved as-is, only bare domains get `https://`

---

## UI Key Details

### projects.html — Import Modal (3 modes)

Clicking `⬇ Import` on any project card opens a modal:
1. **New project** — redirects to New Project form. Existing project untouched.
2. **Append newer posts** — modal fetches `newest-date` from API and shows it. After discovery, client-side filters URLs using `filter_urls_after()`. Shows "N new posts (of M total)".
3. **⚠ Wipe and re-import** — red confirmation dialog, then `POST /api/projects/{id}/wipe`, then discovers and imports all posts.

The modal closes on backdrop click or Escape. **Important:** The modal HTML comes AFTER the `</script>` tag in the DOM. The event listener is therefore wrapped in `DOMContentLoaded` (not inline). If this ever gets refactored, keep this in mind — otherwise you get "Cannot read properties of null" at script load time and the entire page breaks silently.

### index.html — Post Action Bar

Everything in the post action bar is scoped to the currently selected post:
- `[post title · date · author]` — context identifier
- `🔍 Scan` — runs HTML scan + asset scan together (one operation)
- `↺ Generate MD` — dry-run first if MD exists; shows diff modal if different
- `📋 Review Staged` — only visible when `md.staged === true`
- `✓ Validate MD` — runs 31 checks, opens issue panel
- `○ Mark Reviewed` / `✓ Reviewed` — toggles `reviewed` in state
- `🚩 Flag` / `🚩 Flagged` — toggles `flagged`, prompts for note
- `⚡ Issues` — toggles bottom issue panel (shows HTML issues | MD issues)
- `⟺ Sync` — toggle scroll synchronisation
- `☰ Single` / `⇔ Split` — toggle layout
- `⊙ Source` / `⊙ Cleaned` — toggle HTML panel between source/ and cleaned/ (new-schema only)

### Keyboard Shortcuts
- `Cmd+→` or `J` — next post
- `Cmd+←` or `K` — previous post
- `Tab` — toggle split/single layout
- `1` — switch to Original HTML panel (single mode)
- `2` — switch to Markdown panel (single mode)
- `Escape` — close diff modal / close config panel
- Nav keys blocked while diff modal is open

### Scroll Sync Algorithm
1. After iframe loads (400ms delay for layout to settle), scan `h2/h3` headings from both panels
2. Match headings by normalised text (lowercase, first 6 words, punctuation stripped)
3. Build anchor table: `[{md: pixelOffset, html: pixelOffset}]` + origin (0,0) + end (mdMax, htmlMax)
4. On scroll: find which anchor segment the position falls in, interpolate linearly
5. Result: headings always align; prose between headings scrolls proportionally

---

## The Mock Blog for Testing

`tests/fixtures/mock_blog.py` — a self-contained WordPress-like blog:
- 20 articles, dates 2020-01-15 → 2023-11-20 (evenly distributed)
- 3 authors cycling: Alice Smith, Bob Jones, Carol White
- 3 topics: Technology, Engineering, Design
- Serves: HTML articles at `/{YYYY}/{MM}/{DD}/{slug}/`, sitemap at `/sitemap.xml`, images at `/assets/img{001-020}.jpg`
- Uses minimal valid JPEG bytes as images
- Session-scoped pytest fixture via `conftest.py` — shared across all test files
- Exposes `ARTICLES` list for test assertions

---

## Roadmap — What's Next

### Immediate (high value, relatively low effort)

1. **Actually run the kie-fresh import** — the full 3-stage pipeline has never been validated against the real KIE blog. Open `http://localhost:9000/`, click Import on kie-fresh, enter `https://blog.kie.org`, author filter `Mark Proctor`, discover, preview one post, run full import. This is the most important validation step.

2. **Fix convert_post.py portability** — remove the hardcoded `ROOT = Path('/Users/mdproctor/mdproctor.github.io')`. Instead, derive it from the current config's `_posts_dir` (or pass it as a parameter). This blocks MD generation for new-schema projects with different paths.

3. **Delete stale state.json at root** — `/Users/mdproctor/claude/sparge/state.json` is a leftover from before multi-project. It's not used but could be confusing. Just `rm state.json`.

4. **GitHub remote** — `git remote add origin https://github.com/mdproctor/sparge.git && git push -u origin main`. The local repo is ready, just needs a remote. Mark should create the GitHub repo first.

### Medium Priority

5. **Post-ingest summary** — after an import completes (or instead of immediately jumping to the review UI), show a summary page: total posts imported, images recovered, errors, date range, author breakdown. Mark mentioned wanting this. It should appear in the flow between "import complete" and "open project".

6. **Legacy KIE posts migration decision** — decide whether to migrate the 577 existing posts to the new 3-stage schema or continue with the old schema. Options:
   - Keep old schema (simpler, just continue reviewing in the new UI — it works)
   - Write a migration script that copies HTML to source/, rewrites paths to cleaned/, reorganises assets (complex because original URLs are lost)
   - Re-import from blog.kie.org (clean but slow; posts since 2006; may miss some)

7. **Author-grouped navigation** — for the full 1800-post KIE archive (all authors), the flat list is unwieldy. A filter that groups by author or shows a header per author would help.

8. **Post-ingest documentation** — `docs/archive-cleaning.md` should document all the techniques found during Phase 1 image recovery. This is the most valuable institutional knowledge and it's currently only in FEATURES.md notes.

### Longer Term

9. **Playwright UI tests** — browser-level tests for the complete flow: click Import → modal appears → enter URL → discover → preview → run → see posts. Currently only tested with pure Python (ingest.py functions) or HTTP (server API). The UI logic hasn't been browser-tested.

10. **End-user documentation** — turn FEATURES.md into actual docs that a new user could read. Key things to document: getting started, project creation, the 3-stage workflow, the staged workflow, keyboard shortcuts.

11. **Requirements file** — currently no `requirements.txt`. Dependencies: `requests`, `beautifulsoup4[lxml]`, `html2text`, `lxml`. Someone setting this up from scratch needs to know what to install.

12. **"Generate All" improvement** — currently "Gen scope" only generates posts without MD. It doesn't handle the case where existing MD is stale. Consider a "Regenerate stale" option that dry-runs stale posts, stages the ones with diffs, and skips the ones that are identical.

---

## Architecture Philosophy

These decisions were made deliberately — understand them before changing:

**No JS framework** — keeps the tool self-contained. No `npm install`, no build step, works immediately on any machine. The UI can be a single `.html` file served by the Python stdlib. If it becomes complex enough to need a framework, that's a signal to rethink the complexity, not add Vue/React.

**No server framework** — `http.server.BaseHTTPRequestHandler` is sufficient and has zero dependencies. The server is internal tooling, not a public API. `flask` would add value only when the routing logic becomes unmanageable.

**Mutable `cfg` dict** — when switching projects, `cfg.clear(); cfg.update(new_cfg)` mutates the same object so all `from scripts.config import cfg` bindings across the codebase stay valid. This is unusual Python but it's intentional and documented.

**LCS-based side-by-side diff** — the diff modal uses O(m×n) dynamic programming. For 500-line files, that's ~250k operations — well under 50ms in Python. The side-by-side format (not unified) was Mark's explicit preference after seeing the unified view.

**Heading-anchored scroll sync** — pixel-proportional sync drifts badly when post content is distributed unevenly (e.g. a post with a huge code block followed by short paragraphs). Anchoring to headings means structural landmarks always align; prose between them scrolls proportionally within each section. This is the best achievable without a full content-aware alignment algorithm.

**Staged workflow** — the key insight: when HTML is improved (new image recovered, embed fixed), the existing MD becomes "stale" but you don't want to automatically overwrite manually-reviewed MD. Staging lets you see the diff, decide whether it matters, and accept or reject deliberately. This is like git's staging area applied to content migration.

**Source is read-only** — the most important design principle of the new pipeline. Violating it (as `convert_post.py` used to do, writing back image placeholders to the source HTML) makes the archive unreliable as a reference. Any transformation — even "fixing" something — must happen in `cleaned/`, never in `source/`.

**No-JS rendering as self-containment test** — serving HTML without any JavaScript is by design. Without JS, lazy-loaded images show as broken, tracking pixels don't fire, and any content that depends on dynamic loading becomes visible as a gap. This surfaces real archival problems rather than hiding them.

---

## The KIE Blog Specifically — Things to Know

- Blog: `https://blog.kie.org` — still live as of April 2026
- ~1,800 total posts, ~577 by Mark Proctor
- Posts go back to 2006 (Drools 2.x era)
- Dates are in WordPress `article:published_time` meta tags and `<time datetime>` attributes
- Many posts have YouTube embeds (data-src lazy-loaded); Playwright was used to recover these
- Image CDN: many images from `blog.kie.org/wp-content/uploads/` — most recoverable from Wayback Machine
- The `ederign.me` mirror site has many KIE blog posts; title-based matching is needed (not date-based, because publish dates differ)
- Technical terms to preserve in MD: `Drools`, `jBPM`, `KIE`, `OptaPlanner`, `Kogito`, `Guvnor`, `Rete`
- Custom DRL (Drools Rule Language) highlighting registered in highlight.js — essential for post quality
- The `legacy/review-issues.html` (App 1) still exists in the GitHub Pages repo and works as a standalone tool for the raw HTML archive

---

## Start-of-Session Checklist

When starting a new session with Mark:

1. Check server is running: `lsof -i :9000 | grep LISTEN`
   - If not: `cd /Users/mdproctor/claude/sparge && python3 server.py &`
2. Verify tests pass: `python3 -m pytest tests/ -q` → should show 315 passed
3. Open UI if needed: `open http://localhost:9000/`
4. Read any error output from the server carefully — it often has useful diagnostic info
5. If Mark says something "doesn't work", try: restart server, hard-refresh browser, check browser console
6. Ask what he's been doing since last session — context matters

**Never do without asking:**
- Delete any directory under `legacy/` (real archive data)
- `git push --force`
- Modify `projects/kie-mark-proctor/state.json` directly (can lose review state)
- Run `generate all` on the KIE project without Mark's awareness (could trigger 577 conversions)

---

## Key File Locations

| What | Where |
|---|---|
| KIE HTML archive | `/Users/mdproctor/mdproctor.github.io/legacy/posts/mark-proctor/` |
| KIE generated MD | `/Users/mdproctor/mdproctor.github.io/mark-proctor/` |
| KIE assets | `/Users/mdproctor/mdproctor.github.io/legacy/assets/` |
| Sparge project | `/Users/mdproctor/claude/sparge/` |
| KIE fresh data | `/Users/mdproctor/claude/kie-fresh/` (empty until first import) |
| Old App 1 | `/Users/mdproctor/mdproctor.github.io/legacy/review-issues.html` |
| Old App 2 | `/Users/mdproctor/mdproctor.github.io/mark-proctor/viewer.html` |
| Old generator server | `/Users/mdproctor/mdproctor.github.io/scripts/md_generator_server.py` |

---

## Honest Assessment — Where We Are

### What's strong
The foundation is solid. The test coverage (315 tests) is real — most tests exercise actual functionality against the mock blog, not mocks. The architecture is clean and modular. The UI is thoughtful with good UX decisions (staging, diff view, scroll sync). The security work was thorough and caught real bugs.

### What's uncertain
The **new 3-stage pipeline has never been validated against real content**. The mock blog test suite is strong but 20 simple articles can't replicate the edge cases in 577 real blog posts from 2006–2024. The first real import into `kie-fresh` will almost certainly surface issues.

### What's fragile
The relationship between `convert_post.py` (MD generation) and the new directory structure. This was the original script with hardcoded paths, written before the multi-project architecture existed. It works for the KIE legacy project because that project's `POSTS_DIR` = `CLEANED_DIR` = `legacy/posts/mark-proctor/`. For a genuinely new-schema project with different paths, MD generation will fail.

### The big picture
Mark started this wanting to migrate his blog posts. We've built something much more general and architecturally interesting than that original goal required. The tool is now capable of being a genuine open-source project for blog archival. But Mark's 577 posts are still only ~12 reviewed/converted. At some point the right move is to use the tool for its actual purpose rather than keep building it.

The next 2-3 sessions should probably alternate between: (1) fixing the `convert_post.py` portability issue and validating the new pipeline with the real KIE blog, and (2) actually reviewing Mark's posts.
