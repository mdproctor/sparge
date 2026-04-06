# Handover — 2026-04-06

**Head commit:** `3194335` — docs: move all project docs, HANDOVER.md, CLAUDE.md, and blog entries into sparge
**GitHub:** https://github.com/mdproctor/sparge (private)
**Previous handover:** `git show HEAD~1:HANDOVER.md`

## What Changed This Session

- **Codebase consolidated** — All Sparge work was scattered across `blog-migrator/` inside the Jekyll repo (`mdproctor.github.io`). It is now fully consolidated into `~/claude/sparge` with its own private GitHub repo. `blog-migrator/` removed from Jekyll repo entirely.
- **`asset_store.py` + `consolidate.py` integrated (Option A)** — Two unique capabilities from the original sparge codebase ported in: URL-index asset deduplication and content-hash consolidation pass. `POST /api/consolidate` endpoint + UI button added. 86 associated tests ported (28 skip until Option B ingest rearchitecture).
- **HTML prettify** — `GET /api/posts/{slug}/html` prettifies HTML via BeautifulSoup `html.parser` before serving to editor. Fixed lxml double-encoding bug that garbled non-ASCII in all 577 posts.
- **Edit mode redesign** — Three-partition edit mode: sidebar (Save/Discard/Back), CodeMirror editor (HTML or MD), live preview (iframe srcdoc / marked.js). Unsaved-changes modal on all navigation paths.
- **Tests** — 320 passing, 43 skipped, 2 pre-existing failures (unrelated).
- **Option B logged** — Full ingest rearchitecture (source/cleaned/assets_root split) logged in `docs/ideas/IDEAS.md` for future planning.

## State Right Now

- 577 posts in `kie-mark-proctor`, 576 clean, 31 with MD generated, 546 still need MD
- All 577 posts pre-date the enrichment pipeline — need bulk re-scan to apply YouTube/Gist/brush fixes
- `enriched/` folder is empty — no post has been enriched yet via new Scan pipeline
- `~/sparge-projects/` is clean — only `kie-mark-proctor` present

## Immediate Next Step

Write a bulk re-scan script: iterate all slugs in `~/sparge-projects/kie-mark-proctor/state.json`, call `POST http://localhost:9000/api/posts/{slug}/scan` for each. Start Sparge first (`python3 server.py` from `~/claude/sparge/`). This applies enrichment (YouTube thumbnails, Gist inlining, brush normalisation) to all 577 existing posts. Then bulk generate MD for the 546 without it.

## Open Questions / Blockers

- Should `enriched/` copies be committed to git or gitignored? Currently untracked.
- Should the full 1,801-post KIE archive (all authors) become one Sparge project?
- What is the right disposition for the legacy `scripts/` tools in the Jekyll repo — delete or keep?
- Option B (full ingest rearchitecture) — see `docs/ideas/IDEAS.md` for details.

## References

| Context | Where | Retrieve with |
|---|---|---|
| Design state | `docs/design-snapshots/2026-04-06-sparge-edit-experience-and-docs.md` | `cat` |
| Pipeline reference | `docs/pipeline.md` | `cat` |
| ADRs | `docs/adr/` | `ls` then `cat` as needed |
| Option B idea | `docs/ideas/IDEAS.md` | `cat` |
| Blog diary | `docs/blog/` | `ls` then `cat` as needed |
| Writing style guide | `~/claude-workspace/writing-styles/blog-technical.md` | `cat` |
| Garden submissions | `~/claude/knowledge-garden/submissions/` | `ls` |
| Previous handover | git history | `git show HEAD~1:HANDOVER.md` |

## Environment

- **Sparge repo:** `~/claude/sparge/` — GitHub: https://github.com/mdproctor/sparge
- **Run server:** `cd ~/claude/sparge && python3 server.py` (port 9000)
- **Run tests:** `cd ~/claude/sparge && python3 -m pytest tests/ -q`
- **Project data:** `~/sparge-projects/kie-mark-proctor/`
- **App config:** `~/.sparge/config.json` → points to `~/sparge-projects/`
- **Jekyll blog:** `~/mdproctor.github.io/` — separate repo, published content only
- `PERSONAL_WRITING_STYLES_PATH=~/claude-workspace/writing-styles` in `~/.claude/settings.json`
