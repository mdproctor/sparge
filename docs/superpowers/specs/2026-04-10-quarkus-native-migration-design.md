# Sparge — Quarkus Native Migration Design
**Date:** 2026-04-10
**Topic:** Incremental migration from Python + Electron to Quarkus Native + Electron
**Status:** Approved, ready for implementation planning

---

## Overview

Migrate Sparge's Python HTTP server incrementally to Quarkus, culminating in a Quarkus Native
binary bundled inside the Electron app. The migration is also a public technical narrative —
blog entries and knowledge-garden captures are first-class outputs alongside the code,
promoting the Quarkus Native ecosystem.

**Motivation:** Quarkus ecosystem promotion, performance gains (startup, memory, throughput),
and a documented how-to for replacing Python servers with Quarkus Native.

---

## Approach: Sequential module-by-module (Approach 1)

A single sequential track: stand up Quarkus + JEP bridge, then port Python modules one at a
time in dependency order. Each port is a discrete blog chapter. Modules may be grouped into
batches where it makes editorial sense.

---

## Section 1: Project Structure

The Quarkus server lives as `server/` inside the existing `sparge` repo. Single git history,
visible progress per commit.

```
sparge/
  server/                  ← new Quarkus Maven project
    src/main/java/
    src/test/java/
    src/jmh/java/          ← JMH benchmarks
    pom.xml
  scripts/                 ← Python (shrinks over time)
  tests/                   ← pytest (shrinks over time)
  tests/python-legacy/     ← holding area for retired pytest tests
  ui/                      ← unchanged throughout migration
  main.js, preload.js
  python-server.js         ← retired at end of Phase 0
  java-server.js           ← new: spawns JVM server (then native binary)
```

`main.js` uses a config flag to select `python-server.js` vs `java-server.js` during Phase 0
development, allowing instant fallback.

---

## Section 2: Phase 0 — JEP Bridge & Quarkus Server

**Goal:** Electron talks to Quarkus; Python runs in-process via JEP. No modules ported yet.

**Bridge choice: JEP (Java Embedded Python)**
- Embeds CPython via JNI — in-process, zero per-call subprocess overhead
- Links against `resources/python/mac-arm64/lib/libpython3.12.dylib` (already bundled, shared lib confirmed present)
- Works on standard JVM; JNI incompatibility with native image is not a concern until the final phase (Python is gone by then)
- Alternatives evaluated and rejected: Jython (Python 2 only), subprocess per-call (100–200ms overhead per call; unacceptable for chained operations like scan-html which calls 4 functions), GraalPy (not in installed GraalVM distribution), Py4J (sidecar overhead)

**Steps:**

1. **Quarkus project** — `server/` with Quarkus REST (JAX-RS), Jackson, JEP dependency.
   `java.library.path` configured to `../resources/python/mac-arm64/lib/`.

2. **`PythonBridge` singleton** — `@ApplicationScoped` bean owning a JEP `SharedInterpreter`.
   Initialises once at startup, adds `../scripts/` to `sys.path`. All Python calls go through here.

3. **All 40+ endpoints as JAX-RS resources** — each method calls `PythonBridge` which delegates
   to the equivalent Python function via JEP. No logic in Java yet — pure HTTP translation.

4. **`java-server.js`** — mirrors `python-server.js` state machine (idle → starting → healthy →
   crashed → restarting → fatal) but spawns `java -jar server/target/sparge-server.jar`.
   Same readiness polling on `/api/config`.

5. **`main.js` toggle** — env var or config flag selects server manager. Both coexist during
   Phase 0 development.

**Done when:** all existing pytest integration tests pass against the Quarkus server.

**Blog entry:** "Replacing a Python HTTP server with Quarkus + JEP — wiring CPython into the
JVM using a bundled runtime."

---

## Section 3: Module Porting Order & Per-Module Workflow

**Porting order — dependencies first, complex last:**

