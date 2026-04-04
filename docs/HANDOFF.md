# Sparge — Comprehensive Handoff Document

---

## Document History

Handoff documents are date-stamped so future summaries can be compared against previous ones to show progress, catch regressions, and improve the quality of each successive handoff.

| Version | Date | Author | Description |
|---|---|---|---|
| 1.0 | 2026-04-04 | Claude Sonnet 4.6 (1M) | Initial comprehensive handoff — full journey, architecture, test plan, roadmap |

*When adding a new entry: copy this file, increment version, update date and description, add a brief "what changed since last handoff" section near the top.*

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

---

## Detailed Test Plan — Avoiding Regressions

This section maps every significant behaviour to a test (automated or manual), explains what regression it guards against, and specifies exactly how to run or verify it. Future Claude should use this as a checklist before claiming anything is working.

---

### Running the Full Automated Suite

```bash
cd /Users/mdproctor/claude/sparge

# Kill any stale server first — stale active-project state causes false failures
kill $(lsof -ti :9000) 2>/dev/null

# Start a clean server
python3 server.py &
sleep 3  # wait for startup + init_from_source on 577 posts

# Run everything
python3 -m pytest tests/ -q
# Expected: 315 passed in ~35s

# For verbose output on a specific file:
python3 -m pytest tests/test_ingest_integration.py -v
```

**Important:** Always restart the server between test runs. If a previous run activated a temporary project and cleanup failed (e.g. test was interrupted), `_active_project_id` in server memory points at a deleted project, causing `test_active_field_present` to fail with "no active project". A fresh `python3 server.py` resets everything from `projects.json`.

---

### Test File Map

| File | Tests | What it covers | Regression risk if broken |
|---|---|---|---|
| `test_md_validator.py` | 80 | All 31 validation checks | MD quality gates silently disabled |
| `test_scan_html.py` | 57 | All 9 HTML issue detectors | Users can't see/fix HTML problems |
| `test_ingest.py` | 50 | detect, discover, preview, ingest, date extraction, URL filtering | Import pipeline broken |
| `test_ingest_integration.py` | 42 | Full pipeline end-to-end with mock blog | 3-stage architecture broken silently |
| `test_asset_store.py` | 31 | URL dedup, per-post folders, global routing, collisions | Assets duplicated or lost |
| `test_consolidate.py` | 13 | Hash dedup, HTML reference rewriting, idempotency | Consolidation corrupts paths |
| `test_server_api.py` | 33 | All HTTP endpoints, project CRUD, wipe, pipeline via API | Server API broken |
| `test_security.py` | 23 | XSS, file://, scheme injection, sitemap injection | Security regressions |

---

### Per-Feature Regression Tests

#### 1. MD Validation (31 checks)

**File:** `tests/test_md_validator.py`

**How to run:**
```bash
python3 -m pytest tests/test_md_validator.py -v
# Expected: 80 passed
```

**Key regression risks:**
- `test_catches_duplicate` — uses full content hash, not prefix. If changed back to prefix matching, Spring XML configs sharing long preambles produce false positives.
- `test_clean_angle_bracket_links` — html2text produces `](<https://...>)` format. If the `links_dropped` regex is changed, this format gets miscounted and hundreds of posts incorrectly flag as having dropped links.
- `test_entities_in_code_ok` — HTML entities inside code blocks should NOT trigger. If the code-stripping regex changes, this breaks.
- `test_clean_post_has_no_errors` — the clean-post integration test. If any check becomes too aggressive, this fails and signals a false-positive regression.

**Manual verification:** Generate MD for any KIE post, then Validate MD. Issue panel should show only real problems.

---

#### 2. HTML Scanning (9 checks)

**File:** `tests/test_scan_html.py`

**How to run:**
```bash
python3 -m pytest tests/test_scan_html.py -v
# Expected: 57 passed
```

