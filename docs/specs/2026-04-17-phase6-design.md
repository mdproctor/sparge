# Phase 6: Complete JEP Elimination
**Date:** 2026-04-17
**Topic:** Port remaining 22 JEP bridge calls to native Java
**Status:** Approved, ready for implementation planning

---

## Overview

Phases 0–5 reduced JEP call count from 35 to 22. Phase 6 eliminates all remaining calls,
completing the Quarkus native migration. When done, `bridge.py` is dead code and JEP can
be removed from the runtime.

**Sequencing strategy:** Complexity-ascending. Easy wins first to build momentum and
confirm patterns; hardest modules (convert pipeline, ingest) tackled last when all
supporting infrastructure is in place.

---

## Epic & Issue Structure

One GitHub epic: *"Phase 6: Complete JEP elimination (22 calls)"*

| Issue | Group | JEP calls removed | Running total |
|---|---|---|---|
| 6a | config + search + static_resolve | 4 | 22 → 18 |
| 6b | consolidate + staging | 3–5 | 18 → 13–15 |
| 6c | convert pipeline | 6 | → 7–9 |
| 6d | ingest pipeline | 7 | → 0 |

Each issue: TDD cycle (tests first), Java implementation, retire Python tests to
`tests/python-legacy/`. All commits reference child issue (`Refs #N`); epic closes when
all children close.

---

## Section 1: Issue 6a — config + search + static_resolve

**JEP calls:** `config_get`, `config_post`, `search`, `static_resolve` (4 calls)

### ConfigResource
Replace JEP delegation with direct `SpargeConfig` reads/writes. `SpargeConfig` already
exists and manages the config JSON. The resource becomes a thin JAX-RS wrapper.

### SearchResource
Port `search()` from bridge.py to Java. Logic: filter `StateStore.getAll()` by title and/or
MD file content. `StateStore` already exists. No new class needed — logic lives in the resource.

### StaticResource
Replace JEP `static_resolve` call with direct `Path.resolve()` + path-traversal guard
(same guard as bridge.py: resolved path must start with `SERVE_ROOT`). Already partially
native — just remove the JEP fallback.

**New Java classes:** none — all wired into existing resources/`SpargeConfig`/`StateStore`.

**Tests:**
- Unit: `ConfigResourceTest`, `SearchResourceTest`, `StaticResourceTest`
- End-to-end happy path: `@QuarkusTest` hitting `/api/config`, `/api/search?q=&scope=title`,
  `/` static redirect

---

## Section 2: Issue 6b — consolidate + staging

**JEP calls:** `consolidate`, `post_staged_get`, `post_accept_staged`
(plus verify `post_stage`/`post_reject_staged` — likely already native from Phase 4/5)

### Consolidate.java
Port `scripts/consolidate.py`. Deduplicates and cleans up assets. Takes `assets_root` and
`cleaned_dir` from config; returns a result summary. Wired into `ConsolidateResource`.

### PostsResource — staging
- `post_staged_get`: read `<slug>.md.staged` from `MD_DIR`, return plain text
- `post_accept_staged`: call `StateStore.acceptStaged(slug)`, re-validate MD if validator
  available, return updated post state

**New Java classes:** `Consolidate.java`

**Tests:**
- Unit: `ConsolidateTest` (with temp dirs), `PostsResourceStagingTest`
- End-to-end happy path: `@QuarkusTest` for consolidate endpoint, staged accept flow

---

## Section 3: Issue 6c — convert pipeline

**JEP calls:** `post_generate_md`, `post_validate_md`, `post_save_md`, `post_html`,
`post_view`, `post_save_html` (6 calls)

### ConvertPost.java
Port `scripts/convert_post.py` — the HTML-to-Markdown converter. Uses jsoup for HTML
parsing; custom conversion logic walks the DOM and emits Markdown. This is the largest
single module in Phase 6. Strategy: port function-by-function, test each against known
input/output pairs derived from the existing pytest suite.

### MdValidator.java
Port `scripts/md_validator.py` — validates generated Markdown against a set of checks
(e.g. missing front-matter, broken image refs). Returns a list of `MdIssue` records
(check, level, detail).

### PostsResource — convert endpoints
Wire `generate-md`, `validate-md`, `save-md`, `view`, `save-html` to `ConvertPost` and
`MdValidator`. Remove all remaining JEP fallbacks in `PostsResource`.

**New Java classes:** `ConvertPost.java`, `MdValidator.java`, `MdIssue.java` (record)

**Library additions:** jsoup (if not already present in pom.xml)

**Tests:**
- Unit: `ConvertPostTest` (fixture HTML → expected MD), `MdValidatorTest`
- End-to-end happy path: `@QuarkusTest` generate-md → validate-md → save-md full flow on
  a real fixture post

---

## Section 4: Issue 6d — ingest pipeline

**JEP calls:** `ingest_detect`, `ingest_discover`, `ingest_preview`, `ingest_run`,
`ingest_cancel`, `ingest_status`, `project_ingest_run` (7 calls)

### IngestJob.java
Mutable job state record (replaces `_job` dict + `_job_lock` in bridge.py). Fields:
`running`, `done`, `total`, `current`, `errors`, `cancelled`, `log`. Thread-safe via
`synchronized` or `AtomicReference`.

### IngestService.java
Port `scripts/ingest.py`. HTTP scraping via `java.net.http.HttpClient`. Async background
worker via single-thread `ExecutorService`. Exposes: `detect(url)`, `discover(url, author)`,
`preview(url)`, `run(urls, author)` (starts background thread), `cancel()`, `status()`.
`@ApplicationScoped` singleton owning the `ExecutorService` and current `IngestJob`.

### IngestResource
Wire all 6 ingest endpoints + `project_ingest_run` (in `ProjectsResource`) to
`IngestService`. Remove all JEP delegation.

**New Java classes:** `IngestJob.java`, `IngestService.java`

**Tests:**
- Unit: `IngestJobTest` (thread safety), `IngestServiceTest` (mocked `HttpClient`)
- End-to-end happy path: `@QuarkusTest` for detect/status/cancel; full run flow with a
  mock HTTP server (WireMock or similar)

---

## TDD Approach

Consistent with Phases 1–5:
1. Write Java test first — assert the expected Java behaviour before implementation
2. Implement the Java class to make tests pass
3. Retire corresponding Python tests: move to `tests/python-legacy/` with a comment
   pointing to the Java replacement
4. Confirm full test suite still green before closing issue

**Emphasis on end-to-end coverage:**
- Every group has at least one `@QuarkusTest` covering the primary happy path
- End-to-end tests exercise the full HTTP → Java → StateStore/file → response chain
- No mocking of internal Java components (mock only external boundaries: HTTP clients,
  file system fixtures via temp dirs)

---

## Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| HTML parsing for ConvertPost | jsoup | Already likely in deps; battle-tested DOM API |
| HTTP client for IngestService | `java.net.http.HttpClient` | JDK 11+, no extra dep; sync API sufficient for non-reactive use |
| Async ingest worker | single-thread `ExecutorService` | Mirrors Python threading model; one job at a time |
| Ingest job thread safety | `synchronized` on `IngestJob` | Simple, matches existing Python lock pattern |
| MD validator output | `MdIssue` record (check, level, detail) | Matches bridge.py dict shape; easy Jackson serialisation |

---

## Completion Criteria

- All 22 JEP bridge calls removed from production resource classes
- `bridge.py` reduced to dead code (or deleted)
- JEP dependency removable from pom.xml
- 270 pytest + ≥180 JUnit tests passing (new tests added per issue), 0 failures
- Each issue closed with linked commits; epic closed
