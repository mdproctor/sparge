# Handover — 2026-04-06

**Head commit:** `e62b6a0` — docs: update CLAUDE.md with canonical paths, remove legacy orphan artifacts
**GitHub:** https://github.com/mdproctor/sparge (private)
**Previous handover:** `git show HEAD~1:HANDOVER.md`

## What Changed This Session

- **Codebase consolidated** — All work moved from `blog-migrator/` (Jekyll repo) into `~/claude/sparge/`. `blog-migrator/` deleted from Jekyll repo. Two codebases are now one.
- **`asset_store.py` + `consolidate.py` integrated (Option A)** — Ported from original sparge ancestor. `POST /api/consolidate` endpoint + UI button. 86 tests ported (28 skip until Option B).
- **6 new consolidate endpoint tests** — 326 total passing.
- **Path audit** — All pipeline paths confirmed canonical, consistent, no duplicates. Legacy `.issues.json` removed. Orphaned enriched file removed.
- **CLAUDE.md** — Now documents canonical paths table, "do not work elsewhere" rule, and full state of KIE archive.
- **Design snapshot** — `2026-04-06-canonical-paths-and-confusion.md` documents the two-codebase confusion root cause for future Claude sessions.

## The Two-Codebase Confusion — What Happened

This is important context for any future Claude session:

1. `~/claude/sparge` was the original proof-of-concept (8 commits, 2026-04-04)
2. Work moved to `blog-migrator/` in the Jekyll repo but HANDOVER.md was not updated
3. Subsequent Claude sessions read HANDOVER.md → `python3 blog-migrator/server.py` → worked in the wrong place
4. Two days of work (CodeMirror, edit mode, enrichment, storage) accumulated in the wrong codebase
5. **Resolution:** `blog-migrator/` deleted. `~/claude/sparge/` is the only location.

**Do not work anywhere else. The CLAUDE.md rule is not optional.**

## State Right Now

- **Application:** `~/claude/sparge/` — 326 tests passing
- **KIE archive posts:** 577 HTML in `~/mdproctor.github.io/legacy/posts/mark-proctor/` (already enriched by pre-Sparge scripts — YouTube thumbnails on ~7, `language-` classes on 89, `brush:` eliminated)
- **MD output:** 31 files in `~/mdproctor.github.io/mark-proctor/` (546 still need generation)
- **Enriched folder:** Empty — Sparge's enrichment pipeline has never been bulk-run
- **Sparge has scanned 0 of 577 posts** — state.json posts all have empty `html.issues` because they haven't been scanned, NOT because they're clean

## Immediate Next Step

**Bulk re-scan all 577 posts.** Write a script iterating slugs from `~/sparge-projects/kie-mark-proctor/state.json`, calling `POST http://localhost:9000/api/posts/{slug}/scan` for each. Start server first: `cd ~/claude/sparge && python3 server.py`. Most posts should come back clean (legacy scripts already enriched the HTML). Then bulk generate MD for the 546 posts that have none.

## Open Questions / Blockers

- Should `enriched/` copies be committed to git or gitignored? Currently untracked.
- Should the full 1,801-post KIE archive (all authors) become one Sparge project?
- Legacy `scripts/` in Jekyll repo (`~/mdproctor.github.io/scripts/`) — delete or keep for reference?
- Option B (full ingest rearchitecture) — see `docs/ideas/IDEAS.md`

## References

| Context | Where | Retrieve with |
|---|---|---|
| Canonical paths + confusion history | `docs/design-snapshots/2026-04-06-canonical-paths-and-confusion.md` | `cat` |
| Pipeline reference | `docs/pipeline.md` | `cat` |
| ADRs | `docs/adr/` | `ls` then `cat` as needed |
| Option B idea | `docs/ideas/IDEAS.md` | `cat` |
| Blog diary | `docs/blog/` | `ls` then `cat` as needed |
| Writing style guide | `~/claude-workspace/writing-styles/blog-technical.md` | `cat` |
| Previous handover | git history | `git show HEAD~1:HANDOVER.md` |

## Environment

- **Sparge repo:** `~/claude/sparge/` — GitHub: https://github.com/mdproctor/sparge
- **Run server:** `cd ~/claude/sparge && python3 server.py` (port 9000)
- **Run tests:** `cd ~/claude/sparge && python3 -m pytest tests/ -q`
- **Project data:** `~/sparge-projects/kie-mark-proctor/`
- **App config:** `~/.sparge/config.json` → points to `~/sparge-projects/`
- **Jekyll blog (content only):** `~/mdproctor.github.io/` — separate repo, no app code
- `PERSONAL_WRITING_STYLES_PATH=~/claude-workspace/writing-styles` in `~/.claude/settings.json`
