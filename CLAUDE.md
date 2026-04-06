# CLAUDE.md

## Project Type

**Type:** custom

## Overview

Sparge is a blog migration tool — ingests HTML posts from live blog URLs, enriches them (YouTube thumbnails, Gist inlining, code class normalisation), and converts them to Jekyll Markdown for review and publishing.

## Running the server

```bash
python3 server.py
```

Serves on port 9000 (configured in project config). Project data lives in `~/sparge-projects/`.

## Testing

```bash
python3 -m pytest tests/ -q
```

261 tests passing as baseline (some integration tests skip without running server).

## Key directories

- `scripts/` — core logic (ingest, scan, enrich, state, config)
- `ui/` — single-file frontend (index.html, projects.html)
- `tests/` — pytest test suite
- `docs/` — ADRs, design snapshots, pipeline reference, blog diary
- `~/sparge-projects/` — runtime project data (not in repo)
- `~/.sparge/config.json` — points to projects directory
