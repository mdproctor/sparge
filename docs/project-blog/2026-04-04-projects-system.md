# Sparge — The Projects System

**Date:** 2026-04-04
**Type:** phase-update

---

## What We Were Trying To Achieve

Design and build two distinct levels of the UI: a projects landing page
where users manage blog archives, and a per-project review UI where the
actual post work happens. These need to feel different — navigation vs work.
We also need to figure out where "importing posts" lives in this structure.

## What We Believed Going In

The projects page is the simpler part: a list of cards with stats, a "New
Project" button, some basic actions per card. We'll put importing inside the
per-project review UI as its own tab — "Ingest" — alongside the "Review"
and "Overview" tabs. That feels logical.

## What We Tried and What Happened

The Ingest tab in the review UI was wrong. Mark clicked "Open" on the Fresh
Import project and asked "where is the button to start the ingest?" The
answer was: buried in a tab inside the review UI, which you can't access
until you open a project that has no posts yet. The flow was circular.

Once we saw that confusion, the correct structure was obvious: import is a
project-level action, not a post-level action. It belongs on the projects
page, on each project card, triggered before you open the project. We moved
it there and added a three-mode modal:

1. **New project** — import into a fresh project; the existing one is untouched
2. **Append newer posts** — discover all URLs, filter by cutoff date, only
   fetch posts newer than what's already there
3. **Wipe and re-import** — destructive: clears all data, then re-imports
   from scratch with a second confirmation step

The append mode required building `extract_date_from_url()` — a function
that parses YYYY-MM-DD dates from blog post URL slugs. More nuanced than
expected: WordPress uses three formats (`/YYYY/MM/DD/slug/`,
`/YYYY-MM-DD-slug`, and `/YYYY/MM/slug` for month-only URLs, treated as
first of that month). The cutoff comparison is strictly "after" not
"including" — a subtle but important distinction that affects idempotency
when running append mode twice in a row.

The wipe mode required a schema guard. Wipe is only allowed for "new-schema"
projects that store data in their own directories (the `data.source_dir /
cleaned_dir / assets_dir / md_dir` config format). It's explicitly blocked
for legacy-schema projects like the current KIE archive, whose data lives in
the GitHub Pages repository at `/Users/mdproctor/mdproctor.github.io/legacy/`.
If wipe were allowed there, it would delete content from a different git repo.
The 400 error on attempted wipe of a legacy project is not an oversight —
it's a deliberate safety boundary.

The UI layout went through one significant correction. Originally the per-post
action buttons (Scan, Generate MD, Validate, Flag) lived in the top navigation
bar alongside the Browse/Overview mode tabs. Mark said they "danced" when
navigating between posts because the post title changed length. The fix was
structural, not cosmetic: move all post-scoped actions into a dedicated "post
action bar" that sits between the top navigation and the content panels. The
top bar is now navigation only; the post action bar is work. Once re-laid-out
this way, the scoping is obvious from layout alone without needing labels.

## What We Now Believe

The project/review separation is correct. The import modal three-mode design
handles the common cases cleanly. The legacy schema guard is the right safety
model — we should not be in the business of deleting content from other repos.

We're still unsure about the right migration path for the KIE legacy data.
There's no one-click "migrate existing posts to the new three-stage schema"
flow. That gap is documented but unresolved.

---

**Next:** We tackle the most architecturally significant decision in the
project: a three-stage source/cleaned/assets directory split that forces
us to be explicit about what "the archive" actually is and what we're
allowed to modify.
