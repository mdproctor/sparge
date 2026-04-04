# Sparge — The Archive Cleaner

**Date:** 2026-04-03
**Type:** phase-update

---

## What We Were Trying To Achieve

Build App 1: a local web tool that scans the KIE HTML archive, surfaces
every problem in a browsable UI, and attempts to fix as many as possible
automatically. Mark needs to be able to see what's broken and verify fixes
before we move to Markdown conversion.

## What We Believed Going In

Most image recovery should be straightforward — the Wayback Machine is
the obvious fallback. We'll query it for each missing image and download
what we find. We expect maybe 60–70% recovery without too much cleverness.

For WordPress chrome stripping, we think a list of CSS selectors
(`header`, `.author-box`, `#comments`, `.sharedaddy`, etc.) will cover
most of it. WordPress themes are standard enough that a fixed list should
work.

For YouTube embeds, we'll look for the video ID in nearby HTML and
reconstruct the thumbnail URL from it. Should be mechanical.

## What We Tried and What Happened

The image recovery turned into a five-approach hierarchy, not a simple
Wayback lookup. The critical insight about the Wayback Machine CDX API:
you can't just ask for "the latest snapshot" of an image URL. The blog
may have published different content at the same URL path over time. You
need to date-target your query — ask for snapshots *around* the post's
publish date, not the most recent one. This caught a meaningful number of
images that the naive "latest snapshot" approach would have returned as
wrong-era versions or wrong images entirely.

We also discovered `ederign.me` — a personal mirror of the KIE blog that
one of the blog's authors maintains. It has many posts and images that
the Wayback Machine doesn't have at all. But the dates don't align: a post
published March 19 on blog.kie.org might appear February 9 on ederign.me.
Date-based matching fails completely; we had to do title-based matching
instead. This was a subtle and time-consuming discovery.

YouTube embeds required Playwright. The video ID isn't embedded in the
HTML at all — the entire iframe src is injected by JavaScript. There's no
reliable static way to get it. We built a headless browser scraper that
visits each affected post on the live blog, waits for the JavaScript to
fill in the iframe src, and captures the result.

GitHub Gist `<script>` tags required a different approach: fetch the Gist
content from the GitHub API and inline it as a `<pre><code>` block. The
script tag tells us the gist ID; the API gives us the files.

Chrome stripping was harder than expected. WordPress themes vary wildly.
Some had author sections inside `<article>`, some after it. Some had sharing
widgets mixed directly into the prose content. The CSS selector list grew
significantly, and we added text-pattern detection as a fallback for things
that didn't have consistent class names.

The most important design decision, which we arrived at while debugging a
false-positive where "recovered" images weren't actually rendering, is that
**serving HTML without JavaScript is not a limitation — it's the correctness
test**. Without JS, lazy-loaded images show as broken squares. That's right:
those images aren't recovered. If we served the HTML with JS enabled, the
blog's own lazy-loading would fire and temporarily fill in image slots with
the external URLs we're trying to replace — masking the problem. The no-JS
render is the ground truth for archival completeness. We leaned into this
explicitly rather than working around it.

The finished tool: `legacy/review-issues.html` — a side-by-side viewer
with a bottom issue panel, issue type filtering, and in-page red-border
highlighting injected dynamically into the iframe (without ever modifying
the source HTML files).

## What We Now Believe

The archive is substantially better. We don't have a precise recovery rate
but it feels like 80%+ of content images are now local. The bigger surprise
was how complex the WordPress chrome stripping turned out to be — it wasn't
a solved problem, it was an ongoing pattern-matching puzzle with no
definitive end state.

The "no-JS as correctness test" principle will shape how we think about the
three-stage pipeline later. Source is what the internet had. You don't fake
it clean.

---

**Next:** With the HTML archive in reasonable shape, we build the Markdown
conversion tool — and discover that "HTML to Markdown" has its own set of
non-obvious traps.
