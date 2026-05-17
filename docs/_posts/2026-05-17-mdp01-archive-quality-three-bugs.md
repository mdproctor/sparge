---
layout: post
title: "Archive Quality: Three Pipeline Bugs and What Caused Them"
date: 2026-05-17
type: phase-update
entry_type: note
subtype: diary
projects: [sparge]
tags: [enrichment, converter, java, beautifulsoup, pipeline, debugging]
---

The Quarkus server is done. The Electron packaging is done. With the migration tool itself complete, I turned my attention to the output — 577 posts, a meaningful fraction of which had conversion problems. Three of them led somewhere interesting.

---

## The article that became a code block

"Drools and Machine Learning" (2008) came out of the converter entirely wrapped in a DRL code fence. Every paragraph of prose, the sidebar text, all of it — inside ` ```drl `.

The source HTML had an inline DRL rule in the article, formatted with nested `<span>` elements the way the old KIE blog styled code. `CodeBlockFixer` has a method — `fixSpanDrlBlocks()` — that finds any `<div>` containing a leaf `<span>` whose text is exactly "rule", tests whether the element's full text looks like DRL, and if so wraps the whole element in `<pre><code class="language-drl">`.

The problem: no size guard. The outer article `<div>` had `<br>` tags from the WordPress sidebar and the rule keyword buried inside it. The method matched the entire article. Wrapping a 3,000-character prose article in a code block is exactly what you'd expect from a method that checks for the rule keyword but not the element's length.

`fixBrDrlBlocks()` — the sibling method — already had the right guards: skip if average line length exceeds 80 characters (prose, not code) and skip if text exceeds a size limit. I added both to `fixSpanDrlBlocks()`. Fourteen lines. Fixed.

---

## The article that repeated itself fifty times

"Drools Boot Camp in Texas is Now Being Twittered" (2008): a single-sentence announcement repeated approximately fifty times in the output.

The source HTML has an empty `<article>` element — just whitespace. Whatever was in it when this was archived is gone. What's interesting is that the enriched HTML, produced a month after archiving, has the twitter text repeated.

The timestamps said everything. Enrichment ran at 02:11 on April 7th. The source HTML file was last modified at 06:21 that same day. The enrichment ran on an earlier version of the source that still had real content; the source was then overwritten with the empty shell.

`Enricher.enrich()` had no blank check on the `<article>` element it found — unlike `IngestService.findArticle()`, which checks `!e.text().isBlank()` before accepting any candidate element. So when a subsequent run enriched the now-empty source, it passed the empty article through all enrichment functions and serialised the full soup document. BeautifulSoup's `html.parser` re-homed the archive header text under implicit block rules, repeating it across dozens of new `<p>` elements that weren't in the original HTML.

Two fixes: `Enricher.enrich()` now falls back to `<body>` when `<article>` is blank. `ScanHtml.scanPost()` now flags an empty `<article>` as a `no_article` ERROR, catching the problem before enrichment and MD generation run on it.

---

## The agenda table that couldn't hold itself together

The London 2012 event post had an agenda table rendered as `---|---` pipe garbage. Three things were compounding.

First: the KIE blog uses `<noscript>` elements as invisible spacer cells between real table data. Second: the actual agenda data sits inside a `<td>` of an outer layout wrapper table — two levels of nesting for a simple two-column time/session grid. Third: the table had no `<thead>`, so flexmark produced a separator row with nothing above it.

Three additions to `ConvertPost.java`: `noscript` into `JUNK_SELECTORS`, a `flattenNestedTables()` method that promotes inner tables when the outer is a pure wrapper, and `normaliseTableHeaders()` that promotes the first `<tr>` to `<thead>` on tables that lack one. After that: a clean `| Time | Session |` table, as it should have been.

---

Other cleanup this session: four posts with `__trashed-N` slugs from a WordPress CMS accident renamed to their actual titles, seven genuine blog duplicates confirmed live on the original KIE site and retained, one post clobbered by an unrelated commit restored from its source HTML.
