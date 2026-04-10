# Sparge Website Design Spec
**Date:** 2026-04-10
**Topic:** Jekyll website — landing page, docs, blog — published to GitHub Pages
**Status:** Approved, ready for implementation

---

## Overview

A Jekyll site built inside the existing `sparge` repo, served from `docs/` on the `main` branch via GitHub Pages at `mdproctor.github.io/sparge/`. Three sections: landing page, user guide docs (12 pages with sidebar), development blog (diary entries). Theme: dark library-photo hero transitioning to parchment for all content sections where app screenshots appear.

---

## Palette

| Token | Value | Usage |
|-------|-------|-------|
| `--ink` | `#1a1a2e` | Body text, footer bg, strong elements |
| `--ink-deep` | `#0d0d1e` | Hero bg overlay, darkest surfaces |
| `--gold` | `#c8a96e` | Accent: links, active states, eyebrow labels |
| `--parchment` | `#f5ede0` | Primary content bg |
| `--parchment-mid` | `#ede5d4` | Alternate content sections, cards |
| `--parchment-dark` | `#d4c4a8` | Borders, dividers |
| `--muted` | `#8a7a6a` | Body text on parchment |
| `--muted-dark` | `#6b6b8b` | Body text on dark |

Typography: Georgia serif for headings, system-ui for body.

---

## File Structure

```
docs/
  _config.yml
  _layouts/
    default.html       ← nav + footer chrome
    landing.html       ← extends default, custom landing
    doc.html           ← extends default, sidebar + content
    post.html          ← extends default, blog post with prev/next
  _includes/
    doc-sidebar.html   ← grouped sidebar nav
  assets/
    css/main.css       ← all styles
    img/
      hero-library.jpg ← Unsplash library photo (download at build)
  index.html           ← landing page (layout: landing)
  blog/
    index.html         ← blog listing page
  user-guide/          ← existing .md files, front matter added
  (existing images/ stays in user-guide/images/)
```

---

## Section 1: Landing Page (`index.html`)

### Hero (dark)
- Background: `hero-library.jpg` from Unsplash (`photo-1507842217343-583bb7270b66`) at `brightness(0.18) sepia(0.2)`
- Top nav: `Sparge` logo (gold, letter-spaced) left; `Docs · Blog · GitHub ↗` right; links in `--muted-dark`
- Centre stack:
  - Eyebrow: `BLOG MIGRATION TOOL` in gold, 10px tracked caps
  - H1: `Your blog archive,` / `beautifully migrated.` — Georgia, 48px, `--parchment`
  - Sub: one sentence descriptor — `--muted-dark`
  - CTAs: `⬇ Download` (gold filled) + `Read the docs →` (ghost, dark border)
- Stats strip (`--ink-deep`): 4 stats — `577 posts processed · 12 issue checks · 0 issues remaining · Mac · Win · Linux`

### Features (parchment `#f5ede0`)
- Section heading: `Everything your migration needs.`
- Alternating 2-col rows: feature text (icon + title + description) paired with app screenshot
- 3 rows covering: Ingest, Scan+Enrich, Generate+Validate

### Blog preview (`#ede5d4`)
- Heading: `Development diary.`
- 3 most recent posts as cards: date, title, excerpt, tag pill
- `Read all posts →` link

### Footer (`#1a1a2e`)
- Logo left, nav links centre, GitHub right
- `Built with Sparge` tagline

---

## Section 2: Docs Layout (`_layouts/doc.html`)

- **Sidebar** (200px, `#080810`): grouped nav sections — Getting Started / Pipeline / Editors / Reference. Active link: gold left-border + `#1a1a2e` bg. Links in `--muted-dark`, active in gold.
- **Content** (flex:1, parchment bg): renders existing Markdown. `h1` in `--ink` Georgia, `h2` in gold, body in `--muted`, screenshots display naturally on parchment bg.
- **Top nav**: same as landing but without hero
- Breadcrumb: `Docs > Section > Page`

Front matter added to all 12 existing `user-guide/*.md` files:
```yaml
---
layout: doc
title: "Page Title"
section: "Getting Started"   # or Pipeline / Editors / Reference
order: 1
---
```

Sidebar sections:
- **Getting Started:** Installation, First Project, Ingesting Posts
- **Pipeline:** The Pipeline, Working With Posts
- **Editors:** HTML Editor, Markdown Editor
- **Reference:** Issues Panel, Filtering & Search, Staging & Publishing, Checks & Validation, Features

---

## Section 3: Blog (`blog/index.html` + `_layouts/post.html`)

Front matter added to existing `docs/blog/*.md` files:
```yaml
---
layout: post
title: "Post Title"
date: 2026-04-10
excerpt: "One sentence summary."
tags: [Electron, Design]
---
```

- **Blog index:** full-width listing, cards with date / title / excerpt / tags. Sorted newest first.
- **Post layout:** max-width prose, Georgia for body text, gold headings, prev/next navigation.

---

## Publishing

GitHub Pages setting: **Branch `main`, folder `/docs`**.
`_config.yml`:
```yaml
baseurl: "/sparge"
url: "https://mdproctor.github.io"
title: Sparge
description: Blog migration tool
```

Hero image: downloaded from Unsplash and committed to `docs/assets/img/hero-library.jpg`. No external image dependency at runtime.
