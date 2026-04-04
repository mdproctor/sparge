# Sparge — From Tool to Product

**Date:** 2026-04-04
**Type:** pivot

---

## What We Were Trying To Achieve

We've built two tools that work for Mark's KIE blog archive. The question
now is whether to keep hacking specifically at that problem, or to step back
and build something reusable that could work for any WordPress or Blogger
blog archive. Mark asked it plainly: can we move this to its own project?

## What We Believed Going In

The tools are already mostly generic. The paths are hardcoded in a few places
but that's fixable. The harder question was whether to keep the two-app
structure (App 1 for HTML cleaning, App 2 for Markdown review) or unify them
into a single product. We thought we might want to keep them separate — they
serve different purposes at different stages of a workflow.

## What We Tried and What Happened

We decided to unify. The reasoning: the two-app structure made sense when
we were building them incrementally, but from a user's perspective the
stages aren't cleanly separated. You might clean HTML and immediately want
to review the Markdown. You might discover during MD review that an image
is broken and need to go back to HTML cleaning. Keeping them as one
application with a clear state model per post is better than two apps you
swap between.

Then came the name. Finding a name for a developer tool that isn't already
claimed is harder than it sounds.

- **Vellum** — immediately appealing (manuscript material, archival feel,
  the metaphor is apt), but there's a well-funded YC-backed LLM platform
  called Vellum. Thoroughly taken.
- **Kiln** — the transformation metaphor is exact, but Kiln AI (local AI
  evaluation tool), legacy Kiln by Fog Creek (Mercurial VCS), and Kiln
  Connect (Web3 staking) all claim it. Taken three ways.
- **Alembic** — the alchemical distillation vessel, perfect for "extracting
  the essence of web content", but it's the standard SQLAlchemy database
  migration tool. One of the most-used Python tools in existence. Taken.
- **Winnow** — the meaning is exactly right (separate grain from chaff),
  memorable, one syllable. But a major Rust parser combinator library at
  v1.0.1 with 900 stars uses it. Plus a legal compliance SaaS, a food
  waste AI company. Taken on multiple fronts.
- **Sparge** — the brewing step that rinses grain with hot water to extract
  pure wort, discarding spent husks. The metaphor is exact: raw web content
  (grain) goes in, noise is stripped (WordPress chrome, JavaScript, tracking
  pixels, junk selectors), clean Markdown (wort) comes out. Verified clear
  in every major package registry: npm, PyPI, crates.io, RubyGems, no active
  tech companies. The only claim is an archived 5-star Go repo from 2018.

We chose Sparge. The project moved to `/Users/mdproctor/claude/sparge/`.
The blog data stays in the GitHub Pages repo — the tool just points at it
via configuration.

The config system was made multi-project from the start. Not because we
needed multiple projects immediately, but because the single-project shape
would have been painful to retrofit. The cost of doing it right up front
was almost nothing. A `projects/` directory with per-project `config.json`
and `state.json`, a `projects.json` index, a server that hot-switches
between projects. The KIE blog is project one; new projects get their own
slot.

## What Changed and Why

The forcing function was Mark asking to move things. Once we were moving
the project anyway, making it genuinely generic cost almost no additional
work. The hardcoded paths were incidental surface area, not fundamental
constraints.

The naming search taught us something worth keeping: almost every evocative
English word has been claimed. The right search space for developer tool
names is obscure domain-specific vocabulary — brewing, geology, manuscript-
making, bookbinding. These communities have rich terminology that the
software world hasn't colonised yet.

## What We Now Believe

Sparge is a good name. The brewing metaphor is apt, memorable, and
unexpected in a good way. The project structure feels right. What we're
unsure about is pace: how far do we push generality before finishing
Mark's actual migration? The answer is probably "far enough to make the
tool correctly shaped, not further." Hypothetical users can't become a
reason to leave the real work unfinished.

---

**Next:** We build the projects landing page and the import modal — the
entry point any user would see first, with a three-mode design for
importing posts: new project, append, or wipe and restart.
