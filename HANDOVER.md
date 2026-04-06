# Handover — 2026-04-06

**Head commit:** `57470f5` — docs: add design snapshot 2026-04-06-sparge-edit-experience-and-docs
**Previous handover:** `git show HEAD~1:HANDOVER.md` | diff: `git diff HEAD~1 HEAD -- HANDOVER.md`

## What Changed This Session

- **HTML prettify** — BeautifulSoup `prettify()` added to `GET /api/posts/{slug}/html` for editor view. Fixed lxml double-encoding bug (was garbling em dashes, curly quotes in all 577 posts); switched to `html.parser`. 19 prettify tests + runtime garbling detection guard added.
- **Sparge blog series** — 5 retrospective entries written to `docs/blog/`, each with Playwright-generated UI screenshots (thumbnails + full-size). `typora-root-url: ../..` front matter makes images work in both Typora and Jekyll.
- **Writing style guide** — updated with Claude intro rule ("we" can't appear before Claude is named) and "we" variation table. Garden skill Step 5 updated to require full template in confirmation draft.
- **Garden** — 3 submissions: BeautifulSoup lxml encoding gotcha, corruption signature check technique, `typora-root-url` technique.
- **Design snapshot** — `2026-04-06-sparge-edit-experience-and-docs.md` supersedes previous.
- **Tests** — 261 passing (up from 244).

## State Right Now

- 577 posts in `kie-mark-proctor`, 576 clean, 31 with MD, 546 still need MD generated
- All 577 posts pre-date enrichment pipeline — need bulk re-scan to apply YouTube/Gist/brush fixes
- `enriched/` folder empty — no post has been enriched yet via new Scan pipeline
- `projects/` stale dirs still present (delete-me-50f616, test-project-5652be — safe to delete)

## Immediate Next Step

Write a bulk re-scan script: for each slug in `~/sparge-projects/kie-mark-proctor/state.json`, call `POST http://localhost:9000/api/posts/{slug}/scan`. Start Sparge first (`python3 server.py`). This applies enrichment to all 577 existing posts. Then bulk generate MD for the 546 that don't have it.

## Open Questions / Blockers

*Unchanged — `git show HEAD~1:HANDOVER.md`*

## References

| Context | Where | Retrieve with |
|---|---|---|
| Design state | `docs/design-snapshots/2026-04-06-sparge-edit-experience-and-docs.md` | `cat` |
| Pipeline reference | `docs/pipeline.md` | `cat` |
| Blog series | `docs/blog/` | `ls` then `cat` as needed |
| Writing style guide | `~/claude-workspace/writing-styles/blog-technical.md` | `cat` |
| Garden submissions (pending merge) | `~/claude/knowledge-garden/submissions/` | `ls` |
| Previous handover | git history | `git show HEAD~1:HANDOVER.md` |

## Environment

- Sparge server: `python3 server.py` (port 9000)
- Project data: `~/sparge-projects/kie-mark-proctor/`
- `PERSONAL_WRITING_STYLES_PATH=~/claude-workspace/writing-styles` in `~/.claude/settings.json`
