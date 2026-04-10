# Checks, Validations & Autocorrects

Sparge runs checks and autocorrections at multiple pipeline stages. This page is a complete reference of everything it detects and fixes.

---

## At Ingest — autocorrects applied silently

These fixes are applied to every post during ingest. They're idempotent — running them multiple times produces the same result.

| Fix | What it does |
|-----|-------------|
| `<br/>` normalisation | Converts `<br/>` inside `<pre>` blocks to real newlines |
| Code block reformatting | Reformats one-liner DRL and XML code blocks with proper newlines |
| Span-tokenised code | Converts Blogger's `<span>rule</span><span>"Name"</span>` pattern to `<pre><code>` |
| `<p><br/>code</p>` blocks | Converts `<p>` blocks containing `<br/>`-separated code to `<pre><code>` |
| Line-number table code | Converts two-column line-number + code tables to `<pre><code>` |
| Image link localisation | Downloads `<a href>` image links and replaces with `<img>` tags |
| Imgur fallback | Geo-blocked imgur CDN addresses are fetched via the Wayback Machine |
| Wayback fallback | Any image that fails to download is retried via the Wayback Machine |

---

## At Enrich — applied on first scan

Enrichment runs automatically the first time you scan a post.

| Fix | What it does |
|-----|-------------|
| YouTube embed replacement | `<iframe>` YouTube embeds replaced with a local thumbnail image + link |
| Gist inlining | `<script src="gist.github.com/...">` tags fetched and replaced with `<pre><code>` |
| Code class normalisation | `brush: java`, `lang-java`, etc. normalised to `language-java` |
| Code block fixes (idempotent) | Same fixes as ingest applied again, in case HTML was modified after ingest |

---

## At Scan — HTML issue checks

These are *flagged* as issues, not auto-fixed. Review each one in the Issues Panel.

| Issue type | What it detects | Severity |
|-----------|----------------|---------|
| `data_uri` | Inline base64-encoded images (large, won't render in Jekyll) | Error |
| `tracking_pixel` | 1×1 pixel images from known tracking domains | Warning |
| `broken_local_ref` | `<img src="../../assets/...">` paths that don't resolve | Error |
| `external_image` | Images still pointing to remote URLs (not localised) | Error |
| `empty_embed` | YouTube or other embed containers with no content | Warning |
| `unreplaced_gist` | `<script src="gist.github.com/...">` that wasn't inlined | Error |
| `wordpress_chrome` | WordPress metadata, admin bars, share buttons, post navigation | Warning |
| `missing_image_signal` | Text like "as shown below" with no following image | Warning |
| `code_no_newlines` | Code blocks using `<br/>` instead of newlines | Warning |
| `potential_code_block` | `<p>` blocks that look like unformatted code | Warning |
| `linenumber_table_code` | Two-column line-number + code tables not converted at ingest | Warning |
| `imgur_image` | Images hosted on geo-blocked imgur CDN domains | Warning |

---

## At Generate MD — Markdown validation checks

These run automatically after Markdown generation and when you accept staged edits.

| Check | What it detects | Severity |
|-------|----------------|---------|
| Missing images | Images present in HTML but absent from generated Markdown | Error |
| Fence breaks | Unclosed or malformed code fences | Error |
| Garbling | UTF-8 double-encoding artifacts (`ÃÂÃÂ` patterns) | Error |
| Code block integrity | Fences with no language tag or truncated content | Warning |
| Cross-validation | Structural cross-check of Markdown against HTML source | Warning |

> **Note:** Errors must be resolved before a post can be considered clean. Warnings are advisory — review them but they may be acceptable depending on your content.
