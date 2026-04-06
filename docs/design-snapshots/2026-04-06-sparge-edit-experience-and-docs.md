# Sparge — Design Snapshot
**Date:** 2026-04-06
**Topic:** Edit experience, content fidelity, and project documentation
**Supersedes:** [2026-04-05-sparge-pipeline-and-storage](2026-04-05-sparge-pipeline-and-storage.md)
**Superseded by:** *(leave blank — filled in if this snapshot is later superseded)*

---

## Where We Are

Sparge is a blog migration tool with a full three-stage pipeline (Ingest → Scan/Enrich → Generate MD), proper user-level storage (`~/sparge-projects/`), a CodeMirror-powered three-partition edit mode with live preview, and a comprehensive test suite (261 tests). The tool is documented with a five-entry retrospective blog series and four architecture decision records. The KIE archive project has 577 posts tracked, 576 clean, 31 with MD generated.

## How We Got Here

| Decision | Chosen | Why | Alternatives Rejected |
|---|---|---|---|
| Three-stage immutable pipeline | See [ADR-0001](../adr/0001-three-stage-immutable-pipeline.md) | — | — |
| User-level storage | See [ADR-0002](../adr/0002-user-level-storage-architecture.md) | — | — |
| Author filter: config + UI | See [ADR-0003](../adr/0003-author-filter-config-and-ui.md) | — | — |
| Enrichment at Scan | See [ADR-0004](../adr/0004-enrichment-at-scan-not-ingest.md) | — | — |
| CodeMirror over plain textarea | Syntax highlighting, line numbers, proper indentation; htmlmixed + markdown modes | Textarea unusable for minified HTML (all content on one line) | Monaco (too heavy), Ace (less maintained) |
| Three-partition edit mode | Nav sidebar → edit controls, middle → CodeMirror, right → live preview | Keeps all three concerns visible simultaneously | Per-panel edit (loses context of other panel) |
| `html.parser` not `lxml` for prettify | lxml double-encodes non-ASCII via `<meta charset>` sniffing on Python str input | Silent data corruption of em dashes, curly quotes in all 577 posts | lxml (broke), raw textarea without prettify |
| Playwright + Pillow for blog screenshots | Generates realistic UI mockups as PNG without image generation AI | No alternatives — Claude cannot generate image files | n/a |
| `typora-root-url` for blog images | Root-relative paths work in both Typora and Jekyll | One path, both tools; relative paths break in Jekyll URL structure | Separate paths per tool, relative paths only |

## Where We're Going

**Sub-project 2 — Image recovery pipeline (not yet started):**
- Lazy image recovery (noscript/data-src)
- Wayback Machine CDX multi-timestamp recovery
- archive.today fallback
- Cross-post source search
- Playwright iframe recovery
- Unrecovered URL export report

**Ingest improvements (planned):**
- Content-hash image deduplication (currently URL-hash)
- Retry with exponential backoff on downloads
- MIME type validation of downloaded images

**Stage 3 improvements (planned):**
- `cross_technical_terms` check made configurable (currently hardcoded KIE terms)
- Text fingerprint sanity check during MD conversion

**Sub-project 3 — Export & review (planned):**
- Static index.html export
- Enhanced review UI with inline issue highlighting

**Next steps:**
- Bulk re-scan all 577 posts through the enrichment pipeline (pre-date enrich.py)
- Generate MD for the remaining 546 posts
- Begin Sub-project 2 (image recovery) planning

**Open questions:**
- Should `enriched/` copies be committed to git or gitignored? Currently untracked.
- Should the full 1,801-post KIE archive (all authors) become one Sparge project?
- What is the right disposition for the legacy `scripts/` tools — delete now or migrate image recovery first?
- Should Sparge support bulk scan/enrich across all posts in one API call?

## Linked ADRs

| ADR | Decision |
|---|---|
| [ADR-0001](../adr/0001-three-stage-immutable-pipeline.md) | Ingest → Scan/Enrich → Generate MD; original HTML never mutated |
| [ADR-0002](../adr/0002-user-level-storage-architecture.md) | `~/.sparge/config.json` → `~/sparge-projects/` |
| [ADR-0003](../adr/0003-author-filter-config-and-ui.md) | Config sets default author scope; UI dropdown overrides |
| [ADR-0004](../adr/0004-enrichment-at-scan-not-ingest.md) | HTML fixes applied at Scan, written to `enriched/` |

## Context Links

- Pipeline reference: [`blog-migrator/docs/pipeline.md`](../pipeline.md)
- Blog series: [`docs/blog/`](../../../docs/blog/)
- Previous snapshot: [`2026-04-05-sparge-pipeline-and-storage.md`](2026-04-05-sparge-pipeline-and-storage.md)
