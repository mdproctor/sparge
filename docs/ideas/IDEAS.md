# Idea Log

Undecided possibilities — things worth remembering but not yet decided.
Promote to an ADR when ready to decide; discard when no longer relevant.

---

## 2026-04-06 — Full ingest rearchitecture using asset_store.py (Option B)

**Priority:** high
**Status:** active

Adopt sparge's original 3-stage ingest architecture fully into the pipeline.
Currently `ingest.py` uses URL-hash dedup with a flat `assets/` layout — it
writes one HTML file (already rewritten) with no separation between the raw
source and the cleaned version. The full architecture separates `source/`
(raw HTML), `cleaned/` (rewritten HTML), and `assets/global/` + `assets/posts/{slug}/`
with `AssetStore`-based URL-index routing during ingest and content-hash
consolidation post-ingest.

Required changes: new `ingest_post` signature `(source_dir, cleaned_dir, assets_root)`;
`_localise_with_store` replacing `_asset_local_path`; `AssetStore` used throughout
ingest; `_activate_project` updated with new path variables; `config.json` schema updated.

**Context:** Decision made 2026-04-06 to do Option A first — `asset_store.py` and
`consolidate.py` integrated as additive features alongside the existing ingest
(not wired into it). Option B is the next planned feature once the codebase
consolidation into `~/claude/sparge` is complete.

**Promoted to:** *(leave blank — fill if promoted to ADR or task)*
