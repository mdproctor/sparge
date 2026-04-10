# Sparge — Design Snapshot
**Date:** 2026-04-10
**Topic:** Electron desktop app and path configuration
**Supersedes:** *(none — new topic)*
**Superseded by:** *(leave blank — filled in if this snapshot is later superseded)*

---

## Where We Are

Sparge is now a self-contained Electron desktop application. The existing Python HTTP server (`server.py`) runs as an embedded subprocess managed by `python-server.js` — a state machine (idle → starting → healthy → crashed → restarting | fatal) with exponential backoff crash recovery. CPython is bundled via python-build-standalone, downloaded at build time and SHA-256 verified. Path configuration across the codebase is clean: no hardcoded machine-specific paths remain, project path fields are set at creation time and locked thereafter, and the local project creation form has native 📁 folder-picker buttons on all four path fields via Electron's `dialog.showOpenDialog` IPC.

## How We Got Here

Key decisions made to reach this point:

| Decision | Chosen | Why | Alternatives Rejected |
|---|---|---|---|
| Python bundling strategy | python-build-standalone (embedded CPython) | Relocatable, debuggable, clean separation | PyInstaller (magic import issues with dynamic paths), Nuitka (slow compilation) |
| Process management | Dedicated `python-server.js` state machine | Testable independently; crash recovery explicit and observable | Thin shell wrapper (brittle, no crash recovery), Node IPC bridge (rewrites server.py) |
| Window strategy | Single BrowserWindow loads `localhost:PORT/ui/` | No changes to existing UI; clean separation | Two BrowserWindows (extra complexity), multi-tab (requires server refactor — post-V1) |
| Distribution | GitHub Actions matrix (Mac/Win/Linux) → GitHub Releases + electron-updater | Standard Electron pattern; auto-update included | Manual builds, package managers (too much infra) |
| Folder picker placement | Project creation form only | Paths are immutable after creation — setting them at creation is the right UX | Config panel picker (would imply paths are editable, contradicts lock-at-creation intent) |
| Path storage rule | Relative if inside serve_root, absolute if outside | Maximal flexibility; user can pick anywhere | Restrict to inside serve_root only (too limiting for varied setups) |
| Code signing V1 | None | Cert cost not justified at current scale | Apple Developer ID + EV cert (add post-V1 when distribution scale warrants it) |

## Where We're Going

**Next steps:**
- 533 unlabelled code fences across 130 MD posts — bulk language detection needed for syntax highlighting
- Multi-project tabs (post-V1): each tab opens a project in parallel
- Code signing: Apple Developer ID and Windows EV cert when distribution scale warrants it

**Open questions:**
- Multi-project tabs architecture: single server with project-context-per-request (larger refactor) vs. one server process per tab (heavier but isolated)?
- `ENRICHED_DIR` in `server.py` still has a hardcoded project-ID fallback (`kie-mark-proctor`) — needs cleanup before any open-sourcing effort
- Auto-update cadence: 4h polling works for now — revisit if users report intrusive update prompts

## Linked ADRs

*(No ADRs created for these decisions — captured in specs and plans below.)*

## Context Links

- Electron wrapper spec: `docs/superpowers/specs/2026-04-09-electron-wrapper-design.md`
- Path config spec: `docs/superpowers/specs/2026-04-10-path-config-and-folder-picker-design.md`
- Electron wrapper plan: `docs/superpowers/plans/2026-04-09-electron-wrapper.md`
- Path config plan: `docs/superpowers/plans/2026-04-10-path-config-and-folder-picker.md`
- Epic #42 (Electron Desktop Wrapper), Epic #47 (Project Configuration & Path Management)
