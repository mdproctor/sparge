Sparge is now a desktop app. Not a web server you start from a terminal — an actual `.app` you open, with a dock icon and everything.

The path from "Python HTTP server" to "self-contained Electron app" took most of the session. The architecture choice was straightforward: embed CPython via python-build-standalone, bundle it at build time, have the Electron main process spawn the server on a dynamic port, load `localhost:PORT/ui/` in a BrowserWindow. No changes to `server.py` beyond accepting `--port` as a CLI argument.

What wasn't straightforward was the process manager. I wanted a proper state machine — not a thin `spawn()` wrapper that dies silently when the server crashes. We built `python-server.js` with six states: idle, starting, healthy, crashed, restarting, and fatal. Exponential backoff on crashes. A 200-line log ring buffer for the error dialog. A 60-second stability counter that resets the crash count if the server runs cleanly long enough.

We implemented it task-by-task using the subagent pattern — one fresh agent per task, spec compliance review, then code quality review before moving on. For a module like this it's exactly the right approach: the state machine logic is subtle enough that you want isolated context for each piece.

The final code review caught something neither of us had seen during development. The packaged app resolves Python at `Resources/python/bin/python3`. But I'd written `path.join(process.resourcesPath, 'python', 'mac-arm64', 'bin', 'python3')` — including the platform subdirectory. In production electron-builder strips that subdir when copying `extraResources`. The path would have resolved in dev mode (where the source tree structure is intact) and failed silently on every packaged launch.

Worth noting for anyone bundling platform-specific runtimes: if you use `extraResources` with `"from": "resources/python/mac-arm64", "to": "python"`, the contents of `mac-arm64/` land directly in `Resources/python/` — not in `Resources/python/mac-arm64/`. There's no warning and E2E tests in dev mode won't catch it.

The path configuration work that followed was less glamorous but more fundamentally correct. Sparge had `ROOT = Path('/Users/mdproctor/mdproctor.github.io')` sitting in `scripts/convert_post.py`. That's the kind of thing that makes a codebase permanently personal — not wrong enough to block anything, but impossible to hand to anyone else.

More interesting than the cleanup was the folder picker design conversation. I'd expected to add browse buttons to the config panel — give users a way to change paths after the fact. But thinking through what actually happens after you ingest 577 posts into a project: all the state, enriched HTML, and generated markdown assumes those paths. Changing them would be a disaster. The right answer is that paths are immutable after creation — set them once, at project creation time, and the UI makes that clear.

So we added native 📁 buttons to the project creation form instead. Four fields, four buttons. The browse dialog starts at home dir for `serve_root`, at `serve_root` for the relative subdirectories. If you pick something outside `serve_root` the path is stored as absolute; inside and it's stored as relative. The config panel now shows the paths ghosted — visible, not editable, with a tooltip that says why.

Both features are on main. The GitHub Actions matrix build will produce `.dmg`, `.exe`, and `.AppImage` on the next version tag.