**Key regression risks:**
- `test_catches_data_src` — data: placeholders are ERROR level. If check is silenced, lazy-load failures become invisible.
- `test_clean_when_placeholder_follows` — `missing-image` class divs must NOT trigger the signal detector. If `_strip_junk` changes, placeholders might get scanned as content.
- `test_selector_for_img` / `test_selector_uses_id_when_available` — CSS selectors are needed for the issue-highlighting feature. If `_selector()` returns None for common cases, clicking issue rows does nothing.
- `TestScanPostIntegration::test_handles_unreadable_file` — if the scanner raises instead of returning an error dict, the server returns 500 on any scan.

**Manual verification:** Click `🔍 Scan` on a post with known issues (try any 2006 post). Issue panel should show the detected problems. Click an issue row — the element should highlight with a red border in the HTML iframe.

---

#### 3. Ingest Pipeline

**Files:** `tests/test_ingest.py`, `tests/test_ingest_integration.py`

**How to run:**
```bash
python3 -m pytest tests/test_ingest.py tests/test_ingest_integration.py -v
# Expected: 92 passed (~5s for unit, ~4s for integration)
```

**Key regression risks:**

*Date extraction (`test_ingest.py::TestDateExtraction`):*
- 11 parametrized cases. If `extract_date_from_url()` regex changes, append mode silently stops filtering (passes everything or nothing).
- Year range is 2000–2030. KIE blog starts 2006 — safely in range. Don't narrow the range.

*URL filtering (`test_ingest.py::TestFilterUrlsAfter`):*
- `test_cutoff_is_exclusive` — the cutoff is strictly AFTER, not including the cutoff date. If changed to `>=`, append mode re-downloads the last already-ingested post every time.
- `test_undated_urls_always_included` — URLs with no date MUST pass through. If changed to exclude, any post with an unusual URL format gets silently skipped.

*Integration pipeline (`test_ingest_integration.py`):*
- `TestSourceIntegrity::test_source_html_has_original_image_urls` — source files must have bare `/assets/` paths ABSENT (only full http:// URLs allowed). If `ingest_post()` ever rewrites source/, this breaks.
- `TestAppendMode::test_append_after_wipe_starts_fresh` — after a wipe, using cutoff `2000-01-01` should return all dated URLs. If `filter_urls_after()` has an off-by-one on the exclusive comparison, this fails.
- `TestConsolidationAfterIngest::test_consolidation_is_idempotent` — running consolidation twice should promote 0 on the second run. If `promote_to_global()` doesn't update the index, files get moved twice and are lost.
- `TestWipeAndReimport::test_reimport_after_wipe_no_stale_assets` — after wipe and reimport, every URL in the index should have a file on disk. If the sidecar isn't written to cleaned/ (the bug we fixed), date fields are None and newest-date returns null.

**The sidecar bug:** `ingest_post()` must write `{slug}.json` to BOTH `source_dir/` AND `cleaned_dir/`. If only written to `source_dir/`, `init_from_source()` reads from `cleaned_dir/` and finds no sidecar → date = None → append mode doesn't work. This was a real bug found by tests.

---

#### 4. Asset Organisation

**File:** `tests/test_asset_store.py`, `tests/test_consolidate.py`

**How to run:**
```bash
python3 -m pytest tests/test_asset_store.py tests/test_consolidate.py -v
# Expected: 44 passed
```

**Key regression risks:**

*Asset store:*
- `test_second_post_routes_to_global` — same URL from different posts returns the EXISTING path (no new download). If URL lookup breaks, the same image gets downloaded into every post's folder.
- `test_collision_across_posts_no_suffix` — same filename in DIFFERENT posts is NOT a collision. If the collision check doesn't scope to the same folder, `diagram.png` in post-a would get named `diagram-2.png` in post-b even though they're separate.
- `test_index_persists_across_instances` — the `.url-index.json` must survive an `AssetStore` object being re-created. If the file isn't written on `record()`, every server restart re-downloads all assets.

*Consolidation:*
- `test_different_content_same_filename_not_consolidated` — two posts with an image called `img.png` but DIFFERENT content must NOT be consolidated. Only identical content (same SHA-256) gets promoted. If hash comparison is skipped, unrelated images get merged.
- `test_idempotent_second_run_promotes_nothing` — after consolidation, running again should show `promoted: 0`. If the index isn't updated when promoting, the second run finds the same files again and tries to promote them again (they're already in global/).
- `test_html_reference_updated_to_global` — after promotion, ALL cleaned HTML files must have updated references. If the regex substitution misses a file, that post's images silently become broken after consolidation.

