# Sparge Pipeline

Complete reference for how Sparge processes a blog post from raw HTML to publishable Markdown. Every stage, every check, every fix.

---

## Overview

Sparge processes posts through three immutable stages. Each stage reads from the previous stage's output and writes to its own folder. **The original HTML is never modified.**

```
[Ingest]         raw HTML + assets
    ↓
[Scan]           enriched HTML  (fixes applied)
    ↓
[Generate MD]    Markdown
```

A post can be at any stage. Later stages re-read earlier output, so re-running a stage is always safe.

---

## Stage 1 — Ingest

**Reads:** Live web URL (or local mirror)  
**Writes:** `{serve_root}/{source.posts_dir}/{slug}.html` + assets into `{serve_root}/{source.assets_dir}/`  
**State fields set:** `slug`, `title`, `date`, `author`, `original_url`, `ingested_at`

### What Ingest does

1. Fetches the post URL
2. Extracts article body (strips WordPress chrome, nav, comments, social widgets, tracking scripts)
3. Downloads all image assets referenced in the article to `{source.assets_dir}/`
4. Rewrites image `src` attributes to local relative paths
5. Writes the cleaned article HTML (with local image paths) as a standalone file

### What Ingest does NOT do

- Does not fix YouTube iframes — left as-is
- Does not inline Gist embeds — left as-is
- Does not run any validation checks
- Does not modify anything it has already ingested (idempotent on re-run)

---

## Stage 2 — Scan

**Reads:** `{source.posts_dir}/{slug}.html` (original)  
**Writes:** `{project_dir}/enriched/{slug}.html` (fixed copy)  
**State fields set:** `html.issues`, `html.checked_at`, `assets.*`, `enriched.*`

Scan is the fix-and-validate phase. It reads the original HTML, applies all known fixes, writes the enriched copy, then runs all validation checks against it.

### 2a — HTML Fixes (applied in order)

These are transformations applied to produce `enriched/{slug}.html`. The original is never touched.

| Fix | What it does | Output |
|---|---|---|
| **YouTube embed replacement** | Detects `<iframe>` with YouTube/youtube-nocookie src. Downloads thumbnail (`maxresdefault.jpg`, fallback `hqdefault.jpg`) to `{source.assets_dir}/`. Replaces iframe with `<figure class="video-embed"><a href="https://youtube.com/watch?v=..."><img src="...local-thumb..."><figcaption>▶ Watch on YouTube</figcaption></a></figure>` | Thumbnail locally stored; embed preserved as static linked image |
| **Gist embed inlining** | Detects `<script src="gist.github.com/...">`. Calls GitHub API to fetch file content. Replaces script tag with `<figure class="gist-embed"><figcaption><a href="...">View on GitHub Gist: {filename}</a></figcaption><pre><code class="language-{lang}">{content}</code></pre></figure>`. If fetch fails: replaces with archive-note linking to original. | Code inlined; fallback link if unavailable |
| **SyntaxHighlighter class normalisation** | Detects `brush:X` or `brush: X` classes on `<pre>` elements (WordPress SyntaxHighlighter format). Converts to `language-X` on both `<pre>` and inner `<code>`. Stale `brush:` tokens removed. | Language class set for highlight.js |
| **Code language detection** | For `<pre><code>` blocks with no language class, applies regex heuristics (Java imports/class patterns, XML declarations, SQL keywords, Python/JS/Bash/DRL patterns). Adds `language-X` to the `<code>` element. | Language class set where detectable |
| **Unknown embed fallback** | Any remaining `<iframe>`, `<object>`, or `<embed>` not matched by YouTube wrapping is replaced with `<figure class="live-embed">` containing an archive note and a link to the original src. | Embed preserved as link rather than silently removed |

