# Sparge — The Three-Stage Pipeline

**Date:** 2026-04-04
**Type:** phase-update

---

## What We Were Trying To Achieve

Design the correct directory structure for ingested blog archives. The
current approach — one directory, files modified in place — has a
fundamental flaw: once you touch the source HTML, you can no longer compare
against the original. We want a clear structure where source is permanent
reference, cleaned is where work happens, and Markdown is the output.

The asset organisation question is equally important: where do downloaded
images live, and how do you handle the same image appearing in multiple posts?

## What We Believed Going In

The directory structure was obvious: `source/` (original), `cleaned/`
(working copy), `assets/` (downloaded images and CSS), `md/` (Markdown).
Three stages, one direction of transformation.

For assets, we thought a flat hash-named store would work — every image gets
a SHA-256-derived filename, stored in one directory. No collisions, no
ambiguity. Clean.

## What We Tried and What Happened

Mark pushed back on the flat asset store with a question we hadn't considered:
"if you merge into one folder, you will need to deal with duplicate names."
He was right, but not in the way we initially understood. The hash naming
prevents true duplicates but it destroys the ability to see which images
belong to which post. You can't open `assets/` and understand it.

His alternative suggestion: **a folder per post for images**, with globally
shared images detected and promoted to a `global/` folder. This is exactly
the right shape.

We built two detection mechanisms because neither alone is sufficient:

**URL-based real-time detection (during ingest):** The `AssetStore` class
maintains a URL→local-path index. When the same image URL is requested
by a second post, instead of downloading again, it returns the existing path.
The image stays where it first landed. No image is ever downloaded twice for
the same URL. This handles the common case where a site logo or avatar
appears on every post.

**Hash-based consolidation pass (post-ingest):** After bulk importing many
posts, scan all `assets/posts/*/` directories for files with identical
SHA-256 hashes across different post folders. Identical content from different
posts (which could have different URLs — CDN mirrors, URL changes) gets
promoted to `assets/global/`, and all `cleaned/` HTML references are rewritten
to point to the new global location. This pass is idempotent: running it twice
promotes nothing on the second run.

The sidecar bug was real and caught by integration tests before it reached
production: `ingest_post()` was writing the metadata JSON (`{slug}.json`) only
to `source/`. But `init_from_source()` — the function that populates per-post
state from the filesystem — scans `cleaned/` for HTML files and looks for
co-located JSON sidecars to get post dates. Without the sidecar in `cleaned/`,
every ingested post had `date: null`. Append mode couldn't determine the
cutoff date. `GET /api/projects/{id}/newest-date` returned null after a full
import. Fixed by writing the sidecar to both `source/` and `cleaned/`. The
integration tests caught this before it became a confusing user-facing bug.

The security audit on the ingest pipeline surfaced three real vulnerabilities:

- `<img onerror="alert(1)">` event handlers were surviving into cleaned HTML.
  We had a junk-selector stripping function but had never added attribute
  sanitisation. Added a loop that removes all `on*` attributes from every
  surviving tag, strips `javascript:` href/src values, and removes external
  CSS `url()` references.
- `<loc>file:///etc/passwd</loc>` in a sitemap was being processed as a
  post URL. Added a scheme check: only `http://` and `https://` URLs pass
  `_is_post_url()`.
- `http://localhost/../../../etc/passwd` in a sitemap — the `..` segments
  weren't filtered. Added `'..' in path` as a rejection criterion.

All three were real vulnerabilities, not theoretical concerns. The test file
`test_security.py` now exercises all of them.

## What We Now Believe

The three-stage pipeline is the right architecture. Source is read-only
reference — you can always compare to what the internet had. Cleaned is where
work happens. Assets are organised by post ownership with a global fallback.
The dual detection mechanism (URL-based instant + hash-based consolidation)
handles the full range of practical cases.

What we don't know yet: does this hold up against real KIE blog content?
The mock blog (20 articles, known structure) validates the architecture but
can't replicate 577 posts spanning 18 years and multiple WordPress theme
changes. The `kie-fresh` project exists and is configured. It hasn't been
used for a real import. That's the real test, and we haven't run it.

---

**Next:** We step back from feature work to make the project safe for
handoff — 315 tests, security hardening, and a document that gives a
future Claude enough context to continue without losing what we learned.