---

#### 5. Server API

**File:** `tests/test_server_api.py`

**How to run:**
```bash
# Server must be running first
python3 -m pytest tests/test_server_api.py -v
# Expected: 33 passed
```

**Note:** 3 tests use the mock_blog_server fixture and do real network calls to discover/preview/ingest. These take ~3s extra. The remaining 30 tests are fast HTTP calls to the running server.

**Key regression risks:**

*Projects list:*
- `test_active_field_present` — EXACTLY ONE project should have `active: true`. If `_api_projects_list()` stops computing this (e.g., `_active_project_id` becomes None due to a startup error), no project shows as active and the UI can't open any project.

*Wipe endpoint:*
- `test_wipe_rejects_legacy_schema_projects` — wipe MUST return 400 for legacy-schema projects. If this guard is removed, running wipe on the KIE project would delete `legacy/posts/mark-proctor/` — catastrophic data loss.
- `test_wipe_nonexistent_project_returns_404` — if wipe silently succeeds for missing projects, users can wipe things that don't exist with no error feedback.

*Newest-date endpoint:*
- `test_returns_null_date_for_empty_project` — a freshly-wiped or new project must return `{date: null, count: 0}`. If it returns a non-null date, append mode thinks there's already content and skips posts that should be imported.

*Pipeline tests:*
- `test_wipe_and_reimport_same_count` — count after wipe+reimport must match count after first import. If the sidecar location bug recurs, state doesn't get populated and count stays 0.
- `test_ingest_status_tracks_progress` — `done == 5` after ingesting 5 posts. If the worker doesn't decrement on error (it increments `done` even on failure), this test passes but errors are silently hidden.

**Test isolation note:** `TestIngestPipelineViaApi._cleanup()` MUST re-activate `kie-mark-proctor` before deleting the test project. If this line is removed, the next test that calls `GET /api/projects` will see no active project and many tests will fail. This was a real bug found when the cleanup didn't restore state.

---

#### 6. Security

**File:** `tests/test_security.py`

**How to run:**
```bash
python3 -m pytest tests/test_security.py -v
# Expected: 23 passed (~30s — includes real network timeouts)
```

