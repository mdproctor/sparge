# Sparge — Design Snapshot
**Date:** 2026-04-09
**Topic:** Archive Room UI theme — index.html and projects.html
**Supersedes:** *(none — parallel to 2026-04-06-canonical-paths-and-confusion)*
**Superseded by:** *(leave blank — filled in if this snapshot is later superseded)*

---

## Where We Are

Both UI pages (`ui/index.html` and `ui/projects.html`) have been fully restyled from a
GitHub-dark palette to the Archive Room aesthetic: parchment background (`#f4f0e8`), ink-black
primary (`#2a2218`), muted-slate accent (`#4a6a8a`), Georgia serif italic logo, 2px border
radius throughout. All 13 CSS tokens are defined in a single `:root` block in each file.
Zero remaining dark palette hex values in either file. The CodeMirror editor supports a
light/dark toggle persisted in `localStorage`.

## How We Got Here

| Decision | Chosen | Why | Alternatives Rejected |
|---|---|---|---|
| CSS custom properties at `:root` | Single token block per file | Single-file architecture; no build step | Separate CSS file, Tailwind |
| Light-first editor theme | CodeMirror `default` + custom CSS scoped to `body[data-editor-theme="light"]` | Matches parchment aesthetic; dark toggle via `material-darker` preserved | Overriding CM theme entirely |
| SVG logo fills | Literal hex (`#4a6a8a`, `#c87020`) | SVG presentation attributes don't reliably resolve CSS `var()` | `var(--accent)` / `var(--warn)` |
| Theme toggle | `localStorage` key `sparge.editor.theme`, applied via `data-editor-theme` on `<body>` | CSS-only toggle; no JS colour interpolation needed | Per-editor class, JS colour injection |
| `iframe` highlight colour | Literal hex `#8a2a2a` in JS-injected `<style>` | CSS custom properties don't resolve across frame boundaries | `var(--error)` (silently fails) |
| projects.html styling | Same `:root` tokens, matched component-by-component | Consistency; projects.html shares design language with index.html | Shared external CSS file |

## Where We're Going

**Next steps:**
- Electron wrapper — bundle the Python server as a self-contained binary (PyInstaller/Nuitka);
  Electron manages the Python process lifecycle, BrowserWindow loads `localhost:PORT`
- Bulk scan run — 546 posts still need MD generation via Sparge's enrichment pipeline

**Open questions:**
- Electron packaging strategy: PyInstaller vs Nuitka vs embedded Python runtime
- Auto-update mechanism for the Electron app (Squirrel, electron-updater, or manual)
- Whether `projects.html` becomes an Electron-native window or stays a web page

## Linked ADRs

| ADR | Decision |
|---|---|
| [ADR-0001](../adr/0001-three-stage-immutable-pipeline.md) | Three-stage immutable pipeline (ingest → scan → generate) |
| [ADR-0002](../adr/0002-user-level-storage-architecture.md) | User-level storage at `~/sparge-projects/` |

## Context Links

- UI spec: `docs/superpowers/specs/2026-04-09-archive-room-redesign.md`
- Implementation plan: `docs/superpowers/plans/2026-04-09-archive-room-redesign.md`
