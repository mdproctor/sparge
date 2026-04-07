# CLAUDE.md

## Project Type

**Type:** custom

## Overview

Sparge is a blog migration tool — ingests HTML posts from live blog URLs, enriches them (YouTube thumbnails, Gist inlining, code class normalisation), and converts them to Jekyll Markdown for review and publishing.

**This is the single canonical codebase.** It lives at `~/claude/sparge/`. Do not work in any other location. The Jekyll publishing repo (`~/mdproctor.github.io/`) is separate and contains only published content — no application code.

## Running the server

```bash
cd ~/claude/sparge
python3 server.py
```

Serves on port 9000. Project data lives in `~/sparge-projects/` (configured via `~/.sparge/config.json`).

## Testing

```bash
cd ~/claude/sparge
python3 -m pytest tests/ -q
```

326 passing, 43 skipped (integration tests skip without running server), 2 pre-existing failures.

## Key directories — this repo

- `scripts/` — core logic (ingest, scan, enrich, state, config, asset_store, consolidate)
- `ui/` — single-file frontend (index.html, projects.html)
- `tests/` — pytest test suite
- `docs/adr/` — architecture decision records
- `docs/design-snapshots/` — immutable design state snapshots
- `docs/pipeline.md` — full pipeline reference (stages, checks, fixes)
- `docs/blog/` — development diary entries
- `docs/ideas/IDEAS.md` — parked ideas (including Option B ingest rearchitecture)

## KIE archive project — canonical file locations

The active project (`kie-mark-proctor`) points into the Jekyll publishing repo for its content:

| What | Absolute path | Notes |
|---|---|---|
| HTML source (original) | `/Users/mdproctor/mdproctor.github.io/legacy/posts/mark-proctor/` | 577 files — NEVER modify these |
| Assets (images etc.) | `/Users/mdproctor/mdproctor.github.io/legacy/assets/` | 2,983 files |
| MD output | `/Users/mdproctor/mdproctor.github.io/mark-proctor/` | 31 files generated so far |
| Enriched HTML (per-scan) | `~/sparge-projects/kie-mark-proctor/enriched/` | Written by Scan; empty until bulk scan runs |
| Project state | `~/sparge-projects/kie-mark-proctor/state.json` | 577 posts tracked |
| Project config | `~/sparge-projects/kie-mark-proctor/config.json` | serve_root, posts_dir, etc. |

## Runtime data locations

- `~/sparge-projects/` — all project data (configured via `~/.sparge/config.json`)
- `~/.sparge/config.json` — points to `~/sparge-projects/`
- `~/claude/sparge/` — application code (this repo)
- GitHub: https://github.com/mdproctor/sparge (private)

## State of the KIE archive

- 577 HTML posts ingested and tracked in state.json
- HTML files already enriched by pre-Sparge scripts (YouTube thumbnails on ~7 posts, language- classes on 89 posts)
- 0 posts enriched by Sparge's own enrichment pipeline (bulk scan not yet run)
- 31 MD files generated (by old scripts, pre-Sparge)
- 546 posts still need MD generation

## What NOT to do

- Do not work in `~/mdproctor.github.io/blog-migrator/` — it no longer exists
- Do not modify HTML files in `legacy/posts/mark-proctor/` — these are the source of truth
- Do not confuse `~/sparge-projects/` (runtime data) with `~/claude/sparge/` (application code)

## Work Tracking

**Issue tracking:** enabled
**GitHub repo:** mdproctor/sparge
**Changelog:** GitHub Releases (run `gh release create --generate-notes` at milestones)

**Automatic behaviours (Claude follows these when this section is present):**
- Before starting any significant task, check if it spans multiple concerns.
  If it does, help break it into separate issues before beginning work.
- When staging changes before a commit, check if they span multiple issues.
  If they do, suggest splitting the commit using `git add -p`.
