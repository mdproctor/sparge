# Sparge — Design Snapshot
**Date:** 2026-04-06
**Topic:** Codebase consolidation into ~/claude/sparge
**Supersedes:** [2026-04-06-sparge-edit-experience-and-docs](2026-04-06-sparge-edit-experience-and-docs.md)
**Superseded by:** *(leave blank — filled in if this snapshot is later superseded)*

---

## Where We Are

Sparge is a fully self-contained blog migration tool living at `~/claude/sparge/` with its own private GitHub repo (https://github.com/mdproctor/sparge). The codebase was consolidated from `blog-migrator/` inside the Jekyll publishing repo — that directory has been removed. The tool has a three-stage immutable pipeline (Ingest → Scan/Enrich → Generate MD), CodeMirror-powered three-partition edit mode with live preview, content-hash asset deduplication (`asset_store.py` + `consolidate.py`), and 320 passing tests. The KIE archive project has 577 posts tracked, 576 clean, 31 with MD generated.

## How We Got Here

| Decision | Chosen | Why | Alternatives Rejected |
|---|---|---|---|
| Three-stage immutable pipeline | [ADR-0001](../adr/0001-three-stage-immutable-pipeline.md) | — | — |
| User-level storage | [ADR-0002](../adr/0002-user-level-storage-architecture.md) | — | — |
| Author filter: config + UI | [ADR-0003](../adr/0003-author-filter-config-and-ui.md) | — | — |
| Enrichment at Scan | [ADR-0004](../adr/0004-enrichment-at-scan-not-ingest.md) | — | — |
| Consolidate to `~/claude/sparge` | Removed `blog-migrator/` from Jekyll repo; sparge is the single canonical codebase | Jekyll repo is for publishing only; two codebases caused repeated confusion across Claude sessions — each session read HANDOVER.md and guessed wrong location | Keep in Jekyll repo; create new repo and re-implement |
| asset_store + consolidate: Option A (additive) | Added as standalone features alongside existing ingest; `/api/consolidate` endpoint + UI button; 28 integration tests guarded for Option B | Lower risk; existing ingest untouched; Option B is a larger rearchitecture | Option B immediately — too risky during consolidation |
| `html.parser` not `lxml` for prettify | BeautifulSoup `html.parser` treats Python str as-is; lxml does charset sniffing on `<meta charset>` causing double-encoding | lxml silently garbled em dashes and curly quotes in all 577 posts | lxml; raw textarea without prettify |

## Where We're Going

**Immediate:**
- Bulk re-scan all 577 posts to apply enrichment pipeline (YouTube thumbnails, Gist inlining, brush normalisation)
- Bulk generate MD for the 546 posts without it

**Sub-project 2 — Image recovery pipeline (not started):**
- Lazy image recovery, Wayback Machine CDX, archive.today, cross-post source search, Playwright iframe recovery

**Option B — Full ingest rearchitecture (logged in `docs/ideas/IDEAS.md`):**
- `source/cleaned/assets_root` separation; `AssetStore` used during ingest rather than post-ingest only

**Next steps:**
- Write bulk re-scan script
- Begin Sub-project 2 planning

**Open questions:**
- Should `enriched/` copies be committed to git or gitignored? Currently untracked.
- Should the full 1,801-post KIE archive (all authors) become one Sparge project?
- What is the right disposition for legacy `scripts/` in the Jekyll repo — delete or keep for reference?

## Linked ADRs

| ADR | Decision |
|---|---|
| [ADR-0001](../adr/0001-three-stage-immutable-pipeline.md) | Ingest → Scan/Enrich → Generate MD; original HTML never mutated |
| [ADR-0002](../adr/0002-user-level-storage-architecture.md) | `~/.sparge/config.json` → `~/sparge-projects/` |
| [ADR-0003](../adr/0003-author-filter-config-and-ui.md) | Config sets default author scope; UI dropdown overrides |
| [ADR-0004](../adr/0004-enrichment-at-scan-not-ingest.md) | HTML fixes applied at Scan, written to `enriched/` |

## Context Links

- Pipeline reference: [`docs/pipeline.md`](../pipeline.md)
- Option B idea: [`docs/ideas/IDEAS.md`](../ideas/IDEAS.md)
- Blog diary: [`docs/blog/`](../blog/)
- GitHub: https://github.com/mdproctor/sparge
