# Sparge — Design Snapshot
**Date:** 2026-04-06
**Topic:** Canonical paths, pipeline clarity, and the two-codebase confusion
**Supersedes:** [2026-04-06-sparge-consolidation](2026-04-06-sparge-consolidation.md)
**Superseded by:** *(leave blank — filled in if this snapshot is later superseded)*

---

## Where We Are

Sparge lives exclusively at `~/claude/sparge/` (GitHub: https://github.com/mdproctor/sparge). The historic confusion — Claude sessions repeatedly working in `blog-migrator/` inside the Jekyll publishing repo — is resolved: that directory no longer exists. The KIE archive project (`kie-mark-proctor`) points into the Jekyll repo for its content files, but the application code is completely separate. 326 tests passing. Pipeline paths audited, all consistent, no duplicates.

## How We Got Here

| Decision | Chosen | Why | Alternatives Rejected |
|---|---|---|---|
| Three-stage immutable pipeline | [ADR-0001](../adr/0001-three-stage-immutable-pipeline.md) | — | — |
| User-level storage | [ADR-0002](../adr/0002-user-level-storage-architecture.md) | — | — |
| Author filter: config + UI | [ADR-0003](../adr/0003-author-filter-config-and-ui.md) | — | — |
| Enrichment at Scan | [ADR-0004](../adr/0004-enrichment-at-scan-not-ingest.md) | — | — |
| Single canonical codebase at `~/claude/sparge/` | Removed `blog-migrator/` from Jekyll repo; CLAUDE.md documents the "do not work elsewhere" rule | Multiple Claude sessions confused two locations, working in the wrong repo and accumulating changes in the wrong place | Leave both locations; add warning comments |
| asset_store + consolidate: Option A | Integrated alongside existing ingest; `/api/consolidate` endpoint + UI button | Lower risk than full ingest rearchitecture | Option B (logged in IDEAS.md) |
| KIE project content stays in Jekyll repo | `serve_root` points to `~/mdproctor.github.io/`; HTML, assets, MD output all live there | Content belongs with the publishing repo; Sparge is the tool not the content store | Move content into sparge repo |

## Canonical Pipeline Paths (KIE archive project)

These paths are configured in `~/sparge-projects/kie-mark-proctor/config.json` and may differ per-project. Documented here for the current KIE archive:

| Stage | Absolute path | Files | Notes |
|---|---|---|---|
| HTML source (original) | `~/mdproctor.github.io/legacy/posts/mark-proctor/` | 577 HTML | **NEVER modify** — source of truth |
| Assets | `~/mdproctor.github.io/legacy/assets/` | 2,983 files | Images, CSS already localised by pre-Sparge scripts |
| MD output | `~/mdproctor.github.io/mark-proctor/` | 31 MD | 546 posts still need MD generated |
| Enriched HTML (Scan output) | `~/sparge-projects/kie-mark-proctor/enriched/` | 0 files | Empty — bulk scan not yet run |
| Project state | `~/sparge-projects/kie-mark-proctor/state.json` | 577 posts | Consistent with disk |

## Two-codebase confusion — root cause documented

The confusion arose in this order:
1. `~/claude/sparge` was the original proof-of-concept (8 commits, 2026-04-04)
2. Work moved to `blog-migrator/` inside the Jekyll repo but HANDOVER.md was **not updated to say so**
3. Subsequent Claude sessions read HANDOVER.md, saw `python3 blog-migrator/server.py`, and continued working there
4. This compounded: each session's handover reinforced the wrong location
5. Two days of real work (CodeMirror, edit mode, enrichment, prettify, storage, author filter) accumulated in `blog-migrator/` — the wrong place

**The fix:**
- `blog-migrator/` deleted from Jekyll repo entirely
- `CLAUDE.md` has an explicit **"Do not work in any other location"** rule with a table of canonical paths
- HANDOVER.md documents both repos clearly with absolute paths
- This snapshot documents the confusion so future Claude sessions understand the history

## State of the KIE archive posts

- HTML files already enriched by **pre-Sparge scripts** (YouTube thumbnails on ~7 posts, `language-` classes on 89 posts, `brush:` already eliminated)
- Sparge has **not yet scanned** the 577 posts — enriched/ is empty
- 31 MD files exist from pre-Sparge `convert_post.py` runs (with some content_phrase_missing warnings)
- 546 posts still need MD generation

## Where We're Going

- **Immediate:** Bulk re-scan all 577 posts through Sparge's enrichment pipeline
- **Then:** Bulk generate MD for the 546 posts without it
- **Sub-project 2:** Image recovery pipeline (Wayback Machine, lazy images, Playwright iframes)
- **Option B:** Full ingest rearchitecture — see `docs/ideas/IDEAS.md`

**Open questions:**
- Should `enriched/` copies be committed to git or gitignored? Currently untracked.
- Should the full 1,801-post KIE archive (all authors) become one Sparge project?
- Legacy `scripts/` in Jekyll repo — delete or keep for reference?

## Linked ADRs

| ADR | Decision |
|---|---|
| [ADR-0001](../adr/0001-three-stage-immutable-pipeline.md) | Ingest → Scan/Enrich → Generate MD; original HTML never mutated |
| [ADR-0002](../adr/0002-user-level-storage-architecture.md) | `~/.sparge/config.json` → `~/sparge-projects/` |
| [ADR-0003](../adr/0003-author-filter-config-and-ui.md) | Config sets default author scope; UI dropdown overrides |
| [ADR-0004](../adr/0004-enrichment-at-scan-not-ingest.md) | HTML fixes applied at Scan, written to `enriched/` |

## Context Links

- Canonical paths table: [`CLAUDE.md`](../../CLAUDE.md)
- Pipeline reference: [`docs/pipeline.md`](../pipeline.md)
- Option B idea: [`docs/ideas/IDEAS.md`](../ideas/IDEAS.md)
- GitHub: https://github.com/mdproctor/sparge
