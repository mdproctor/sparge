# CLAUDE.md

## Project Type

**Type:** custom

## Overview

Sparge is a blog migration tool — ingests HTML posts from live blog URLs, enriches them (YouTube thumbnails, Gist inlining, code class normalisation), and converts them to Jekyll Markdown for review and publishing.

**This is the single canonical codebase.** It lives at `~/claude/sparge/`. Do not work in any other location. The Jekyll publishing repo (`~/mdproctor.github.io/`) is separate and contains only published content — no application code.

## Running the server

```bash
cd ~/claude/sparge
python3 server.py             # Python server, browser mode (port 9000)
npm start                     # Electron app — Python server by default
SPARGE_SERVER=java npm start  # Electron app — Quarkus JEP server
```

Browser mode (Python) serves on port 9000. Electron mode allocates a dynamic port. Project data lives in `~/sparge-projects/` (configured via `~/.sparge/config.json`).

**Quarkus server (Phase 0 — delegates all calls to Python via JEP):**
```bash
cd ~/claude/sparge/server
mvn package -DskipTests    # build jar → target/quarkus-app/quarkus-run.jar
# Runtime env vars required:
export PYTHONHOME=$HOME/claude/sparge/resources/python/mac-arm64
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
java -Djava.library.path=$HOME/claude/sparge/resources/python/mac-arm64/lib/python3.12/site-packages/jep \
     -Dquarkus.http.port=9000 \
     -jar target/quarkus-app/quarkus-run.jar
```
First-time setup: `resources/python/mac-arm64/bin/pip install jep lxml`

## Testing

```bash
cd ~/claude/sparge
python3 -m pytest tests/ -q --ignore=tests/python-legacy
```

270 passing, 427 skipped (integration tests skip without running server), 0 pre-existing failures. (`tests/python-legacy/` holds retired Python tests for ported modules — not run in CI.)

**Java tests (Quarkus):**
```bash
cd ~/claude/sparge/server && mvn test
```

180 passing (unit + integration), 0 pre-existing failures. `@QuarkusTest` endpoint tests require JEP — skip in CI.

**JS tests (Electron):**
```bash
npm run test:unit        # 38 passing — Jest unit tests (mocked)
npm run test:integration # 4 passing — real Python process tests
npm run test:e2e         # 4 passing — Playwright full app tests
```
E2E tests require `resources/python/` (run `node scripts/fetch-python.js` once) and the Electron binary (run `node node_modules/electron/install.js` once).

## Key directories — this repo

- `scripts/` — core logic (ingest, scan, enrich, state, config, asset_store, consolidate)
- `scripts/bridge.py` — JEP bridge: all handler logic exposed as JSON-returning functions for Quarkus
- `server/` — Quarkus 3.34 Maven project (Phase 0: delegates to Python via JEP)
- `ui/` — single-file frontend (index.html, projects.html, browse-utils.js)
- `electron-tests/` — Jest unit/integration + Playwright E2E tests for the Electron wrapper
- `main.js`, `preload.js`, `python-server.js` — Electron entry point and Python process manager
- `java-server.js` — Electron JVM process manager (mirrors python-server.js, used when `SPARGE_SERVER=java`)
- `tests/` — pytest test suite
- `docs/adr/` — architecture decision records
- `docs/_posts/` — development diary entries (Jekyll blog posts)
- `docs/pipeline.md` — full pipeline reference (stages, checks, fixes)
- `docs/ideas/IDEAS.md` — parked ideas (including Option B ingest rearchitecture)
- `DESIGN.md` — living design document (captures snapshots + decisions)

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

**Automatic behaviours (Claude follows these at all times in this project):**
- **Before implementation begins** — when the user says "implement", "start coding",
  "execute the plan", "let's build", or similar: check if an active issue or epic
  exists. If not, run issue-workflow Phase 1 to create one **before writing any code**.
- **Before writing any code** — check if an issue exists for what's about to be
  implemented. If not, draft one and assess epic placement (issue-workflow Phase 2)
  before starting. Also check if the work spans multiple concerns.
- **Before any commit** — run issue-workflow Phase 3 (via git-commit) to confirm
  issue linkage and check for split candidates. This is a fallback — the issue
  should already exist from before implementation began.
- **All commits should reference an issue** — `Refs #N` (ongoing) or `Closes #N` (done).
  If the user explicitly says to skip ("commit as is", "no issue"), ask once to confirm
  before proceeding — it must be a deliberate choice, not a default.