| Batch | Modules | Java libraries | Blog angle |
|-------|---------|---------------|------------|
| 1 | `sparge_home.py`, `config.py` | Quarkus Config, Jackson | Path resolution — establishes Java patterns |
| 2 | `state.py` | Jackson `ObjectMapper` (streaming API) | JSON state machine — first real data layer |
| 3 | `html_utils.py`, `fix_code_blocks.py` | Jsoup | DOM manipulation — BeautifulSoup → Jsoup |
| 4 | `scan_html.py`, `scan_assets.py` | Jsoup CSS selectors | 9 issue types, rich test suite, good milestone |
| 5 | `enrich.py` | Jsoup + Java HTTP client + virtual threads | YouTube/Gist enrichment — async IO story |
| 6 | `asset_store.py`, `consolidate.py` | NIO, Jackson | File hashing, deduplication |
| 7 | `md_validator.py`, `convert_post.py` | Flexmark or CommonMark | The hardest port — html2text replacement |
| 8 | `ingest.py` | Java HTTP client, Jsoup, virtual threads | Platform detection, asset localisation — final boss |

Batches are flexible — split or merge based on actual complexity encountered.

**Per-module workflow (repeated for every port):**

```
1. Write JUnit test calling through JEP → Python   (contract established in Java)
2. Port module to Java
3. JUnit test now calls Java directly              (JEP call removed, same assertions)
4. Move pytest tests → tests/python-legacy/
5. Delete JEP delegate for that module
6. Run full test suite — green
```

JEP call count is a public metric published per blog entry, dropping from ~40 to zero.

---

## Section 4: Final Phase — Drop Python, Compile Native

When JEP call count reaches zero:

1. **Remove JEP dependency** from `pom.xml` — compile error if any Python calls remain (safety net).
2. **Remove `resources/python/`** — CPython bundle gone; significant Electron package size reduction.
3. **Remove `python-server.js`** and `main.js` toggle.
4. **`mvn package -Pnative`** — Quarkus Native binary (`sparge-server`). Expect native image
   issues here: reflection config, resource inclusion, JNI cleanup. Each issue is a blog note.
5. **Update `java-server.js`** — switch from `java -jar sparge-server.jar` to `./sparge-server`.
   Startup time drops from ~2s (JVM warmup) to ~50ms (native).
6. **Update `electron-builder` config** — `extraResources` now includes native binary per
   platform instead of the Python bundle.
7. **GitHub Actions matrix build** — native binary per platform (mac-arm64, mac-x64, win-x64,
   linux-x64). Cross-compilation is limited; matrix build is the correct approach.

**Done when:** `npm run test:e2e` passes with the native binary. No Python, no JVM, no JEP.

**Blog entry:** "From JVM to native — compiling a Quarkus app that started as a Python server."

---

## Section 5: Test Strategy

**Hybrid approach:**

- **Default (B):** Port module → write JUnit → move pytest to holding area → JUnit is live.
- **On demand (A):** Re-activate pytest from holding area to cross-check a specific port.
  Run both suites, verify agreement, re-retire pytest tests.

**Structure:**

```
server/src/test/java/     ← JUnit (grows)
tests/                    ← pytest (shrinks)
tests/python-legacy/      ← holding area (never runs in CI)
```

`tests/python-legacy/` excluded from default pytest run via `pytest.ini` (`--ignore`).
Reactivating a batch: `pytest tests/python-legacy/test_scan_html.py` directly.

**JUnit test pattern:**
- Written in two stages: first calls through JEP (proves contract), then implementation swaps
  to Java with no assertion changes. The test *is* the spec.
- Integration tests (requiring a running server) stay as pytest until the final phase, then
  become `@QuarkusTest` JUnit tests.

**CI:**
- Python pytest runs on `tests/` (shrinking). JUnit runs on `server/`. Both required green.
- `tests/python-legacy/` never runs in CI.

**Final state:** zero pytest in `tests/`, zero in `tests/python-legacy/`, all coverage in JUnit.

---

## Section 6: Blog & Documentation Cadence

