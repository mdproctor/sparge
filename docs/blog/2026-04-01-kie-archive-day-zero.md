---
typora-root-url: ../..
---

# Sparge — Day Zero: 577 posts and a pile of scripts

**Date:** 2026-04-01
**Type:** day-zero

---

## What I was trying to achieve: get my old KIE blog posts into Jekyll

Fifteen years of posts on blog.kie.org. 577 mine — on Drools, rule engines, PHREAK, backward chaining, the full arc of the KIE project. I wanted them on my own site, under my own control, published as Jekyll Markdown.

The archive already existed. I'd spent serious time hunting broken images: Wayback Machine CDX queries, lazy-load recovery, Playwright for JS-injected iframes, cross-referencing Red Hat and DZone mirrors for images that had vanished from the original CDN. That work was manual, painstaking, and irreplaceable. A WordPress XML dump would lose all of it.

## What I believed going in: scripts would be enough

I had `convert_post.py`. Run it across all 578 posts, validate with `md_validator.py`'s 31 checks, review the output. Straightforward.

## The batch conversion that lasted one commit

I asked Claude to run it. The commit came back: "convert all 578 Mark Proctor posts to Jekyll Markdown."

Four hours later I reverted the lot: "starting over with manual review process."

Claude had done exactly what I asked. The problem was what I'd asked for. The validator produced a wall of output — hundreds of warnings about missing images, word count drops, code blocks that hadn't converted cleanly, heading mismatches. No way to tell which were real problems and which were noise without opening the original HTML alongside the generated Markdown and looking. Do that 578 times, with no tooling, and you lose track completely.

Scripts had gotten me the archive. They couldn't get me through the review.
