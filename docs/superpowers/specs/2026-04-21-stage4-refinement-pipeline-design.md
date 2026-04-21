# Stage 4 — Content Refinement Pipeline Design

**Date:** 2026-04-21  
**Status:** Approved  
**Promoted from:** `docs/ideas/IDEAS.md` — Content Refinement Pipeline entry

---

## Overview

Stage 4 sits between Generate MD (Stage 3) and Publish. It surfaces content quality improvements detected by the refinement validator (`refine()` in `md_validator.py`) and lets the user selectively apply them to the generated MD. Refinements are stored as typed rules with content anchors, not raw text diffs, so they can be replayed automatically when MD is regenerated.

**Pipeline:**
```
[Ingest] → [Scan/Enrich] → [Generate MD] → [Refine] → [Publish]
```

---

## Section 1 — Architecture & Data Model

### State additions (per post in `state.json`)

```json
"refinement": {
  "refined_at": "2026-04-21T...",
  "accepted": [
    {
      "check": "language_tag_missing",
      "fence_index": 3,
      "fingerprint": "sha256:normalised-block-content",
      "fix": { "language": "java" }
    },
    {
      "check": "prose_in_code",
      "fence_index": 7,
      "fingerprint": "sha256:...",
      "fix": { "extracted_text": "Some prose..." }
    }
  ],
  "replay_conflicts": ["prose_in_code@fence_7"]
}
```

### Replay engine (`scripts/refine_replay.py`)

Replays accepted refinement rules against a newly generated MD:

1. For each accepted rule, locate target fence by `fence_index`
2. Verify via fingerprint similarity (≥ 85% match on normalised content)
3. If fingerprint misses, slide ±2 fences and retry — fuzzy position recovery
4. Apply the fix; if no fence matches the threshold, add to `replay_conflicts`
5. Returns: refined MD text + list of unresolved rule identifiers

### Refinement checks (existing, in `md_validator.py`)

| Check | What it detects | Fix stored |
|-------|-----------------|------------|
| `language_tag_missing` | Code fences with no language class — language detected by heuristic | `{ language: "java" }` |
| `prose_in_code` | Prose sentences inside fenced code blocks | `{ extracted_text: "..." }` |
| `youtube_count` | YouTube embed count mismatch HTML vs MD | Verification only — never stored in `accepted`, no replay |

### On regeneration

If `refinement.accepted` is non-empty when Generate MD runs, the replay engine runs automatically after writing the new MD file. Conflicts are written to `refinement.replay_conflicts`. Replay never blocks generation — conflicts surface as a badge.

---

## Section 2 — UI

### Pipeline toggle button

Located in the existing action bar. Cycles between two split-view modes:

- `≡ HTML→MD` — existing view: left = enriched HTML iframe, right = generated MD
- `≡ MD→Refined` — new view: left = original MD (read-only), right = refined MD with inline diff

Toggle is disabled until `md.generated_at` exists for the post.

### Refine mode split view

- **Left panel:** original MD, read-only, plain text, synced scroll with right
- **Right panel:** refined MD with inline diff — green for added/changed lines, red strikethrough for removed
- **Divider:** draggable as usual
- Reuses the existing `#html-panel` / `#md-panel` elements with different render modes

### Suggestions panel (third column)

Mirrors the existing issues panel. Opens automatically when entering Refine mode.

**Structure:**
```
[Refinements]                              [×]
─────────────────────────────────────────────
[⊕ Add all]  [⊖ Remove all]
─────────────────────────────────────────────
[− Remove]  language_tag_missing
            3 code blocks: java, xml, sql
─────────────────────────────────────────────
[− Remove]  prose_in_code
            Line 42: prose in code block
─────────────────────────────────────────────
[+ Add  ]  youtube_count                  ← greyed (40% opacity)
            1 embed — verify figure
─────────────────────────────────────────────
⚠ prose_in_code@fence_7 — replay conflict ← amber, no toggle
  Re-enter refine mode to resolve manually
```

