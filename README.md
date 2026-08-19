# Sparge

Desktop blog migration tool. Ingests HTML posts from live blog URLs, enriches them (YouTube thumbnails, Gist inlining, code block normalisation), and converts to Jekyll Markdown for review and publishing.

Built for migrating the [KIE/Drools blog archive](https://blog.kie.org) — 577 posts spanning 2006–2022 — but designed to work with any HTML blog source.

## How It Works

Three-stage immutable pipeline — original HTML is never modified:

1. **Ingest** — fetch HTML posts from source URLs, create project state
2. **Scan / Enrich** — apply HTML fixes (broken links, missing images, embed expansion), write enriched copies
3. **Generate Markdown** — convert enriched HTML to Jekyll-compatible Markdown with frontmatter

Each stage writes forward only. Original HTML stays intact for audit and re-processing.

## Stack

| Layer | Technology |
|---|---|
| Desktop shell | Electron 33 |
| Server | Quarkus 3.34 (Java 21, uber-jar) |
| UI | Single-file HTML/CSS/JS — no build step |
| Tests | JUnit (346), pytest (288), Jest (63), Playwright E2E (19) |

The server is fully native Java — no Python runtime required in the distributed app.

## Running

```bash
npm start              # Electron app (starts embedded Java server)
```

For development without Electron:

```bash
cd server
mvn package -DskipTests
java -Dquarkus.http.port=9000 -jar target/sparge-server-runner.jar
# then open http://localhost:9000/ui/ in a browser
```

## Testing

```bash
# Java (Quarkus)
cd server && mvn test

# Python (enrichment logic)
python3 -m pytest tests/ -q --ignore=tests/python-legacy

# JavaScript (Electron)
npm run test:unit          # Jest unit tests
npm run test:integration   # JavaServer process tests
npm run test:e2e           # Playwright end-to-end
```

## Project Structure

```
main.js, preload.js       Electron entry point
java-server.js            JVM process manager (state machine)
server-factory.js         Server construction with Electron context
server/                   Quarkus 3.34 Maven project
ui/                       Single-file frontend (index.html, projects.html)
scripts/                  Core pipeline logic (ingest, scan, enrich, consolidate)
tests/                    pytest test suite
electron-tests/           Jest + Playwright tests
docs/adr/                 Architecture decision records
docs/pipeline.md          Pipeline stage reference
```

## Distribution

Built with electron-builder for macOS (DMG), Windows (NSIS), and Linux (AppImage). Auto-update via GitHub Releases.