Code and blog are co-equal outputs. Each batch produces one blog entry.

**Entry structure per batch:**
1. What we're porting and why this batch is interesting
2. Java library choices made (and alternatives rejected)
3. Surprising gotchas (JEP behaviour, Quarkus quirks, library gaps)
4. JEP call count before → after
5. Test approach — JUnit vs the pytest tests they replaced

**Planned entries:**

| Entry | Topic |
|-------|-------|
| 0 | Why: Quarkus Native as a Python server replacement |
| 1 | Bridge evaluation — JEP vs subprocess vs GraalPy, why JEP won |
| 2 | Phase 0 — Wiring JEP + Quarkus, replacing the Python HTTP server |
| 3 | Batch 1–2 — Config + state; establishing Java patterns |
| 4 | Batch 3–4 — Jsoup as BeautifulSoup; porting the scan pipeline |
| 5 | Batch 5–6 — Enrichment, assets, IO |
| 6 | Batch 7–8 — html2text → Flexmark; the hardest port |
| 7 | Final — Native compilation; what broke, what surprised us |

**Garden & forage discipline:** every non-obvious technique, gotcha, or undocumented behaviour
captured in the knowledge garden during the session it's found — feeds directly into blog entries.

**Design snapshots** at the end of each batch freeze the current state for reference and
as evidence for blog entries.

---

## Section 7: Benchmarking & Performance

**Three-way comparison at each phase:**

| Metric | Python | Quarkus JVM | Quarkus Native |
|--------|--------|-------------|----------------|
| Startup time | `time python3 server.py` | `time java -jar` | `time ./sparge-server` |
| Idle RSS memory | `psutil` / `ps` | JVM heap + metaspace | Native RSS |
| Per-operation latency | `time` on each API call | same | same |
| Bulk throughput | scan all 577 posts | same | same |

Benchmarks run at: Phase 0 baseline, after each batch, final native build.
Published as a running table in each blog entry.

**Tooling:**
- **JMH** (`server/src/jmh/java/`) — per-method micro-benchmarks (e.g. `scanHtml()` throughput)
- **k6 or Gatling** — HTTP-level throughput on the full server
- **`/usr/bin/time -l`** — RSS memory on startup

**High-throughput coding principles for the Java port:**

- **Virtual threads** (Project Loom, Java 21+, Quarkus native support) — all I/O-bound
  operations: ingest, asset downloads, enrichment HTTP calls
- **Single DOM parse per request** — Jsoup parses once; scan + enrich + fix all operate on
  the same `Document`, passed through
- **Compiled CSS selectors** — `scan_html` currently re-parses selector strings per call;
  Java port caches `Evaluator` instances as `static final` fields
- **Streaming Jackson** — `state.json` reads/writes use `JsonParser`/`JsonGenerator` (not
  `ObjectMapper.readTree()`) for large state files
- **Parallel bulk ops** — scan-all-577 uses virtual thread pool via `ExecutorService`
- **Zero-copy file I/O** — `Files.writeString()` / `Files.readString()` with explicit charset;
  no intermediate `String` copies for large HTML files

**Blog angle:** "We didn't just port — we measured. Here's what Quarkus Native actually buys
you over Python for a real workload."

---

## Open Questions

- **Maven vs Gradle** for `server/` — Quarkus defaults to Maven; no strong reason to deviate.
- **Java version** — Java 21+ required for virtual threads (Project Loom). Confirm GraalVM
  version supports Java 21 for native compilation.
- **Cross-platform JEP** — `libpython3.12.dylib` confirmed on mac-arm64. Windows and Linux
  equivalents (`libpython3.12.so`, `python312.dll`) need verification when those platform
  builds are tackled.
- **`ENRICHED_DIR` hardcoded fallback** in `server.py` — **must be cleaned up before Phase 0
  begins** so the Java port doesn't inherit the hardcoded `kie-mark-proctor` project-ID.
  This is a pre-migration prerequisite, not a deferred item.
