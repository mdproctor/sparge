# Idea Log

Undecided possibilities — things worth remembering but not yet decided.
Promote to an ADR when ready to decide; discard when no longer relevant.

---

## 2026-04-07 — Content Refinement Pipeline

**Priority:** medium
**Status:** active

A second pipeline stage that runs after migration fidelity is confirmed ("Content Fixing"). Rather than flagging conversion losses, it surfaces quality improvements that apply to both the HTML source and the MD — the conversion was faithful, but the original content could be better. Checks already implemented and collecting data via `refine()` in `md_validator.py`; suggestions stored in `state.md_suggestions` on every validate/generate call.

**What needs building:**
- UI: "Refine" view tab in the issue panel (separate from the "Fix" tab)
- Scope action: "⚑ Refine scope" button alongside ⚙ Generate / 🔍 Scan
- Per-check fix strategies for each refinement type:
  - `prose_in_code` — move prose out of fenced block, make it a preceding paragraph
  - `language_tag_missing` — auto-detect or prompt user to tag code fences
  - `youtube_links_dropped` — embed YouTube thumbnail + link using the enrichment step
- Bulk apply: "fix all `language_tag_missing` in scope" pattern
- Separate badge/count from the conversion-defect badge

**Context:** Emerged from auditing MD issues on the KIE blog migration. Many validator checks were flagging original content quality characteristics (prose in `<pre>`, untagged code blocks, YouTube embeds) rather than conversion losses. These are genuinely worth improving but are a distinct concern from "did the converter faithfully reproduce the HTML content." Split into `REFINEMENT_CHECKS` / `CROSS_REFINEMENT_CHECKS` registries in `md_validator.py` on 2026-04-07.

**Promoted to:** spec `docs/superpowers/specs/2026-04-21-stage4-refinement-pipeline-design.md` — implemented in epic #70
