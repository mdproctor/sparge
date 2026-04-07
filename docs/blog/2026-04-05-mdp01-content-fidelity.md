---
typora-root-url: ../..
---

# Sparge — what the pipeline was silently losing

**Date:** 2026-04-05
**Type:** phase-update

---

## What I was trying to achieve: stop losing content on ingest

Sparge ingested HTML cleanly. What it didn't do was preserve the content that WordPress had embedded rather than written — YouTube iframes stripped silently, GitHub Gists removed without a trace, SyntaxHighlighter code blocks with `brush:java` classes that highlight.js would never pick up. Post after post looked fine until you noticed the missing video, the missing code sample, the missing diagram.

I brought Claude back in to fix this properly.

## The three-stage pipeline

The fix required a design decision first. I didn't want enrichment happening at ingest time — ingest should be a pure download, nothing more. And I didn't want it happening at MD generation time either, where it couldn't be inspected.

The answer was a third stage between them: Scan now writes an enriched copy of the HTML to `enriched/` before running validation. Generate MD reads from enriched if it exists, falls back to original. The original is never touched.

Claude and I built `enrich.py`. YouTube iframes became local thumbnails. Gists were fetched via the GitHub API and inlined as code blocks. `brush:java` classes normalised to `language-java`. Unknown embeds wrapped with a fallback link rather than silently removed.

[![Sparge content fidelity — click to enlarge](/assets/blog/sparge-enrich-thumb.jpg)](../../assets/blog/sparge-enrich.png)
*After enrichment: the YouTube iframe is replaced with a local thumbnail, the Gist inlined as a code block. The original HTML is untouched.*

## Projects move out of the repo

While we were in the pipeline, I also fixed something that had been bothering me: project data lived inside the blog-migrator directory. Move the code, lose the projects.

I decided on `~/.sparge/config.json` pointing to `~/sparge-projects/`. App config in one place, project data in another. Claude and I wired it up — `sparge_home.py` reads the config on startup, and the old location is left intact.

## Author filter

The UI showed all posts regardless of the project's author filter. That was fine for a single-author project but wrong for anything broader.

Between us we added `GET /api/posts?author=X` on the server side and a dropdown in the UI that pre-selects from the project config. Switch authors within a session without touching config.
