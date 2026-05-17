# Handover — 2026-05-17

**Branch:** `main` (clean)

## Current state

Phase 1 (Electron packaging) is complete — done before this session started. Verified this session: all 4 child issues closed, all definition-of-done criteria met, 63 unit tests passing.

This session was an archive quality pass on the KIE blog output.

## Three pipeline bugs fixed

**`CodeBlockFixer.fixSpanDrlBlocks()`** (`75bdd57`) — no size or avgLen guard caused entire articles to wrap in a DRL code fence when a sidebar `<br>` and a `<span>rule</span>` co-occurred in the outer article div. Fixed: `text.length() > 2000` and `avgLen > 80` guards added (mirrors `fixBrDrlBlocks()`).

**`Enricher.enrich()` + `ScanHtml.scanPost()`** (`ce8df71`) — empty `<article>` (whitespace only) caused html.parser to re-serialise surrounding content into repeated `<p>` elements. `Enricher` now falls back to `<body>` when article text is blank. `ScanHtml` now flags a structurally empty article as `no_article` ERROR.

**`ConvertPost.java` table handling** (`284b17f`) — three compounding issues: `<noscript>` spacer cells, nested layout wrapper tables, missing `<thead>`. Fixes: `noscript` into `JUNK_SELECTORS`; `flattenNestedTables()`; `normaliseTableHeaders()`; `removeEmptyTags()` extended to `<td>/<tr>`.

## Archive cleanup (mdproctor.github.io)

- 4 `__trashed-N` posts renamed to clean slugs across all layers
- 1 clobbered post restored from source HTML (`2006-05-31-what-is-a-rule-engine.md`)
- 1 corrupted post manually re-converted (`2008-07-06-drools-and-machine-learning.md`)
- 1 repeated-text post recovered from Wayback Machine (`2008-10-15-drools-boot-camp-in-texas-is-now-being-twittered.md`)
- 1 garbled table post hand-corrected (`2012-02-21-drools-jbpm-event-london-8th-march-2012-2.md`)
- `git config --global credential.helper osxkeychain` — added; was missing, causing HTTPS push failures

## What's next

**Immediate:** Re-scan posts with corrupted enriched HTML so they regenerate correctly. Start with `2008-07-06-drools-and-machine-learning` (enriched file deleted this session — will regenerate on next scan).

**Then:** Bulk archive work:
- 546 posts still need MD generation (bulk generate-md run)
- 533 unlabelled code fences across 130 MD posts (bulk language detection)

**Part 5 of "When the Machine Codes"** — waiting on Gastown as the empirical case study. Do not prompt to write until Gastown is working (see memory).

## References

| Context | Where |
|---|---|
| Blog entry (this session) | `docs/_posts/2026-05-17-mdp01-archive-quality-three-bugs.md` |
| Java server fixes | `server/src/main/java/io/sparge/server/CodeBlockFixer.java`, `Enricher.java`, `ScanHtml.java`, `ConvertPost.java` |
| Previous handover | `git show HEAD~1:HANDOFF.md` |
