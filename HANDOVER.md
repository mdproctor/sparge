# Handover — 2026-04-14

**Head commit:** `4810147` — fix(#1): resolve 4 pre-existing md_validator test failures
**GitHub:** https://github.com/mdproctor/sparge (private)
**Previous handover:** `git show HEAD~1:HANDOVER.md`

## What Changed This Session

- **Archive Quality Sweep (epic #15) — fully closed.** All 11 open issues resolved.
- **Test count:** 456 passing / 5 failing → **473 passing / 0 failing**
- **New tests added:** 12 for convert_post.py pipeline fixes (#6), XML code signal (#37)
- **New feature:** Search bar (`#search-input`, `#search-scope` title/body/both) in `ui/index.html`; wired into `filtered()` so search stacks with filter buttons and issue-type scoping
- **Bug fix:** Divider drag `pointer-events:none` on iframe during drag — leftward drag no longer stalls
- **Bug fix:** `cross_table_acknowledged` now uses cell-count (≥2 cells = significant) not pure text length
- **Bug fix:** 4 pre-existing md_validator failures resolved (duplicate test needed HTML; language/youtube tests moved to `refine()`; table significance threshold)
- **Housekeeping:** CLAUDE.md test count updated, stale `docs/design-snapshots/` path fixed, DESIGN.md Next Steps updated to show Quarkus migration as declared next

## Issues Closed This Session

| # | Title | How |
|---|---|---|
| #1 | MD validator false positives | 4 pre-existing failures fixed |
| #2 | html2text trailing whitespace | Already done; closed |
| #3 | HTML editor save not visible | Already done; closed |
| #4 | HTML↔MD editor switch | Already done; closed |
| #5 | Scroll sync broken | Already done; closed |
| #6 | convert_post.py pipeline fixes | Regression tests added |
| #7 | md_notation_in_text scan check | Already done; closed |
| #8 | generateAll() overwrite prompt | Already done; closed |
| #37 | Code block recovery | XML strong signal added |
| #38 | Search bar + divider drag | Implemented |
| #15 | Archive Quality Sweep (epic) | Closed |

## State Right Now

- **Application:** `~/claude/sparge/` — 473 tests passing, 0 failing
- **KIE archive posts:** 577 HTML in `~/mdproctor.github.io/legacy/posts/mark-proctor/`
- **MD output:** 31 files in `~/mdproctor.github.io/mark-proctor/` (546 still need generation)
- **Enriched folder:** Empty — Sparge's bulk scan has never been run
- **Open GitHub issues:** 0
- **v1.0.0** shipped (tagged, binaries on GitHub Releases)

## Declared Next: Quarkus Migration Phase 0

The v1.0.0 blog entry explicitly says "Phase 0 is next." This is the next piece of work.

**What Phase 0 means:**
- Scaffold a Quarkus project alongside the existing Python server
- Wire in JEP (Java Embedded Python) so Quarkus delegates ALL operations to the existing Python modules
- Zero porting at Phase 0 — the goal is to establish the bridge and prove the architecture
- `libpython3.12.dylib` is confirmed present in `resources/python/mac-arm64/lib/` — JEP can link against it

**Where the design lives:**
- Design spec: `docs/superpowers/specs/2026-04-10-quarkus-native-migration-design.md`
- No plan file written yet — Phase 0 plan needs to be drafted before any code

**Phase sequence (from design):**
- Phase 0: Quarkus JVM + JEP → delegates everything to Python
- Phase 1–N: Port modules one by one (state/config → scan/enrich → convert → ingest)
- Final: Remove JEP + CPython bundle → Quarkus Native

## References

| Context | Where | Retrieve with |
|---|---|---|
| Quarkus migration design | `docs/superpowers/specs/2026-04-10-quarkus-native-migration-design.md` | `cat` |
| Pipeline reference | `docs/pipeline.md` | `cat` |
| ADRs | `docs/adr/` | `ls` then `cat` as needed |
| Living design doc | `DESIGN.md` | `cat` |
| Development diary | `docs/_posts/` | `ls` then `cat` as needed |
| Option B idea | `docs/ideas/IDEAS.md` | `cat` |

## Environment

- **Sparge repo:** `~/claude/sparge/` — GitHub: https://github.com/mdproctor/sparge
- **Run server:** `cd ~/claude/sparge && python3 server.py` (port 9000)
- **Run tests:** `cd ~/claude/sparge && python3 -m pytest tests/ -q`
- **Project data:** `~/sparge-projects/kie-mark-proctor/`
- **App config:** `~/.sparge/config.json` → points to `~/sparge-projects/`
- **Jekyll blog (content only):** `~/mdproctor.github.io/` — separate repo, no app code
