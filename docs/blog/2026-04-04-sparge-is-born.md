---
typora-root-url: ../..
---

# Sparge — the tool gets a name

**Date:** 2026-04-04
**Type:** phase-update

---

## What I was trying to achieve: learn vibe coding on a real problem

The two-panel reviewer worked. At this point I had something that solved my immediate problem — but I also had a more interesting opportunity.

I'd been wanting to properly learn vibe coding, particularly with UIs. The KIE archive was a perfect vehicle: a well-defined problem I understood completely, enough scope to make it interesting, and a clear measure of success. If it worked well enough that someone else could use it to migrate their own blog, I'd built something real.

This was also the perfect opportunity to find out exactly what vibe coding can do — how far it can be pushed, how much polish is achievable in a short time. I had a justification for letting the ADHD OCD tendencies run. So I did. The dopamine hit from fast, productive responses — each prompt delivering something real — was intense. "Just one more prompt." :) That deliberate decision to keep pushing changed what I was building: multi-project support, a proper ingest pipeline, real test coverage. Not just a one-off script with a UI skin.

## Building the ingest pipeline

I brought Claude back in for this phase. The ingest pipeline was the core piece — given a URL, detect the platform, discover all post URLs via sitemap or API, fetch each one, extract the article body, localise images, write the HTML to the project folder. Claude and I built the full pipeline in one session: platform detection, discovery, preview before committing, and a background job runner with progress reporting.

[![Sparge ingest pipeline — click to enlarge](/assets/blog/sparge-ingest-thumb.jpg)](../../assets/blog/sparge-ingest.png)
*Discovering posts from a live blog URL — platform auto-detected as WordPress, 577 posts queued for ingest.*

Multi-project architecture came alongside it — each project gets its own config, state file, and folder. Switching between them activates the right paths across the whole server.

## 214 tests and a name

We added a proper test suite. Not just happy-path checks — security tests, navigation edge cases, the full scan and ingest flows against a mock blog serving 20 generated articles. Claude flagged several security issues during the review pass I hadn't spotted: path traversal risks in the static file server, missing input validation on project creation.

I renamed it Sparge. It's a brewing term — the final rinse of the grain bed, extracting the last of what's there. That felt right.

214 tests passing.