**Interaction:**
- All suggestions start in Added state on entering Refine mode
- `[− Remove]` / `[+ Add]` toggles individual suggestion; removed entries at 40% opacity
- `⊕ Add all` / `⊖ Remove all` are bulk toggles
- Each toggle triggers a server round-trip to recompute `refined_md` with the new accepted set
- Replay conflicts shown in amber with `⚠` prefix — no add/remove, must be manually resolved
- Close button returns panel to Issues view

### Accept flow

- `Accept refined` button in action bar — visible only in Refine mode, enabled only when ≥ 1 suggestion is Added
- Writes refined MD over existing `.md` file
- Stores `refinement.accepted` (with fingerprints) and `refined_at` to state
- Switches back to HTML→MD view
- Post badge updates to `✨ Refined` or `⚠ N conflicts` as appropriate

### Post badges

| Badge | Meaning |
|-------|---------|
| `✨ Refined` | Accepted refinements applied, all replay cleanly |
| `⚠ N conflicts` | Replay found unresolved rules after last regeneration — amber |

---

## Section 3 — Data Flow & Error Handling

### Entering Refine mode

1. `GET /api/posts/{slug}/refine` — server runs `refine()` on current MD, returns `{ suggestions, refined_md }` with all suggestions auto-applied
2. Left panel loads raw MD; right panel renders diff against `refined_md`
3. Suggestions panel populates — all entries in Added state
4. Nothing written to disk until Accept

### Toggling a suggestion

- `POST /api/posts/{slug}/refine` with `{ accepted: ["language_tag_missing", ...] }`
- Server re-runs apply with only specified checks, returns updated `refined_md`
- Right panel diff re-renders; suggestions panel updates opacity
- Fast round-trip (pure text processing, no filesystem I/O)

### Accepting

- `POST /api/posts/{slug}/refine/accept` with `{ accepted: [...with fingerprints...] }`
- Server applies rules, writes MD file, stores `refinement` to state
- On disk write failure: error shown in action bar, no state change

### After regeneration (auto-replay)

- `POST /api/posts/{slug}/generate` (existing) — after writing new MD, server checks `refinement.accepted`; if non-empty, runs replay engine
- Conflicts written to `refinement.replay_conflicts`; returned in post state
- All clean → `✨ Refined` badge; any conflicts → `⚠ N conflicts` badge

### Error states

| Situation | Behaviour |
|-----------|-----------|
| MD not generated yet | Toggle button disabled, tooltip: "Generate MD first" |
| No suggestions detected | Refine mode opens, empty panel: "No refinements detected for this post" |
| All suggestions removed | Accept button disabled |
| Replay conflict after regen | Amber badge; conflict rows in suggestions panel — user resolves manually |
| Disk write failure on accept | Error shown inline, state unchanged |

---

## New API endpoints

| Method | Path | What |
|--------|------|------|
| `GET` | `/api/posts/{slug}/refine` | Run refinement, return suggestions + full refined MD |
| `POST` | `/api/posts/{slug}/refine` | Re-run with subset of accepted checks, return updated refined MD |
| `POST` | `/api/posts/{slug}/refine/accept` | Write refined MD to disk, store accepted rules to state |

Existing `POST /api/posts/{slug}/generate` extended to auto-replay if `refinement.accepted` is non-empty.

---

## New files

| File | What |
|------|------|
| `scripts/refine_replay.py` | Replay engine — applies accepted rules with fuzzy fence matching |
| `server/src/main/java/io/sparge/server/RefineResource.java` | Java endpoint wiring the three new API routes |

## Modified files

| File | Change |
|------|--------|
| `scripts/state.py` | Add `refinement` field to post state schema |
| `scripts/md_validator.py` | Already has `refine()` — expose result shape for API |
| `server/src/main/java/io/sparge/server/PostsResource.java` | Auto-replay hook in `generate` endpoint |
| `ui/index.html` | Pipeline toggle, Refine mode split view, suggestions panel, badges, Accept button |

---

## Out of scope

- Bulk refinement across multiple posts in one action (Ideas.md mentions "Bulk apply" — deferred)
- Manual text editing inside the refined MD panel (diff view is read-only; freeform edits remain in the MD editor)
- `youtube_count` fix automation (this is a verification check only — no auto-fix)
