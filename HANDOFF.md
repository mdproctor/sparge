# Handover — 2026-04-15

**Head commit:** `a359e00` — docs: session wrap — gitignore, CLAUDE.md, blog entry for Phase 0
**Branch:** `epic-quarkus-migration` (not yet merged to main)
**GitHub:** mdproctor/sparge, issue #51 open (epic: Quarkus migration)

## What changed this session

**Phase 0 of the Quarkus migration is complete.** Full JEP bridge from Quarkus to Python:

- `scripts/bridge.py` — 35 bridge functions, all Python handler logic as JSON-returning functions
- `server/` — Quarkus 3.34.3 Maven project, all 35 JAX-RS endpoints delegating via JEP
- `java-server.js` — Electron JVM process manager (mirrors python-server.js state machine)
- `main.js` — `SPARGE_SERVER=java` toggle selects Java server in Electron
- `PythonBridge` — dedicated daemon thread owning the SharedInterpreter (critical: synchronized is wrong)

**Key runtime requirements** (not obvious from code):
- `PYTHONHOME=$HOME/claude/sparge/resources/python/mac-arm64` — required for CPython stdlib
- `DYLD_LIBRARY_PATH` — for libpython3.12.dylib
- `java.library.path` — for libjep.jnilib
- `lxml` installed in bundled Python: `resources/python/mac-arm64/bin/pip install lxml`

**Test state:** 473 passing, 0 failing (baseline preserved). All API tests pass against Quarkus.
Playwright UI tests (hardcoded port 9000) reveal pre-existing JS bugs — not Quarkus regressions.

**Garden:** 7 JEP entries submitted — Hortora/garden#56 (new `jep/` domain).

## State right now

- Branch `epic-quarkus-migration` — all Phase 0 work committed, needs merge to main
- Issue #51: open (epic covers all phases — merge branch now; close #51 when all phases done, or retitle to Phase 1+)
- Tests: 473 passing, 0 failing
- Quarkus jar: gitignored — rebuild with `cd server && mvn package -DskipTests`
- Blog: `docs/_posts/2026-04-15-mdp01-quarkus-phase0.md` written and committed

## Immediate next steps

1. **Merge the epic branch** — `git checkout main && git merge epic-quarkus-migration`
2. **Phase 1 plan** — port `sparge_home.py` + `config.py` to Java (Quarkus Config + Jackson). Use `superpowers:writing-plans` before any code. Pattern: write JUnit test via JEP first, swap to Java, retire pytest to `tests/python-legacy/`.
3. **Pre-existing Playwright JS bugs** — save button stays disabled after first save; dirty-detection edge case. Fix before Phase 1 if touching the UI anyway.

## References

| Context | Where |
|---|---|
| Quarkus migration design spec | `docs/superpowers/specs/2026-04-10-quarkus-native-migration-design.md` |
| Phase 0 implementation plan | `docs/superpowers/plans/2026-04-14-quarkus-phase0.md` |
| Living design doc | `DESIGN.md` |
| Blog entry (Phase 0) | `docs/_posts/2026-04-15-mdp01-quarkus-phase0.md` |
