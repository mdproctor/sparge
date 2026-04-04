# Sparge — Tests, Security, and Knowing When to Stop

**Date:** 2026-04-04
**Type:** phase-update

---

## What We Were Trying To Achieve

Make the project safe to hand off and safe to continue building on without
losing context. That means comprehensive tests that catch regressions,
security tests that verify real threat surfaces, and documentation that a
future Claude — or Mark in a future session — can read and understand what
was built, why, and what comes next.

## What We Believed Going In

Test coverage was good but uneven. The MD validator had 80 tests covering
all 31 checks. The HTML scanner had 57 tests. The ingest pipeline had unit
tests but no end-to-end integration tests covering the full
source/cleaned/assets flow. The server API had no HTTP-level tests at all.
The UI had no automated tests.

Security we'd thought about case by case, but we hadn't done a systematic
pass. We expected to find a few things we'd missed.

## What We Tried and What Happened

The mock blog server became the foundation for everything. It's a pytest
session-scoped fixture that generates 20 WordPress-like HTML articles with
real JPEG image data, a `sitemap.xml`, and metadata. It starts on a random
port and tears down after the test session. This made it possible to write
integration tests that exercise real HTTP, real file I/O, and real asset
downloading without touching the actual KIE archive.

The integration tests found two bugs in the first run:

**The sidecar location bug** (described in the previous entry): sidecars
were only written to `source/`, but `init_from_source()` looks for them
in `cleaned/`. Every ingested post had `date: null`, breaking append mode
and newest-date detection. The test `test_newest_date_after_ingest` caught
this immediately.

**The http→https URL normalisation bug:** `_normalise_url()` was
force-upgrading `http://` to `https://`. This caused discovery against the
mock blog (which runs plain HTTP) to return zero results — requests to
`https://localhost:PORT` got connection refused. We'd never noticed because
the live KIE blog is HTTPS. The mock blog exposed it. Fixed by preserving
`http://` as-is; only bare domains without a scheme get `https://` added.

The security tests found three real vulnerabilities:

`onerror` attribute XSS — `<img src="x.jpg" onerror="alert(1)">` survived
into cleaned HTML. We had junk-element stripping but no attribute
sanitisation. Once you see this test fail, you can't unsee it. Fixed by
adding an attribute sanitisation loop to `_strip_junk()` that removes all
`on*` event handlers, `javascript:` src/href values, and external CSS
`url()` references.

Sitemap URL injection — a crafted sitemap containing
`<loc>file:///etc/passwd</loc>` was being processed. `_is_post_url()` had
heuristic checks (has a date, isn't a category/tag/page URL) but no scheme
check. Fixed by requiring `http://` or `https://` at the top of the function.

Path traversal — `http://localhost/../../../etc/passwd` in a sitemap was
not filtered. Fixed by checking for `..` in the URL path.

The test isolation problem deserves its own note because it caused a
confusing false failure: if any test activates a temporary project and
the cleanup step doesn't re-activate the original project, the server's
in-memory `_active_project_id` points at a deleted project ID. Every
subsequent call to `GET /api/projects` returns projects with no `active:
true` entry. The fix was simple once understood: cleanup always re-activates
`kie-mark-proctor` before deleting the test project. But it also means you
must restart the server between test runs if any run was interrupted —
stale in-memory state doesn't reset otherwise, and the first test that
checks for an active project will fail.

The handoff document (`docs/HANDOFF.md`) grew to 916 lines. It covers the
full journey in narrative form, every architectural decision and its
rationale, the complete API surface, both config schemas, the known technical
debt (seven items, of which `convert_post.py`'s hardcoded paths is the most
pressing), a detailed test plan with a regression matrix, and six manual
test scenarios for features that have no automated coverage. We also added a
Document History table so future handoffs can be date-stamped and compared
against previous ones.

## What We Now Believe

315 tests is a solid foundation. The security tests found real bugs — that's
the right signal that the investment was worthwhile and that our earlier
"thought about security case by case" approach was insufficient.

We're honest about the gaps. The UI has almost no automated coverage: the
diff modal, staged workflow, scroll sync, keyboard shortcuts, the
source/cleaned toggle — all of these work (we've used them in the session),
but there are no browser-level tests. That's documented as a Playwright
gap for when the time is right.

The biggest unresolved question has nothing to do with code: Mark's 577
posts are still mostly unreviewed. The `kie-fresh` project exists and is
configured for the new three-stage pipeline but has never been used for
a real import. We've built a tool; the work the tool was built to do hasn't
happened yet. At some point the right move is to stop building and start
using.

---

**Next:** A future session will resolve the standing choice: start the real
KIE migration (open kie-fresh, run a real import against the live blog,
work through posts) or continue building (fix `convert_post.py`'s hardcoded
paths, push to GitHub, build the post-ingest summary page). The
`docs/HANDOFF.md` describes both paths in full.
