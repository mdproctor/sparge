# Retro Issues Proposal
*Generated 2026-04-08. Review and edit before confirming YES.*

---

## Phase Boundaries

| Date | Signal | Phase |
|------|--------|-------|
| 2026-04-01 | Scaffold commit + KIE archive plan doc | Phase 1: KIE Archive Scripts |
| 2026-04-03 | Blog entry "Two Apps, One Tool" | Phase 2: Sparge Foundation |
| 2026-04-05 (morning) | ADR 0001-0004 created, pipeline spec | Phase 3: Content Fidelity & Storage |
| 2026-04-05 (afternoon) | Edit mode spec + CodeMirror plan | Phase 4: Edit Experience |
| 2026-04-06 | Consolidation + docs, 5-blog-entry series | Phase 5: Consolidation |
| 2026-04-07+ | This session (current) | Phase 6: Archive Quality Sweep |

---

## Epic A — KIE Archive Extraction Scripts
*2026-04-01. Pre-Sparge scripting phase: extract, rescue, and convert 577 KIE blog posts.*

**Definition of Done:** 577 posts extracted as local HTML archives with images localised, ready for review tooling.

### A1 — Build post discovery, metadata extraction, and resumable state
`feat: post discovery helpers` · `feat: metadata extraction from WordPress HTML` ·
`feat: resumable state file load/save` · `feat: author slug and post slug normalisation` ·
`fix: author selector for real KIE blog markup`

### A2 — Image download with SHA-256 dedup + multi-source recovery
`feat: image download with SHA-256 deduplication` · `feat: add Wayback Machine image recovery` ·
`fix: add Wayback fallback to lazy image recovery` · `feat: lazy image recovery — wire 4,632 already-cached images` ·
`feat: comprehensive 5-approach image recovery` · `feat: comprehensive image recovery — Wayback CDX, ederign.me URL remapping`

### A3 — YouTube thumbnail replacement + GitHub Gist inlining + HTML shell
`feat: YouTube iframe extraction and thumbnail replacement` · `feat: GitHub Gist detection, API fetch, and inline code replacement` ·
`feat: standalone HTML shell wrapper with archive metadata` · `feat: article content cleaning, attribute stripping` ·
`fix: HTML-escape YouTube/Gist values in generated HTML`

### A4 — Validation pass, index generator, and orchestrator
`feat: validation pass for images, links, and unreplaced gists` · `feat: index generator` ·
`feat: main extraction orchestrator` · `fix: strip trailing slashes in url_to_mirror_path` ·
`fix: strip URL fragments in check_local_links`

### A5 — Batch MD conversion (first attempt, later superseded)
`feat: convert all 578 Mark Proctor posts to Jekyll Markdown` ·
`chore: remove auto-converted mark-proctor posts — starting over with manual review process`

---

## Epic B — Sparge Application Foundation
*2026-04-03 to 2026-04-04. Blog Migrator → Sparge: build the core review application.*

**Definition of Done:** Multi-project tool with ingest pipeline, two-panel HTML+MD review UI, asset scanning, and 214 tests.

### B1 — Initial two-panel review tool with asset scanning and issue highlighting
`feat: complete App 1 (HTML archive reviewer) + App 2 (MD conversion reviewer)` ·
`feat(blog-migrator): add full blog migration review tool` · `feat(blog-migrator): asset scanning and issue highlighting`

### B2 — Ingest pipeline: URL discovery, image localisation, background jobs
`feat(blog-migrator): ingestion pipeline + bulk ops + manual MD editing` ·
`feat(blog-migrator): validate scope, bulk staged ops, manual MD editing`

### B3 — Multi-project architecture + projects landing page
`feat(blog-migrator): multi-project architecture with projects landing page`

### B4 — Test suite, security fixes, scan actions merge, rename to Sparge
`feat(blog-migrator): test suite + security fixes + navigation bug fix` ·
`fix(blog-migrator): merge Scan HTML + Scan Assets into single Scan action` ·
`brand: rename Blog Migrator → Sparge`

---

## Epic C — Content Fidelity & Storage Architecture
*2026-04-05 morning. Three-stage pipeline, enrichment, user-level storage, author filter.*

**Definition of Done:** Immutable ingest → enriched copies → MD generation. YouTube/Gist/code enrichment working. Project data in `~/sparge-projects/`. Author filter in config + UI.

### C1 — Three-stage enrichment pipeline (YouTube, Gist, code classes, fallbacks)
`feat(enrich): YouTube iframe → thumbnail figure` · `feat(enrich): Gist script tag → inlined code figure` ·
`feat(enrich): brush:X class normalisation + language detection` · `feat(enrich): unknown iframe/object/embed → live-embed fallback` ·
`feat(enrich): enrich_post() orchestrator` · `feat(state): add mark_enriched()` ·
`feat(server): enriched HTML pipeline — scan enriches first, generate-md prefers enriched`

### C2 — User-level storage migration (~/.sparge + ~/sparge-projects)
`feat(sparge-home): read ~/.sparge/config.json` · `feat(sparge-home): auto-migrate projects from blog-migrator/projects/` ·
`feat(server): use PROJECTS_DIR from ~/.sparge/config.json`

### C3 — Author filter: config default + UI override
`feat(server): GET /api/posts?author=X` · `feat(ui): author filter dropdown` ·
`fix(ui): avoid double fetch on startup`

### C4 — MD conversion pipeline improvements
`fix(server): validate-md cross-checks also prefer enriched HTML` ·
`docs(pipeline): fix Stage 2a fix table` ·
`chore: remove one-off migration code`

---

