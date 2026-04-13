# Sparge — Design

Sparge is a blog migration and content enrichment tool for the KIE/Drools archive. It runs as an Electron desktop application embedding a Python HTTP server. This document captures architectural decisions; the user-facing documentation is in `docs/user-guide/`.

**Canonical location:** `~/claude/sparge/` (GitHub: https://github.com/mdproctor/sparge)

**Do not work in any other location.** Past sessions created a duplicate `blog-migrator/` directory inside the Jekyll publishing repo; that directory has been deleted. CLAUDE.md documents the canonical paths table.

---

## Core Architecture

### Three-Stage Immutable Pipeline

[ADR-0001](docs/adr/0001-three-stage-immutable-pipeline.md) — original HTML is never mutated:

1. **Ingest** — read HTML, create project state
2. **Scan/Enrich** — apply HTML fixes, write to `enriched/`
3. **Generate MD** — convert enriched HTML to Markdown output

### Storage Architecture

[ADR-0002](docs/adr/0002-user-level-storage-architecture.md) — `~/.sparge/config.json` → `~/sparge-projects/<project>/`

| Path | Contents |
|---|---|
| `~/.sparge/config.json` | Global config: list of projects and their locations |
| `~/sparge-projects/<project>/config.json` | Per-project config: serve_root, author, paths |
| `~/sparge-projects/<project>/state.json` | Per-project scan state |
| `~/sparge-projects/<project>/enriched/` | Enriched HTML copies (Scan output) |

[ADR-0003](docs/adr/0003-author-filter-config-and-ui.md) — Config sets default author scope; UI dropdown overrides per-session.

[ADR-0004](docs/adr/0004-enrichment-at-scan-not-ingest.md) — HTML fixes applied at Scan time, written to `enriched/`; original HTML in `serve_root` never modified.

### Key Decisions

| Decision | Chosen | Why | Alternatives Rejected |
|---|---|---|---|
| Single canonical codebase | `~/claude/sparge/` only; `blog-migrator/` deleted | Multiple Claude sessions confused two locations, accumulating work in the wrong repo | Leave both; add warning comments |
| KIE project content location | `serve_root` → `~/mdproctor.github.io/`; content stays in Jekyll repo | Content belongs with the publishing repo; Sparge is the tool not the content store | Move content into sparge repo |
| asset_store + consolidate | Option A: integrated alongside existing ingest; `/api/consolidate` endpoint + UI button | Lower risk than full ingest rearchitecture | Option B (logged in `docs/ideas/IDEAS.md`) |
| Path storage rule | Relative if inside `serve_root`, absolute if outside | Maximal flexibility | Restrict to inside serve_root only |

---

## Archive Room UI

Both `ui/index.html` and `ui/projects.html` use the Archive Room aesthetic: parchment background (`#f4f0e8`), ink-black primary (`#2a2218`), muted-slate accent (`#4a6a8a`), Georgia serif italic logo, 2px border radius. All 13 CSS tokens defined in a single `:root` block per file.

| Decision | Chosen | Why | Alternatives Rejected |
|---|---|---|---|
| CSS custom properties at `:root` | Single token block per file | Single-file architecture; no build step | Separate CSS file, Tailwind |
| Light-first editor theme | CodeMirror `default` + custom CSS scoped to `body[data-editor-theme="light"]` | Matches parchment aesthetic; dark toggle via `material-darker` | Overriding CM theme entirely |
| SVG logo fills | Literal hex (`#4a6a8a`, `#c87020`) | SVG presentation attributes don't reliably resolve CSS `var()` | `var(--accent)` / `var(--warn)` |
| Theme toggle | `localStorage` key `sparge.editor.theme`, `data-editor-theme` on `<body>` | CSS-only toggle; no JS colour interpolation | Per-editor class, JS colour injection |
| `iframe` highlight colour | Literal hex in JS-injected `<style>` | CSS custom properties don't resolve across frame boundaries | `var(--error)` (silently fails) |

---

## Electron Desktop App

Sparge runs as an Electron desktop application. The Python server runs as an embedded subprocess.

| Decision | Chosen | Why | Alternatives Rejected |
|---|---|---|---|
| Python bundling | python-build-standalone (embedded CPython) | Relocatable, debuggable, clean separation | PyInstaller (magic import issues), Nuitka (slow compilation) |
| Process management | Dedicated `python-server.js` state machine (idle → starting → healthy → crashed → restarting/fatal) | Testable independently; crash recovery explicit | Thin shell wrapper (brittle), Node IPC bridge (rewrites server.py) |
| Window strategy | Single BrowserWindow loads `localhost:PORT/ui/` | No changes to existing UI; clean separation | Two BrowserWindows, multi-tab (post-V1) |
| Distribution | GitHub Actions matrix (Mac/Win/Linux) → GitHub Releases + electron-updater | Standard Electron pattern; auto-update included | Manual builds, package managers |
| Folder picker | Project creation form only (paths immutable after creation) | Paths locked at creation is the right UX | Config panel picker (implies editability, contradicts lock-at-creation intent) |
| Code signing V1 | None | Cert cost not justified at current scale | Apple Developer ID + EV cert (post-V1) |

---

## KIE Archive Project — Current State

Canonical paths (configured in `~/sparge-projects/kie-mark-proctor/config.json`):

| Stage | Path | Files | Notes |
|---|---|---|---|
| HTML source (original) | `~/mdproctor.github.io/legacy/posts/mark-proctor/` | 577 HTML | **Never modify** |
| Assets | `~/mdproctor.github.io/legacy/assets/` | 2,983 files | Already localised |
| MD output | `~/mdproctor.github.io/mark-proctor/` | 31 MD | 546 posts need MD generation |
| Enriched HTML | `~/sparge-projects/kie-mark-proctor/enriched/` | 0 files | Bulk scan not yet run |

326 tests passing (as of 2026-04-06). HTML files pre-enriched by pre-Sparge scripts (YouTube thumbnails, language classes). 533 unlabelled code fences across 130 MD posts — bulk language detection needed.

---

## Next Steps

- Bulk re-scan all 577 posts through Sparge's enrichment pipeline
- Bulk generate MD for the 546 posts without it
- Fix 533 unlabelled code fences (bulk language detection for syntax highlighting)
- Multi-project tabs (post-V1): each tab opens a project in parallel
- Image recovery pipeline: Wayback Machine, lazy images, Playwright iframes
- Code signing: Apple Developer ID and Windows EV cert when distribution scale warrants

---

## Open Questions

- `enriched/` copies: commit to git or gitignore? Currently untracked.
- Should the full 1,801-post KIE archive (all authors) become one Sparge project?
- Legacy `scripts/` in Jekyll repo — delete or keep for reference?
- Multi-project tabs architecture: single server with project-context-per-request vs one process per tab?
- `ENRICHED_DIR` in `server.py` has a hardcoded project-ID fallback (`kie-mark-proctor`) — needs cleanup before open-sourcing
- Auto-update cadence: 4h polling — revisit if users report intrusive prompts

---

## ADRs

| ADR | Decision |
|---|---|
| [ADR-0001](docs/adr/0001-three-stage-immutable-pipeline.md) | Three-stage immutable pipeline |
| [ADR-0002](docs/adr/0002-user-level-storage-architecture.md) | User-level storage at `~/sparge-projects/` |
| [ADR-0003](docs/adr/0003-author-filter-config-and-ui.md) | Author filter: config default + UI override |
| [ADR-0004](docs/adr/0004-enrichment-at-scan-not-ingest.md) | Enrichment at Scan, not Ingest |
