# Sparge — The KIE Migration Problem

**Date:** 2026-04-03
**Type:** day-zero

---

## What We Were Trying To Achieve

Mark Proctor has 577 blog posts from blog.kie.org sitting in a local HTML
archive at `legacy/posts/mark-proctor/`. He wants them published on his
GitHub Pages Jekyll blog at mdproctor.github.io. The task sounds simple:
convert HTML to Markdown, add Jekyll front matter, push. We think we can
knock this out in a session.

## What We Believed Going In

This is fundamentally a format conversion problem. HTML→Markdown is solved
territory. html2text exists. BeautifulSoup exists. We'll write a script,
run it on 577 files, maybe do some spot-checking, and be done.

We're also assuming the HTML archive is in reasonable shape. It was captured
with a mirror tool, so the content should be intact. There might be some
WordPress chrome to strip — bylines, comment sections, that sort of thing.
We expect those to be easy to detect and remove.

The bigger unknown is images. Blog posts reference images hosted on
blog.kie.org — some of which may no longer be accessible. We're going to
have to deal with that somehow, but we'll cross that bridge when we come
to it.

## What We Tried and What Happened

The moment we looked at the first HTML file closely, the "simple format
conversion" framing dissolved. These aren't clean HTML documents. They're
WordPress output: full of sidebar widgets, author boxes, share buttons,
comment forms, tracking pixels, lazy-loaded images with `data:` placeholder
src attributes, YouTube iframes with empty `src=` that get filled by JS,
and GitHub Gist `<script>` tags that render nothing without JavaScript.

The images situation is worse than anticipated. A huge fraction of images
have been replaced with 1×1 transparent GIFs — WordPress's lazy-loading
at work. The real image URL lives in a sibling `<noscript>` tag. Without
JavaScript running, every lazy-loaded image in the archive is just a blank
square.

We also realised that "convert to Markdown" can't happen until the HTML is
clean. Markdown generated from a post where 40% of the images are broken
1×1 GIFs is garbage Markdown. The archival problem has to be solved first.

## What We Now Believe

This is a two-stage problem, not one. Stage one: make the HTML archive
trustworthy — recover images, fix embeds, strip WordPress chrome. Stage
two: convert the clean HTML to Markdown. We're building two tools, not one.

We don't yet know how many images are actually recoverable. The Wayback
Machine might have them. Other mirror sites might. We'll find out.

---

**Next:** We'll build the HTML archive cleaner — a tool to scan every post,
detect all the problems, and attempt recovery through multiple approaches.