## Epic D — HTML/MD Edit Experience
*2026-04-05 afternoon. CodeMirror editors, three-partition layout, prettification, exit flows.*

**Definition of Done:** CodeMirror HTML + MD editors with live preview, scroll sync, save/discard/unsaved-changes modal, and HTML prettification working correctly.

### D1 — CodeMirror editors (HTML + MD) with syntax highlighting
`feat(ui): load CodeMirror 5 from CDN` · `feat(ui): upgrade MD editor from textarea to CodeMirror` ·
`feat(ui): add CodeMirror HTML editor` · `feat(server): GET /api/posts/{slug}/html` ·
`feat(server): POST /api/posts/{slug}/save-html`

### D2 — Edit mode three-partition layout + scroll sync + live preview
`feat(ui): add #edit-sidebar HTML and CSS` · `feat(ui): unified enterEditMode(mode)` ·
`feat(ui): debounced live preview` · `feat(ui): edit mode scroll sync`

### D3 — Save/discard/unsaved-changes exit flows + tests
`feat(ui): exitEditMode, saveEditContent, discardEdit` · `feat(ui): styled unsaved-changes modal` ·
`fix(ui): address code review — double-slash URL, scroll accumulation, async toggles` ·
`test(edit-mode): comprehensive unit + integration tests` · `test(edit-flow): integration tests for HTML/MD save/retrieve cycle`

### D4 — HTML prettification fix (lxml → html.parser) + prettify tests
`feat(server): pretty-print HTML in editor view` · `fix(server): use html.parser not lxml for prettify` ·
`test(prettify): 19 tests + runtime garbling detection` · `test(prettify): regression guard`
*(Incorporates existing issues #3, #4, #5)*

### D5 — Edit experience bug fixes (save visibility, editor switch, scroll sync)
*Maps to existing open issues #2 #3 #4 #5 — leave open for linkage.*

---

## Epic E — Consolidation & Asset Store
*2026-04-06. Integrate asset_store + consolidate from original Sparge ancestor.*

**Definition of Done:** `POST /api/consolidate` endpoint working; project docs moved into repo; blog series complete.

### E1 — Asset store + global consolidation integration
`feat(sparge): integrate asset_store + consolidate from original sparge — Option A`

### E2 — Documentation: blog series, design snapshots, handover
`docs: Sparge blog series — all 5 entries` · `docs: add design snapshot 2026-04-06-*` ·
`docs: session handover` · `chore: remove blog-migrator/ — Sparge now lives at ~/claude/sparge`

---

## Epic F — Archive Quality Sweep
*2026-04-07 (this session). Comprehensive scan/validate improvements, image handling, code blocks, UI polish.*

**Definition of Done:** 0 false-positive scan/validation issues across 577 posts. Pipeline invariants tested. All imgur images resolved. All scan check types have tests.

### F1 — HTML scan pipeline fixes: invariants, stale detection, scan-not-re-enriching
*Maps to current session work: pipeline invariants test suite, stale hash tracking fix (html.hash / md.html_hash using enriched copy), scan no longer re-enriches existing copies.*
*(Partially covered by existing issues #7, #9)*

### F2 — MD validator false positive sweep
*Maps to existing open issue #1 — systematic reduction 41 → 0 false positives.*
*Validator fixes: URL-only paragraphs, ordinal whitespace, smart quotes, escaped list markers, caption-in-div skip.*

### F3 — Image handling: imgur/Wayback, external localisation, ingest improvements
*New issue: imgur geo-blocking detection + Wayback resolution in ingest; external image localisation for href links; br→newline in pre blocks at ingest; wayback fallback for all failed downloads.*

### F4 — Code block recovery and detection
*New issue: potential_code_block and code_no_newlines scan checks; br→newline fix in convert_post; per-post DRL/XML code block fixes.*

### F5 — UI improvements: search bar, divider drag, project delete, issue type scoping
*New issue: post list search (Title/Body/Both via API); iframe pointer-events fix for divider drag; JSON.stringify onclick bug in project delete; issue-type filter scoping button.*
*(Incorporates existing issues #8)*

### F6 — MD generation fixes: generateAll overwrite prompt, figure captions, pipeline
*Maps to existing open issues #6 #8 — converter pipeline fixes, generateAll overwrite modal.*

---

## Standalone Issues

### S1 — chore: code quality, shared constants, broken import, migration docs
*Existing issue #9 — not part of any epic.*

---

## Excluded Commits (trivial)

| Commit | Reason |
|--------|--------|
| `chore: gitignore __pycache__` | Pure gitignore / whitespace |
| `chore: ignore .worktrees/` | Pure gitignore |
| `chore: ignore .superpowers/` | Pure gitignore |
| `chore: remove __pycache__ from git tracking` | Pure housekeeping |
| `chore: document lxml 5.x version rationale` | Inline comment doc only |
| `fix: move BS4 import to top` | Trivial import reorder |
| `chore: remove test project artifacts` | Cleanup only |
| `chore: remove project dirs from ~/sparge-projects/` | Cleanup only |
| `Add KIE blog archive design spec` | Doc scaffold only |
| `Add KIE blog archive implementation plan` | Doc scaffold only |
| `sample blog` (×2) | Initial Jekyll sample posts, not Sparge |
| `Initial commit` | Empty Jekyll scaffold |

---

## Summary

| | Count |
|--|--|
| Epics proposed | 6 (A–F) |
| Child issues | 25 |
| Standalone issues | 1 |
| Excluded commits | 13 |
| Existing issues to close | #1, #2, #6, #7, #9 (completed work) |
| Existing issues to keep open | #3, #4, #5, #8 (may still need linkage) |

