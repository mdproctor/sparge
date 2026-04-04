# Sparge — The Markdown Reviewer

**Date:** 2026-04-03
**Type:** phase-update

---

## What We Were Trying To Achieve

Build App 2: a side-by-side reviewer showing the original HTML on the left
and converted Markdown on the right. Mark steps through his 577 posts,
generates MD for each, reviews the output, and marks posts as approved or
flagged. We want this to feel like a genuine review workflow, not a script
that runs and produces files he has to inspect manually.

## What We Believed Going In

html2text handles the hard parts of HTML→Markdown conversion. We wrap it
with BeautifulSoup to strip remaining junk, then produce Jekyll front matter
from the JSON sidecar. The main work is polishing edge cases in the output.

We're expecting the conversion output to be mostly good. The hard part was
Stage 1 (image recovery and chrome stripping). Stage 2 should be relatively
mechanical.

## What We Tried and What Happened

The first major bug is now permanently recorded in our test suite as a named
lesson: **the placeholder collision bug**. html2text converts `<pre><code>`
blocks to 4-space-indented text, losing the language tag entirely. The fix
is obvious: extract code blocks before passing to html2text, replace with
unique placeholder strings, then restore them as fenced blocks afterward.

The placeholder format matters enormously. We initially used
`CODEBLOCK_FENCE_1`, `CODEBLOCK_FENCE_2`, and so on. Then
`str.replace('CODEBLOCK_FENCE_1', ...)` was called on a string containing
`CODEBLOCK_FENCE_10`, and `FENCE_10` became `FENCE_1` + a stray `0`. The
zero appeared immediately after the closing fence: ` ```0`. A post with ten
or more code blocks would silently corrupt every block after the ninth.

Fixed with zero-padded delimited keys: `@@CODEBLOCK_000@@`,
`@@CODEBLOCK_001@@`. Every key is exactly 15 characters. No key is a
substring of any other. Partial matching is impossible by construction.

html2text also produces angle-bracket link format for some URLs:
`](<https://...>)` instead of the more common `](https://...)`. Our
link-count validator was checking for `](https?://` and completely missing
the angle-bracket variant. Every post with many links was flagging as
having "dropped links" — a false positive affecting hundreds of posts.
We caught this while puzzling over why the KIE posts were all showing link
loss.

The validator grew organically from these discoveries. Every time we saw
a conversion artifact we hadn't anticipated, we added a check for it. By
the end there were 31 checks: 16 that run on the Markdown alone (structural
integrity, WordPress junk, HTML entities still present, etc.) and 15 that
cross-validate the Markdown against the original HTML (word count ratio,
heading presence, code block count, image count, technical term survival,
and more). The cross-validation was the most valuable part — it caught
entire sections of content being silently dropped that visual inspection
would have missed.

The staged workflow was not planned. It emerged from a question Mark asked:
what happens if you regenerate MD for a post you've already reviewed? The
naive answer — overwrite and re-review — loses your review work. The right
answer is: dry-run the generation first, compare the output to what's on
disk, and only show a diff if anything changed. We built an LCS-based
side-by-side diff modal (Myers algorithm, pure JS, no dependency) for this.
It became one of the most-used features of the review tool.

The scroll sync algorithm deserves a mention. Pixel-proportional sync
between two panels doesn't work when content is distributed differently
between HTML and Markdown (a post with a large code block followed by two
sentences will be much longer in HTML than Markdown). We implemented
heading-anchored proportional sync: match h2/h3 headings by normalised text
between both panels, use the matched pairs as anchor points, interpolate
linearly between anchors. Within each section, scroll is proportional to
that section's height. Headings always align; the rest does the best it can.

## What We Now Believe

Stage 2 was not mechanical. The conversion has its own complexity distinct
from the archival problems — placeholder collisions, link format edge cases,
silent content drops. The validator suite is essential; you genuinely cannot
trust eyeballing 577 posts. The staged workflow and diff modal are features
we'd carry forward into any future version of this tool.

We also notice something that will matter soon: we've built two good
standalone tools, but they're both hardcoded to Mark's specific paths. There
is no reason these tools couldn't work for any blog archive. That observation
is going to change the project's shape.

---

**Next:** That last observation turns into a deliberate pivot. We're going
to extract these tools from the blog repo and make something reusable — but
first we have to find a name that isn't already taken.