**Why these tests are slow:** `test_internal_ip_ingest_is_bounded` tries to connect to `10.255.255.1` which times out (good — it means we're waiting for the timeout). `test_huge_response_does_not_hang` sends 5MB of data. These are intentionally slow to verify the security properties hold under load.

**Key regression risks:**

- `test_onerror_attribute_stripped` — `onerror="alert(1)"` on an `<img>` must be gone after extraction. This was a REAL BUG: before we added `_strip_junk()` attribute sanitisation, ALL event handlers survived into cleaned HTML. If the sanitisation loop is removed from `_strip_junk()`, this test fails and real XSS becomes possible.

- `test_file_url_returns_error` — `preview_post('file:///etc/passwd', session)` must return an error dict, not the contents of the file. If `_normalise_url()` is changed to convert `file://` to `https://` (wrong) or to not filter it, this test fails and local file reads become possible through the API.

- `test_file_urls_in_sitemap_filtered` — a sitemap containing `<loc>file:///etc/passwd</loc>` must not include that URL in `discover_urls()` results. Verified by `_is_post_url()` scheme check. If the scheme check is removed, the ingest worker would try to `session.get('file:///etc/passwd')` which on some systems reads local files.

- `test_path_traversal_in_sitemap_not_fetched` — `http://localhost/../../etc/passwd` in a sitemap must be rejected. Verified by `'..' in path` check in `_is_post_url()`. If removed, the worker fetches the traversal URL.

- `test_bad_urls_return_error_not_exception` — every bad URL must return a dict with `error` field, never raise. If any of the 5 parametrized cases raises, the server worker's try/except catches it but the test fails because the public API contract is broken.

- `test_huge_response_does_not_hang` — 15-second SIGALRM timeout. If `preview_post()` hangs on a 5MB response (e.g., if timeout parameter was removed from session.get), this test fails with TimeoutError.

**The http→https normalisation bug (already fixed but watch for regression):** `_normalise_url()` used to force-convert `http://` to `https://`. This caused `discover_urls()` to try `https://localhost:{port}` for the mock blog server, which isn't TLS-enabled, silently getting 0 results. The fix: `http://` is preserved as-is (caller chose it explicitly); only bare domains without a scheme get `https://`. The security tests now test local URLs correctly.

---

### Manual Tests — Things That Can't Be Automated

These require a browser and human judgment. Future Claude should run these when making UI changes or after any significant refactoring.

#### MT-1: Projects Page — Import Modal Flow

**When to run:** After any change to `ui/projects.html` or `server.py` project endpoints.

**Steps:**
1. Open `http://localhost:9000/`
2. Verify both projects appear (KIE Blog — Mark Proctor with 577 posts, KIE Blog — Fresh Import with 0 posts)
3. Click `⬇ Import` on KIE Blog — Mark Proctor. **Expected:** Modal opens, "Append newer posts" shows a date (e.g., 2016-08-05), "Wipe" is red. Escape closes without action.
4. Click `⬇ Import` on KIE Blog — Fresh Import. **Expected:** Modal opens, "Append newer posts" is dimmed (no posts yet), "New project" is selected by default.
5. Choose "New project" → Continue. **Expected:** New Project form scrolls into view, not the kie-fresh ingest panel.
6. Click `⬇ Import` on Fresh Import again → Choose "Append" → Continue. **Expected:** Inline ingest panel opens with URL input.
7. Enter `https://blog.kie.org` → click Discover. **Expected:** "Found N posts, WordPress" message appears, Run button appears.
8. **Do NOT actually run** unless you intend to import — it's slow and writes to disk.

**Regression check:** If the projects page shows empty, check browser console for JS errors. The most common cause: `document.getElementById('import-modal')` returns null because the modal HTML is after the `</script>` tag — the `DOMContentLoaded` listener prevents this now, but if the listener is removed, the whole page breaks silently.

#### MT-2: Review UI — Full Workflow on a Single Post

**When to run:** After any change to `ui/index.html`, `server.py` post endpoints, or `scripts/convert_post.py`.

**Steps:**
1. Open `http://localhost:9000/`, click Open on KIE — Mark Proctor.
2. Select the first post (2006-05-31-what-is-a-rule-engine).
3. Verify: HTML panel shows the post, MD panel shows rendered markdown. Both panels should be side-by-side.
4. Click `🔍 Scan` → wait. **Expected:** ✓ Scanned feedback. Issue panel opens automatically. Check HTML Issues and MD Issues columns are populated (or show "No issues recorded").
5. Click `✓ Validate MD` → wait. **Expected:** Issue panel updates with any validation findings.
6. Click `↺ Generate MD` (since MD already exists). **Expected:** Either "✓ No change" (if MD is up-to-date) or diff modal appears.
7. If diff modal appears: verify side-by-side columns, synced scrolling between columns, Escape closes it, "Keep Existing" closes without saving.
8. Click `⟺ Sync` (should be highlighted). Scroll the HTML iframe. **Expected:** MD panel scrolls in sync. Click Sync again to disable, scroll — panels independent.
9. Click `○ Mark Reviewed`. **Expected:** button changes to `✓ Reviewed` (highlighted). Click again → back to unreviewed.
10. Use `Cmd+→` to advance to next post, `Cmd+←` to go back. **Expected:** both panels update, scroll position is remembered when returning.

#### MT-3: Issue Highlighting in Iframe

**When to run:** After any change to the issue panel or highlight injection code in `ui/index.html`.

**Steps:**
1. Find a post with HTML issues (after scanning). Filter nav to "HTML ⚠".
2. Open the issue panel (⚡ Issues button).
3. Click an issue row that has a CSS selector (not dimmed). **Expected:** Red outline appears around the element in the HTML iframe, page scrolls to it.
4. Click the same row again. **Expected:** Outline disappears.
5. Click a different issue row. **Expected:** Previous outline gone, new element highlighted.
6. Navigate to a different post. **Expected:** Highlight cleared.
7. Close the issue panel. **Expected:** Highlight cleared.

**What to check if broken:** The `__sparge-highlight-style__` element is injected into the iframe's `<head>`. Open browser devtools on the iframe's document and look for a `<style id="__sparge-highlight-style__">` element. If it's there but the highlight isn't visible, the CSS selector is wrong or the element doesn't exist in the iframe at that path.

#### MT-4: Diff Modal and Staged Workflow

**When to run:** After any change to the diff modal, staged workflow, or `_api_generate_md`.

**Steps:**
1. Select any post that has MD generated.
2. Manually edit the MD (✎ Edit button → add a word → Save).
3. Click `↺ Generate MD`. **Expected:** Diff modal appears showing the difference (your added word should be in the "Saved version" column).
4. Click `📋 Stage for Review`. **Expected:** Modal closes, post action bar shows `📋 Review Staged` button (amber), MD panel panel header shows "📋 Staged — awaiting review".
5. Click `📋 Review Staged`. **Expected:** Diff modal opens in "staged review" mode with "Saved version" vs "Staged version" columns, buttons are "✕ Reject Staged" (red) and "✓ Accept Staged" (green).
6. Click `✓ Accept Staged`. **Expected:** MD panel updates to the new content, Staged button disappears, badges update.
7. Repeat steps 2–4 but click `✕ Reject Staged`. **Expected:** staged file deleted, post returns to pre-staged state.

#### MT-5: ⊙ Source / Cleaned Toggle (New-Schema Projects Only)

**When to run:** After running a real import into kie-fresh, or after any change to `_loadHtmlPanel()` or `_updateSourceBanner()`.

**Prerequisite:** kie-fresh project must have at least one ingested post (source/ and cleaned/ both populated).

**Steps:**
1. Open kie-fresh project, select any post.
2. **Expected:** HTML panel shows "Cleaned HTML" label with `⊙ Source` button visible.
3. Click `⊙ Source`. **Expected:** Panel switches to source HTML (original http:// image URLs, images might not load), label changes to "Original Source".
4. Click `⊙ Cleaned`. **Expected:** Returns to cleaned view with local /assets/ images.
5. Navigate to another post. **Expected:** View resets to Cleaned (not stuck on Source).

**Note:** For the KIE legacy project, the `⊙ Source` button should NOT appear (both panels serve from the same directory). Verify this is the case.

#### MT-6: Bulk Operations

**When to run:** After any change to `generateAll()`, `scanAll()`, `validateAll()`, or their server endpoints.

**Steps (use filtered scope to limit scope):**
1. Filter to "No MD" (if any posts lack MD). Click `⚙ Gen scope`. **Expected:** Progress shows slug-by-slug, button re-enables when done, post count updates.
2. Filter to "All". Click `🔍 Scan scope`. **Expected:** All 577 posts scanned, progress visible, HTML column in Overview updates.
3. Filter to "HTML ⚠". Click `⟳ Consolidate`. **Expected:** Report shows N promoted, N HTML files updated (or 0/0 if nothing shared).
4. Filter to "📋 Staged" (if any exist). Verify `✓ Accept all staged` and `✕ Reject all staged` buttons appear. Click Accept all → confirm dialog → all staged posts should flip to current.

---

### Test Plan for New Features

When adding new features, the following tests should be written BEFORE or ALONGSIDE the implementation:

#### For any new server endpoint:
1. Unit test: endpoint returns correct status code for valid input
2. Unit test: endpoint returns 404 for nonexistent resources
3. Unit test: endpoint returns 400 for missing required parameters
4. Integration test (if writes state): verify state is correct after the call
5. Integration test (if modifies files): verify files exist/don't exist as expected
6. Security: does the endpoint accept malicious input? (path traversal, XSS, large payloads)

#### For any new ingest behaviour:
1. Unit test against mock blog server (20 articles, known dates)
2. Test the happy path: result has no error, expected files created
3. Test idempotency: running twice produces same result, no duplicates
4. Test edge cases: empty input, malformed URLs, unreachable host

#### For any new UI feature:
1. Check for JS errors on page load (DOM ordering issues — the modal bug)
2. Verify API calls succeed with correct payloads (check Network tab)
3. Manual test of the full flow including error states
4. Verify the feature works for BOTH legacy and new-schema projects (or document which schema it requires)

---

### Regression Matrix — Critical Paths

This table maps user-facing features to the tests that protect them. If a test in the "Protected by" column fails, the feature listed is likely broken.

| Feature | Protected by | Manual test |
|---|---|---|
| Projects list loads | `TestProjectsList::test_returns_list` | MT-1 |
| Active project shows | `TestProjectsList::test_active_field_present` | MT-1 |
| Import modal opens | No automated test | MT-1 |
| Discover URLs from blog | `TestIngestDiscover::test_discovers_mock_blog_posts` | MT-1 |
| New project created | `TestProjectCreate::test_creates_project_with_local_paths` | MT-1 |
| Project deleted cleanly | `TestProjectDelete::test_deletes_project` | MT-1 |
| Wipe clears data | `TestProjectWipe::test_wipe_clears_data_directories` | — |
| Wipe rejects legacy | `TestProjectWipe::test_wipe_rejects_legacy_schema_projects` | — |
| Append date cutoff | `TestAppendMode::test_cutoff_is_exclusive` | MT-1 |
| Post opens in review | No automated test | MT-2 |
| Scan detects issues | `TestScanPostIntegration::test_detects_multiple_issue_types` | MT-2 |
| Issue highlighting | `TestSelectorGeneration::test_selector_for_img` | MT-3 |
| MD generation dry-run | `TestIngestDiscover::test_discovers_mock_blog_posts` | MT-2 |
| Diff modal shows diff | No automated test | MT-4 |
| Stage workflow | No automated test | MT-4 |
| Scroll sync | No automated test | MT-2 |
| Source/cleaned toggle | No automated test | MT-5 |
| Bulk Gen scope | No automated test | MT-6 |
| Bulk Scan scope | No automated test | MT-6 |
| Consolidation | `TestConsolidationAfterIngest::*` | MT-6 |
| XSS stripped | `TestXSSInContent::test_onerror_attribute_stripped` | — |
| file:// rejected | `TestURLSchemeInjection::test_file_url_returns_error` | — |
| Sitemap injection | `TestSitemapURLInjection::test_file_urls_in_sitemap_filtered` | — |
| Full ingest pipeline | `TestFullPipelineLayout::*`, `TestIngestPipelineViaApi::*` | MT-5 (kie-fresh) |
| Wipe+reimport cycle | `TestWipeAndReimport::*`, `TestProjectWipe::*` | MT-1 + MT-5 |
| MD 31 validation checks | `TestValidatorStructure::test_clean_post_has_no_errors` | MT-2 |

**Gaps (no automated coverage — future work):**
- Import modal 3-mode selection logic (pure JS, needs browser test)
- Diff modal side-by-side rendering (pure JS, needs browser test)
- Staged workflow UI (pure JS, needs browser test)
- Scroll sync algorithm (pure JS, needs browser test)
- ⊙ Source/Cleaned toggle (pure JS, needs browser test)
- Keyboard shortcuts (pure JS, needs browser test)

These gaps are documented here so future Claude knows they exist and can add Playwright tests when the time comes.
