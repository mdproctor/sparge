# ADR 0005 — Quarkus uber-jar for Electron packaging

**Date:** 2026-04-21  
**Status:** Accepted

## Context

When packaging the Sparge Electron app, the Quarkus server must be bundled as a binary artifact. Quarkus offers two primary JVM packaging modes:

- **Fast-jar** (default): produces `quarkus-app/quarkus-run.jar` plus a `lib/` directory and `quarkus/` metadata tree (~20 MB total across multiple files)
- **Uber-jar**: produces a single self-contained `sparge-server-runner.jar` (~19 MB, one file)

## Decision

Use **uber-jar** as the default build output, configured via `application.properties`:

```properties
quarkus.package.jar.type=uber-jar
quarkus.package.output-name=sparge-server
```

This produces `server/target/sparge-server-runner.jar` on every `mvn package`.

## Rationale

| Factor | Fast-jar | Uber-jar |
|--------|----------|----------|
| Size | ~20 MB (directory tree) | ~19 MB (single file) |
| Startup time | ~1.02s | ~1.03s |
| `extraResources` config | Directory glob, fragile | Single file entry, simple |
| Dev/prod JAR consistency | Different paths | Same JAR, same path pattern |
| Electron-builder support | Needs `from: dir/**` | `from: file.jar` |

The startup time difference (10ms) is negligible. The packaging simplicity difference is significant: a single file entry in `extraResources` is unambiguous, version-agnostic (fixed output name), and trivially verified.

## Consequences

- `mvn package` (default, no flags needed) produces the uber-jar
- `server/target/sparge-server-runner.jar` is the canonical JAR for both dev and packaged Electron
- `package.json` `extraResources` includes one entry: `server/target/sparge-server-runner.jar → sparge-server-runner.jar`
- `getJarPath(isPackaged=false)` → `server/target/sparge-server-runner.jar`
- `getJarPath(isPackaged=true, resourcesPath)` → `resourcesPath/sparge-server-runner.jar`
- The `quarkus-app/` fast-jar directory is no longer used and can be ignored
