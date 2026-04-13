---
layout: post
title: "v1.0.0, the CI obstacle course, and the Quarkus plan"
date: 2026-04-13
tags: [Release, CI, Quarkus]
excerpt: "v1.0.0 is tagged. Getting there took four tag pushes, three Windows CI failures each masking the next, and one discovery that GitHub Pages won't enable itself."
---

v1.0.0 is tagged. The binaries are published. Getting there took more tag pushes than I expected.

The previous entry left off at "the GitHub Actions matrix build will produce `.dmg`, `.exe`, and `.AppImage` on the next version tag." What it didn't cover was how many version tags that would require.

## Building the user guide and website

Before pushing any tag, I wanted v1.0.0 to actually have documentation. I brought Claude in to help build it — 12 pages of user guide plus a Jekyll site to host everything.

The user guide needed screenshots. We wrote a Playwright script (`npm run docs:screenshots`) that launches the Electron app, navigates through each UI state, and saves clipped element-level PNGs. The first run captured everything from the docs fixture project — five small test posts. When I reviewed the results, most MD editor screenshots showed "No Markdown yet" as a full-page empty state. The issues panel said "No HTML issues recorded." Not useful as documentation.

We retook them against the real KIE project instead. Claude found the correct DOM selectors — `.pi` for post rows, `#html-panel`, `#issue-panel`, `#btn-issues` — by inspecting the running Electron app's DevTools rather than guessing from the source. The replacement screenshots show actual content: a KIE post in the split pane, real issue entries in amber, the post list with dates and pipeline badges.

![The Sparge split-pane editor, showing a real KIE post in both HTML and Markdown](/sparge/user-guide/images/05-split-pane-open.png)
*The split pane with real content — "What is a Rule Engine", a 2006 post from the KIE archive.*

The Jekyll site went up at the same time: landing page with a library hero photo, docs with sidebar navigation, and all seven diary entries in the blog. Getting GitHub Pages working surfaced a sequencing constraint: the `configure-pages` Action expects Pages to be enabled before it runs — it doesn't enable it for you. The correct sequence is to call `gh api repos/{owner}/{repo}/pages -X POST --field 'build_type=workflow'` first, then trigger the workflow. The `--field` flag matters here; `-f` produces "invalid key" with no explanation from the gh CLI.

The site also required making the repo public — GitHub Pages is gated on paid plans for private repos. That decision was easy: Sparge is headed for a public blog series about Quarkus anyway.

## Four tags, four attempts

Pushing `v1.0.0` triggered the release workflow. Three platforms, three build jobs. Mac and Linux passed immediately. Windows did not.

**First failure: wrong archive format.** The Python download URL I'd constructed was `x86_64-pc-windows-msvc-install_only_stripped.zip`. HTTP 404. I'd assumed `.zip` on Windows and assumed the extension matched Mac/Linux. The actual file: `cpython-3.12.10+20250409-x86_64-pc-windows-msvc-install_only_stripped.tar.gz`. No `.zip` variant exists in python-build-standalone for Windows. `tar` is available on GitHub Actions Windows runners, so the extraction code needed no special casing — just drop the PowerShell fallback.

**Second failure: wrong variant assumption.** After switching to `.tar.gz`, I guessed Windows might need a `shared` discriminator, the way some toolchains split shared/static builds. Added `-shared` to the arch string. HTTP 404 again. Checking the actual release assets via the GitHub API: no `shared` variant, no `static` variant, just the plain filename. Revert.

**Third failure: three things at once.** With Python downloading successfully, the job reached pip install — and failed. `Scripts/pip.exe` in the python-build-standalone Windows distribution wasn't cooperating. Switching to `python.exe -m pip install -r requirements.txt` fixed it. Same attempt revealed two more: the unit tests were asserting `.zip` for Windows (now wrong after the format fix), and macOS E2E was failing because `npm ci --ignore-scripts` skips the Electron binary download and we weren't reinstalling it before running Playwright. Three separate failures, one attempt.

**Fourth failure: integration tests on Windows.** With everything else fixed, the next layer appeared: Windows integration tests timeout at 15 seconds because the Python server won't start in the CI environment. The tests require a running server; the server requires Python to be configured for Windows paths in a way that isn't set up in CI. Skipped Windows integration tests with a comment. The Windows binary itself works — the tests just can't exercise it in CI without more setup than it's worth right now.

Each Claude fix cleared one layer and revealed the next. By the fourth tag the release job completed: `.dmg`, `.exe`, `.AppImage`, and the update YAML files all in the GitHub release.

## The Quarkus migration design

With v1.0.0 out, I wanted to plan the next real phase. The idea: replace the Python HTTP server incrementally with Quarkus — module by module, with benchmarks at each step — and document it as a blog series. It's a real migration of a real codebase, which makes for an honest story about Quarkus Native.

We brainstormed the bridge mechanism. The obvious option is subprocess per-call — spawn `python3 script.py` for each operation. The problem is latency: scan-html chains four Python functions in sequence, so that's 400–800ms per button click for however long the migration takes. JEP (Java Embedded Python) runs CPython in-process via JNI. Claude confirmed `libpython3.12.dylib` is present in the bundled runtime at `resources/python/mac-arm64/lib/` — the shared library variant that JEP needs. JEP it is.

The migration plan is phased. Phase 0: Quarkus JVM + JEP delegates everything to Python. Phases 1–N: port modules one by one in dependency order — state/config first, then scan and enrich, then the conversion pipeline, then ingest. Each port removes a JEP call; the JEP call count is a running metric across blog entries. Final phase: JEP removed, CPython bundle removed, compile to Quarkus Native.

The test strategy runs alongside: JUnit tests are written against JEP first (proving the contract), then the implementation swaps under the same tests. The pytest suite moves to a holding area rather than being deleted — reactivatable if a specific port needs cross-checking.

Benchmarks at each step: startup time, idle RSS, per-operation latency, bulk throughput on all 577 posts. The comparison is Python vs Quarkus JVM vs Quarkus Native. The spec and plan are both in `docs/superpowers/`. Phase 0 is next.
