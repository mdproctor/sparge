# Sparge — Design Snapshot
**Date:** 2026-04-05
**Topic:** Content fidelity pipeline, storage architecture, and author filter
**Supersedes:** *(none)*
**Superseded by:** [2026-04-06-sparge-edit-experience-and-docs](2026-04-06-sparge-edit-experience-and-docs.md)

---

## Where We Are

Sparge is a blog migration tool (previously "Blog Migrator") that ingests HTML posts from live URLs, processes them through a multi-stage pipeline, and produces Jekyll Markdown. Today's work completed three significant milestones: a content fidelity enrichment stage (YouTube thumbnails, Gist inlining, code class normalisation, language detection, unknown embed fallbacks), a proper user-level storage architecture (`~/.sparge/` + `~/sparge-projects/`), and an author filter across both the API and UI. The tool processes the 1,801-post KIE archive with 576/577 posts clean, and is general enough to handle future blog migration projects.

## How We Got Here

| Decision | Chosen | Why | Alternatives Rejected |
|---|---|---|---|
| Three-stage immutable pipeline | Ingest → Scan (enriched/) → Generate MD | Original HTML never mutated; each stage is idempotent and re-runnable | Mutating HTML in place during ingest |
| Enrichment at Scan, not Ingest | Scan writes `enriched/` copy; Generate MD reads it | Keeps Ingest as a pure download; all transformations explicit and re-runnable | Enriching during ingest; enriching only at MD generation time |
| YouTube: thumbnail download | Download `maxresdefault.jpg` → local assets; replace iframe with `<figure class="video-embed">` | Archive works offline; no live embed dependency | Strip iframes silently; keep as live embed |
| Gist: inline via GitHub API | Fetch content, inline as `<pre><code>`; fallback archive-note link if API fails | Code preserved in archive with no GitHub dependency to view | Strip script tags silently; keep raw script tag |
| Gist GitHub token | Optional in `config.json`; warning if Gists present but no token | 60 req/hr unauthenticated sufficient for small blogs; 5,000/hr with token for bulk | Always require token; never support authenticated |
| Unknown embeds: wrap, not strip | `<figure class="live-embed">` with archive note + link to original src | Preserves knowledge that content existed; better than silent loss | Strip all unrecognised iframes |
| SyntaxHighlighter normalisation | `brush:X` → `language-X` on `<pre>` elements | WordPress-era code blocks unusable by highlight.js without this | Leave brush: classes; handle at MD generation only |
| Storage: `~/.sparge/` + `~/sparge-projects/` | App config at `~/.sparge/config.json`; project data at `~/sparge-projects/` | Separates app code from user data; portable across code moves | Project data inside blog-migrator repo dir |
| Author filter: config + UI (Option C) | Config sets default display scope; UI dropdown overrides | Consistent (ingest and display use same author); flexible per-session | Config only (A); UI only (B) |
| Author filter: server-side | `GET /api/posts?author=X` filters in Python; UI re-fetches on change | Single source of truth; correct even without JS | Client-side JS filter only |

## Where We're Going

**Sub-project 2 — Image recovery pipeline:**
- Lazy image recovery (noscript/data-src patterns)
- Wayback Machine CDX multi-timestamp recovery
- archive.today as secondary fallback
- Cross-post source search (Red Hat, DZone, Medium)
- Playwright iframe recovery (JS-rendered iframes)
- Unrecovered URL export report for manual recovery

**Sub-project 3 — Export & review:**
- Static index.html export from project state
- Enhanced review UI (inline issue highlighting, iframe viewer alongside issue list)

**Ingest improvements (planned):**
- Content-hash image deduplication (currently URL-hash based)
- Image download retry with exponential backoff
- MIME type validation of downloaded images (catch HTML error pages saved as `.jpg`)

**Stage 3 improvements (planned):**
- `cross_technical_terms` check made configurable per project (currently hardcoded KIE terms)
- Text fingerprint sanity check during MD conversion

**Next steps:**
- Bulk re-scan the 577 Mark Proctor posts through the new enrichment pipeline (existing posts pre-date it)
- Begin Sub-project 2 (image recovery) planning
- Decide whether to create a Sparge project for the full 1,801-post KIE archive (all authors)

**Open questions:**
- Should Sparge support bulk re-scan (all posts in one API call) to avoid manual per-post scanning?
- Should SlideShare get a dedicated thumbnail-fetch path, or is the generic live-embed fallback sufficient?
- What is the right disposition for the legacy `scripts/` tools now that Sparge supersedes most of them — archive in place, delete, or migrate remaining capabilities first?
- Should `enriched/` files be committed to git or gitignored? Currently untracked.
- Should the full 1,801-post KIE archive (all authors) become a single Sparge project, or remain as author-scoped projects?

## Linked ADRs

| ADR | Decision |
|---|---|
| [ADR-0001 — three-stage immutable pipeline](../adr/0001-three-stage-immutable-pipeline.md) | Ingest → Scan/Enrich → Generate MD; original HTML never mutated |
| [ADR-0002 — user-level storage architecture](../adr/0002-user-level-storage-architecture.md) | `~/.sparge/config.json` points to `~/sparge-projects/` for project data |
| [ADR-0003 — author filter config and UI](../adr/0003-author-filter-config-and-ui.md) | Config sets default author scope; UI dropdown overrides per session |
| [ADR-0004 — enrichment at Scan not Ingest](../adr/0004-enrichment-at-scan-not-ingest.md) | HTML fixes applied at Scan stage, written to `enriched/` folder |

## Context Links

- Pipeline reference: [`blog-migrator/docs/pipeline.md`](../pipeline.md)
- Author filter + storage spec: [`blog-migrator/docs/superpowers/specs/2026-04-05-author-filter-design.md`](../superpowers/specs/2026-04-05-author-filter-design.md)
- Content fidelity plan: [`blog-migrator/docs/superpowers/plans/2026-04-05-content-fidelity.md`](../superpowers/plans/2026-04-05-content-fidelity.md)
- Storage + author filter plan: [`blog-migrator/docs/superpowers/plans/2026-04-05-storage-and-author-filter.md`](../superpowers/plans/2026-04-05-storage-and-author-filter.md)