**Gist GitHub token (optional):**  
Add `"github_token": "ghp_..."` to `config.json` to authenticate GitHub API calls. Without a token, the API allows 60 requests/hour — sufficient for small posts but likely to rate-limit on bulk re-scans of large blogs. With a token: 5,000 requests/hour. See [Setup — GitHub token](#setup--github-token) below.

### 2b — HTML Validation Checks

Run against the enriched HTML. Issues are stored in `state.html.issues`.

| Check | Level | What it detects |
|---|---|---|
| `data_placeholders` | ERROR | `data-src`, `data-lazy-src` or other `data-*` image src attributes that were never resolved — the real image URL was never recovered |
| `noscript_remnants` | WARN | Remaining `<noscript>` tags — signals lazy-load images that may not have been recovered |
| `external_images` | WARN | `<img src>` still pointing to an external URL — image not localised |
| `tracking_pixels` | WARN | `<img>` with 0×0 or 1×1 dimensions — tracking beacons |
| `missing_local_images` | ERROR | Local image path referenced in HTML but file does not exist on disk |
| `empty_embeds` | WARN | `<iframe>` or `<object>` with empty or missing `src` — embed content lost |
| `unreplaced_gists` | ERROR | `<script src="gist.github.com/...">` still present — Gist was not inlined |
| `wordpress_chrome` | WARN | Known WordPress UI fragments still present in article (share buttons, comment forms, etc.) |
| `missing_image_signals` | WARN | Text patterns indicating a previously-missing image placeholder is still in the content |

### 2c — Asset Checks

| Check | What it records |
|---|---|
| Total images referenced in HTML | `assets.total` |
| Images successfully localised (local path, file exists) | `assets.localised` |
| Images with broken local path (file missing) | `assets.broken` |

---

## Stage 3 — Generate MD

**Reads:** `{project_dir}/enriched/{slug}.html` if it exists; falls back to `{source.posts_dir}/{slug}.html`  
**Writes:** `{serve_root}/{output.md_dir}/{slug}.md`  
**State fields set:** `md.generated_at`, `md.html_hash`, `md.issues`

### What Generate MD does

1. Reads enriched HTML (or original if not yet scanned)
2. Converts HTML to Markdown: headings, lists, tables, links, images, code blocks
3. Detects code block languages from `class="language-X"` or `brush:X` attributes
4. Replaces any remaining unrecovered images with `> **Missing image**` blockquotes
5. Builds Jekyll front matter (`tags`, `author`, `date`)
6. Runs MD validation checks (see below)
7. Writes `.md` file

### MD Validation Checks

Run after generation. Issues stored in `state.md.issues`. Split into MD-only checks and cross-checks against the HTML source.

#### MD-only checks

| Check | Level | What it detects |
|---|---|---|
| `orphaned_placeholder` | ERROR | Code placeholder tokens left unreplaced in output |
| `stray_digit_after_fence` | ERROR | Digit immediately following closing code fence (malformed output) |
| `unbalanced_fences` | ERROR | Odd number of ` ``` ` fences — a code block is unclosed |
| `empty_code_blocks` | WARN | Code fences with no content |
| `missing_front_matter` | ERROR | File does not begin with `---` |
| `unclosed_front_matter` | ERROR | Front matter block never closed |
| `missing_fm_field` | ERROR | Required front matter field absent (`tags`, `author`, `date`) |
| `bad_date_format` | WARN | Date field not in `YYYY-MM-DD` format |
| `empty_title` | WARN | Title field very short or empty |
| `empty_body` | ERROR | Post body empty or near-empty after front matter |
| `wordpress_junk` | WARN | Known WordPress UI text present in MD body |
| `html_entities_in_body` | WARN | Raw HTML entities (`&amp;`, `&nbsp;`, etc.) in MD text |
| `relative_image_path` | WARN | Image path that won't resolve correctly in Jekyll |
| `broken_links` | WARN | Empty link targets `[text]()` |
| `excessive_blank_lines` | WARN | Three or more consecutive blank lines |
| `prose_in_code` | WARN | Natural-language sentences inside a code block |
| `duplicate_paragraph` | ERROR | Identical paragraph appears more than once (conversion artifact) |
| `excessive_line_length` | WARN | Lines substantially longer than standard Markdown wrapping |
| `many_missing_images` | WARN | High proportion of images replaced with missing-image blockquotes |
| `unknown_fence_language` | WARN | Code fence language tag not in known list |

#### Cross-checks (MD vs original HTML)

| Check | Level | What it detects |
|---|---|---|
| `code_blocks_dropped` | ERROR | HTML had code blocks; MD has fewer or none |
| `code_block_count_mismatch` | WARN | Code block count differs between HTML and MD |
| `code_content_missing` | ERROR | Specific code content present in HTML but absent from MD |
| `code_content_truncated` | WARN | Code content in MD is significantly shorter than HTML original |
| `language_tag_missing` | WARN | HTML code block had a language class; MD fence has none |
| `word_count_low` | WARN | MD word count is substantially lower than HTML — content likely dropped |
| `heading_missing` | WARN | Heading present in HTML not found in MD |
| `lists_dropped` | WARN | HTML had list items; MD has fewer |
| `links_dropped` | WARN | HTML had links; MD has fewer |
| `table_dropped` | WARN | HTML contained a table; MD has none |
| `truncated_at_end` | WARN | Last HTML section heading not present in MD — post cut short |
| `images_dropped` | WARN | Image count in MD lower than HTML |
| `youtube_links_dropped` | WARN | YouTube links present in HTML not found in MD |
| `technical_terms_missing` | WARN | Known technical terms from HTML (class names, API names) absent from MD |
| `blockquotes_dropped` | WARN | HTML blockquotes not present in MD |
| `content_phrase_missing` | WARN | Sample phrases from HTML paragraphs not found in MD — spot-check for dropped content |
| `chrome_leakage` | WARN | WordPress UI text (share, comments, etc.) found in MD body |

---

## Project configuration (`config.json`)

```json
{
  "project_name": "My Blog",
  "serve_root": "/path/to/repo",
  "source": {
    "posts_dir": "legacy/posts/author",
    "assets_dir": "legacy/assets"
  },
  "output": {
    "md_dir": "author-posts"
  },
  "filter": {
    "author": "Author Name"
  },
  "server": {
    "port": 9000
  },
  "github_token": ""
}
```

| Field | Required | Description |
|---|---|---|
| `project_name` | Yes | Display name shown in Sparge UI |
| `serve_root` | Yes | Absolute path to the root of the site repository |
| `source.posts_dir` | Yes | Path to original HTML posts, relative to `serve_root` |
| `source.assets_dir` | Yes | Path to image asset storage, relative to `serve_root` |
| `output.md_dir` | Yes | Path for generated Markdown files, relative to `serve_root` |
| `filter.author` | No | Only ingest posts by this author name |
| `server.port` | No | Port for the Sparge UI server (default: 9000) |
| `github_token` | No | GitHub personal access token for Gist API. See setup below. |

---

## Setup — GitHub token

Sparge inlines GitHub Gist embeds during Scan by calling the GitHub API. Without a token, GitHub allows **60 API requests per hour** (unauthenticated). For a blog with many Gist embeds scanned in bulk, this will rate-limit quickly.

With a token: **5,000 requests per hour**.

**When you need a token:** If your blog has more than ~50 posts with Gist embeds and you're running bulk scans. Sparge will warn you during Scan if it detects Gists but no token is configured.

**How to create a token:**

1. Go to GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click **Generate new token (classic)**
3. Give it a name (e.g. "Sparge Gist reader")
4. Select **no scopes** — Gists are public; no permissions needed
5. Click **Generate token** and copy it

**How to add it to Sparge:**

Open your project's `config.json` and add:

```json
"github_token": "ghp_xxxxxxxxxxxxxxxxxxxx"
```

The token is stored locally in your project config and never transmitted anywhere except the GitHub API.

---

## Folder layout (per project)

```
blog-migrator/projects/{project-id}/
  config.json          ← project configuration
  state.json           ← per-post state (all stages)
  enriched/            ← Stage 2 output: fixed HTML copies
    {slug}.html
    ...

{serve_root}/
  {source.posts_dir}/  ← Stage 1 output: original HTML (never modified)
    {slug}.html
    ...
  {source.assets_dir}/ ← images, thumbnails (managed by Ingest + Scan)
  {output.md_dir}/     ← Stage 3 output: Jekyll Markdown
    {slug}.md
    ...
```

---

## What is NOT yet in Sparge (planned)

These capabilities exist in the original `scripts/` tools and will be migrated in future sub-projects:

### Stage 1 — Ingest improvements

| Capability | Notes | Status |
|---|---|---|
| Content-hash image deduplication | Currently Sparge uses URL-hash for asset filenames. The original used content-hash (MD5 of bytes), so two URLs pointing to the same image share one file. Prevents duplicate assets. | Planned |
| Image download retry with exponential backoff | Sparge's `_download_asset()` has no retry. The original retried transient failures. Important for bulk ingest over slow connections. | Planned |
| MIME type validation of downloaded images | Validate magic bytes of downloaded files to catch HTML error pages saved as `.jpg`. Emit a WARN if the file is not a valid image. | Planned |

### Stage 2 — Scan/Enrich additions

| Capability | Notes | Status |
|---|---|---|
| `brush:X` → `language-X` class normalisation | WordPress SyntaxHighlighter used `brush:java` style classes on `<pre>` tags. Normalised to `language-java` before MD conversion. | **Done** |
| Language heuristics for unlabelled code blocks | Detect likely language of `<pre><code>` blocks with no class using content patterns. Adds `language-X` class for MD conversion. | **Done** |
| Non-YouTube, non-Gist embed fallback | Any `<iframe>` not matched as YouTube wrapped with `<figure class="live-embed">` rather than silently removed. | **Done** |
| SlideShare embed resolution | Resolve SlideShare embed URLs to page URL, download thumbnail, replace with thumbnail+link figure. The generic embed fallback above covers SlideShare with a link; a thumbnail-specific path can be added later. | Planned |
| External link dead-URL checking | Optional HEAD-request scan of all external links. Flags dead links as WARN. Slow — should be opt-in per scan run. | Planned |
| Unrecovered image URL export | After scan, export a report of all image URLs that could not be localised — for manual recovery via Yandex/Bing reverse image search. | Sub-project 2 |

### Stage 2 — Image recovery pipeline (Sub-project 2)

| Capability | Notes | Status |
|---|---|---|
| Lazy image recovery (noscript/data-src) | Recover images stored in `data-src` / `data-lazy-src` attributes or `<noscript>` siblings from lazy-load patterns. | Planned |
| Wayback Machine CDX recovery | Query CDX API (multi-timestamp, prefers closest to post date) rather than the simpler availability API. More robust. | Planned |
| archive.today as recovery source | Try archive.today as a second fallback after Wayback. | Planned |
| Cross-post source search | Search known syndication sites (Red Hat blog, DZone, Medium) for the same image by filename/path heuristic. | Planned |
| Playwright iframe recovery | Use headless browser to resolve JS-injected iframe `src` values that are empty in the static HTML. | Planned |
| Multi-strategy orchestration | Run all recovery strategies in sequence per image, stop at first success, report anything still unrecovered. | Planned |

### Stage 3 — Generate MD improvements

| Capability | Notes | Status |
|---|---|---|
| `cross_technical_terms` — configurable | Currently hardcoded to KIE terms (`drools`, `jbpm`, etc.). Must be configurable per project via `config.json` (`technical_terms: [...]`). Empty list = skip check. | Planned |
| Text fingerprint sanity check | After conversion, compare text fingerprint of enriched HTML vs MD body to catch silent content drops during conversion. Internal check, not user-visible issue. | Planned |

### Stage 3 — Export (Sub-project 3)

| Capability | Notes | Status |
|---|---|---|
| Static index.html export | Generate a standalone `index.html` grouping all posts by author/tag from project state. Useful for sharing the archive without running Sparge. | Planned |
| Enhanced review UI | Rendered post view with per-issue CSS highlighting — each flagged element outlined and labelled inline, click-to-scroll. Currently Sparge shows issues in a list only. | Planned |
