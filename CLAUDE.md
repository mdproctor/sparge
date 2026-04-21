# CLAUDE.md

## Project Type

**Type:** custom

## Overview

Sparge is a blog migration tool — ingests HTML posts from live blog URLs, enriches them (YouTube thumbnails, Gist inlining, code class normalisation), and converts them to Jekyll Markdown for review and publishing.

**This is the single canonical codebase.** It lives at `~/claude/sparge/`. Do not work in any other location. The Jekyll publishing repo (`~/mdproctor.github.io/`) is separate and contains only published content — no application code.

## Running the server

```bash
cd ~/claude/sparge
python3 server.py   # Python server, browser mode (port 9000)
npm start           # Electron app — Java server
```

Browser mode (Python) serves on port 9000. Electron mode allocates a dynamic port. Project data lives in `~/sparge-projects/` (configured via `~/.sparge/config.json`).

**Quarkus server (fully native Java — no Python/JEP required):**
```bash
cd ~/claude/sparge/server
mvn package -DskipTests    # build uber-jar → target/sparge-server-runner.jar
java -Dquarkus.http.port=9000 \
     -jar target/sparge-server-runner.jar
```

## Testing

```bash
cd ~/claude/sparge
python3 -m pytest tests/ -q --ignore=tests/python-legacy
```

288 passing, 427 skipped (integration tests skip without running server), 0 pre-existing failures. (`tests/python-legacy/` holds retired Python tests for ported modules — not run in CI.)

**Java tests (Quarkus):**
```bash
cd ~/claude/sparge/server && mvn test
```

346 passing (unit + integration), 0 pre-existing failures. `@QuarkusTest` endpoint tests skip via `@EnabledIf("kieArchivePresent")` when the KIE archive is absent.

**JS tests (Electron):**
```bash
npm run test:unit        # 73 passing — Jest unit tests (mocked)
npm run test:integration # 4 passing — real JavaServer process tests
npm run test:e2e         # 19 passing (5 app + 4 delete + 10 refine)
```
E2E tests require the Electron binary (run `node node_modules/electron/install.js` once).

## Key directories — this repo

- `scripts/` — core logic (ingest, scan, enrich, state, config, asset_store, consolidate)
- `scripts/bridge.py` — dead code (JEP bridge retired; all endpoints ported to native Java)
- `server/` — Quarkus 3.34 Maven project (fully native Java — no Python/JEP dependency)
- `ui/` — single-file frontend (index.html, projects.html, browse-utils.js)
- `electron-tests/` — Jest unit/integration + Playwright E2E tests for the Electron wrapper
- `main.js`, `preload.js` — Electron entry point
- `server-factory.js` — constructs the JavaServer with Electron context
- `java-server.js` — Electron JVM process manager
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
