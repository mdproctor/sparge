#!/usr/bin/env python3
"""Convert a single KIE archive HTML post to clean Jekyll Markdown."""
import json, re, sys
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString, Tag
import html2text

JUNK_SELECTORS = [
    '.entry-header', 'header', '.entry-meta',
    '.author-box', '.author-description', '.author-info',
    '.addtoany_share_save_container', '.addtoany_share_save',
    '.sharedaddy', '#comments', '.comments-area',
    '.jp-relatedposts', '.post-navigation',
    '.wpdiscuz-form-container', 'script', 'style',
]

META_PATTERNS = [
    re.compile(r'^by\s', re.I),
    re.compile(r'Post Comment', re.I),
    re.compile(r'View all posts', re.I),
    re.compile(r'mailto:'),
    re.compile(r'^\[?\s*Rules?\s*\]?\s*\[?\s*Article', re.I),
]

# Social platform names are matched only when the element looks like a sharing
# widget — either short text (a widget label) OR the hrefs contain a sharing URL.
# Long paragraphs that merely *mention* Twitter/Facebook as a topic must not
# be stripped (e.g. "I've setup a twitter account to send updates").
_SOCIAL_PLATFORM_RE = re.compile(r'addtoany|linkedin|twitter|facebook|reddit|tumblr', re.I)
_SOCIAL_SHARE_URL_RE = re.compile(
    r'twitter\.com/intent|facebook\.com/sharer|linkedin\.com/share'
    r'|reddit\.com/submit|plus\.google\.com/share|t\.co/', re.I
)

JUNK_LINES = [
    # Note: bare [](<url>) lines are now stripped by prefix removal before this loop;
    # this pattern remains as a fallback for any that slip through.
    re.compile(r'^\[\]\(<https?://\s*$'),  # entire line is empty link — no content follows
    re.compile(r'^\[\]\(<https://www\.addtoany'),
    re.compile(r'^\[Post Comment\]'),
    re.compile(r'^## Author\s*$'),
    re.compile(r'^\* \!\[.*?\]\(/legacy/assets/images.*?\)\s*$'),
    re.compile(r'^\[Mark Proctor\].*?title="Mark Proctor"\)'),
    re.compile(r'^\[ View all posts \]'),
    re.compile(r'^\[ \]\(<mailto:'),
]


def convert_post(html_path: Path, json_path: Path | None = None) -> str:
    # json_path lets callers supply the sidecar from a different location
    # (e.g. when html_path is an enriched copy outside the original posts tree)
    sidecar = json_path if json_path is not None else html_path.with_suffix('.json')
    meta = json.loads(sidecar.read_text())
    soup = BeautifulSoup(html_path.read_text(errors='replace'), 'html.parser')
    article = soup.find('article') or soup.find('body')
    if not article:
        return None

    # Remove known junk selectors
    for sel in JUNK_SELECTORS:
        for el in article.select(sel):
            el.decompose()

    # Remove HTML comment blocks
    from bs4 import Comment
    for c in article.find_all(string=lambda t: isinstance(t, Comment)):
        c.extract()

    # Decode <pre><code> elements whose content is HTML-encoded markup.
    # Blogger and some CMSes HTML-encode table/div content when pasted into the
    # rich-text editor: <table> becomes &lt;table&gt; inside a <pre><code> block.
    # Decoding and replacing the block lets html2text convert the real HTML
    # rather than treating it as a verbatim code sample.
    # The check scan_html.suspicious_code_content flags these for human review;
    # this pipeline step handles them automatically during conversion.
    import html as _html
    _ENCODED_TAG_RE = re.compile(r'&lt;(?:table|div|p|span|ul|ol|tr|td|th)\b', re.I)
    for pre in list(article.find_all('pre')):
        if not isinstance(pre, Tag): continue
        code = pre.find('code')
        if not isinstance(code, Tag): continue
        raw_content = str(code)
        if _ENCODED_TAG_RE.search(raw_content):
            # Decode and replace the pre>code block with the real HTML
            decoded = _html.unescape(code.get_text())
            # Strip layout spacer images from the decoded content
            decoded = re.sub(r'<img[^>]*spacer[^>]*/?>',  '', decoded, flags=re.I)
            decoded = re.sub(r'<img[^>]+height=["\']?[01]["\']?[^>]+alt=["\']?["\']?[^>]*/?>',
                             '', decoded, flags=re.I)
            fragment = BeautifulSoup(decoded, 'html.parser')
            pre.replace_with(fragment)

    # Unwrap <blockquote> elements used as indentation wrappers (not semantic quotes).
    # Old blog HTML uses <blockquote> for visual indent — the entire book description,
    # feature lists, chapter summaries, etc. are wrapped in <blockquote> purely for
    # the indentation effect.  html2text converts this to "> content" — the ">"
    # blockquote prefix appears throughout the MD as visual noise.
    #
    # Detection: indentation blockquotes have NO class attribute and NO <cite> child
    # (semantic blockquotes quoting a person use <cite> for attribution).
    # We also skip our own missing-image placeholder blockquotes.
    for bq in list(article.find_all('blockquote')):
        if not isinstance(bq, Tag): continue
        if 'missing-image' in ' '.join(bq.get('class', [])):
            continue
        if bq.get('class'):          # styled blockquote — keep
            continue
        if bq.find('cite'):          # has attribution — semantic quote, keep
            continue
        bq.unwrap()                  # plain indentation wrapper — remove the box

    # Remove [class*="wpDiscuz"] and [class*="author"] manually
    for tag in list(article.find_all(True)):
        if not isinstance(tag, Tag): continue
        classes = ' '.join(tag.get('class', []))
        if any(k in classes.lower() for k in ('wpdiscuz', 'addtoany')):
            tag.decompose()

    # Remove author avatar links (wrapped in search_authors/<a> element)
    for a in list(article.find_all('a', href=re.compile(r'search_authors|/author/'))):
        img = a.find('img')
        if img:
            a.decompose()

    # Remove bare author portrait images — appear inline inside content divs as
    # CMS template chrome.  The CMS inserts the author's profile photo alongside
    # real content; we detect it by matching the img alt text against the author name.
    # This is universal: any CMS that embeds author portraits with the author's name
    # as alt text will have these stripped correctly.
    author_name = (meta.get('author', '') or '').strip().lower()
    if author_name:
        for img in list(article.find_all('img')):
            alt = (img.get('alt', '') or '').strip().lower()
            if alt == author_name:
                img.decompose()

    # Remove h2 "Author" and everything after it
    for h in list(article.find_all(['h2', 'h3'])):
        if h.get_text(strip=True).lower() in ('author', 'related posts', 'feedback', 'share'):
            for sib in list(h.find_next_siblings()):
                sib.decompose()
            h.decompose()
            break

    # Remove metadata-looking short paragraphs (any element)
    for tag in list(article.find_all(['p', 'div', 'span'])):
        if not isinstance(tag, Tag): continue
        text_nospace = tag.get_text(strip=True)
        text = tag.get_text(separator=' ', strip=True)  # spaces between elements
        hrefs = ' '.join(a.get('href', '') for a in tag.find_all('a'))
        combined = text + ' ' + hrefs

        # For divs with substantial real content, only remove if text STARTS with metadata
        # (avoids removing content containers that happen to have metadata children)
        if tag.name == 'div' and len(text_nospace) > 120:
            # Only catch divs that start with "by" metadata pattern
            if re.match(r'^by\b', text) and len(text_nospace) < 300:
                tag.decompose()
            continue

        if len(text_nospace) < 500 and any(p.search(combined) for p in META_PATTERNS):
            tag.decompose()
            continue
        # Social platform names: only strip when the element is clearly a sharing widget.
        # Two signals: (1) a known sharing URL in the hrefs, or (2) very short text with
        # a platform name and NO external links (a bare label like "Share on Twitter").
        # Profile links (twitter.com/username) and content paragraphs that mention social
        # platforms as a topic must NOT be stripped.
        if _SOCIAL_PLATFORM_RE.search(combined):
            is_sharing_url  = _SOCIAL_SHARE_URL_RE.search(hrefs)
            is_bare_label   = len(text_nospace) < 50 and not hrefs
            if is_sharing_url or is_bare_label:
                tag.decompose()
                continue
        # Catch "by Author - Date Category" pattern
        if re.match(r'^by\b', text) and len(text_nospace) < 300:
            tag.decompose()

    # Remove duplicate h3 title
    title_start = meta.get('title', '')[:20].lower()
    for h3 in list(article.find_all('h3')):
        if title_start and title_start[:12] in h3.get_text(strip=True).lower():
            h3.decompose()

    # Fix image paths
    for img in article.find_all('img'):
        if not isinstance(img, Tag) or not isinstance(img.attrs, dict): continue
        src = img.get('src', '')
        if src.startswith('data:'):
            img.decompose()
        elif src.startswith('../../assets/'):
            img['src'] = '/legacy/' + src.replace('../../', '')

    # Fix local hrefs
    for a in article.find_all('a', href=True):
        if a['href'].startswith('../../assets/'):
            a['href'] = '/legacy/' + a['href'].replace('../../', '')

    # Remove empty tags
    changed = True
    while changed:
        changed = False
        for tag in list(article.find_all(['p', 'div', 'span', 'li'])):
            if not isinstance(tag, Tag): continue
            if not tag.get_text(strip=True) and not tag.find('img'):
                tag.decompose(); changed = True

    # ── Step: Replace remaining data: placeholders with styled missing-image boxes ──
    # These are images that couldn't be recovered; look at surrounding text for context
    MISSING_IMG_SIGNALS = [
        re.compile(r'as shown (below|above|here)', re.I),
        re.compile(r'(see|view) (the )?(image|screenshot|figure|diagram|chart|graph|photo) (below|above)', re.I),
        re.compile(r'(the )?(following|below) (image|screenshot|figure|diagram|chart|graph) shows?', re.I),
        re.compile(r'(image|screenshot|figure|diagram|chart|graph|photo):?\s*$', re.I),
        re.compile(r'(click (to )?(enlarge|zoom|view))', re.I),
    ]

    # Find ALL noscript tags with unrecovered http image URLs
    # and ALL data: placeholder imgs without any noscript sibling
    # Group by their outermost container to avoid duplicates
    handled = set()

    # Pass 1: noscript-based missing images (data: main img + noscript with http URL)
    for ns in list(article.find_all('noscript')):
        if id(ns) in handled: continue
        ns_img = ns.find('img')
        if not isinstance(ns_img, Tag): continue
        ns_src = ns_img.get('src', '')
        if not ns_src.startswith('http'): continue

        # Walk up to find the best replacement target
        target = ns
        if isinstance(ns.parent, Tag) and ns.parent.name == 'a':
            target = ns.parent
        if isinstance(target.parent, Tag) and target.parent.name in ('figure', 'div') and len([
            c for c in target.parent.children if isinstance(c, Tag)]) <= 2:
            target = target.parent

        handled.add(id(ns)); handled.add(id(target))

        fname = ns_src.split('/')[-1].split('?')[0]
        suggestion = fname.replace('-',' ').replace('_',' ')
        for ext in ('.png','.jpg','.gif','.jpeg','.webp','.svg'): suggestion = suggestion.replace(ext,'')
        if not suggestion.strip(): suggestion = 'content image'

        placeholder_html = (
            f'<blockquote class="missing-image"><strong>📷 Missing image</strong> — '
            f'<em>{suggestion.strip()}</em></blockquote>'
        )
        placeholder = BeautifulSoup(placeholder_html, 'html.parser').find()
        target.replace_with(placeholder)

    # Pass 2: standalone data: placeholder imgs (no noscript sibling)
    for img in list(article.find_all('img')):
        if not isinstance(img, Tag) or not isinstance(img.attrs, dict): continue
        src = img.get('src', '')
        if not src.startswith('data:'): continue
        if id(img) in handled: continue

        # Gather context: preceding paragraph text + alt text + noscript hint
        context_parts = []
        alt = img.get('alt', '').strip()
        if alt and alt.lower() not in ('', 'image', 'photo', 'screenshot'):
            context_parts.append(alt)

        # Check noscript sibling for original URL hint
        ns = img.find_next_sibling()
        orig_url_hint = ''
        if isinstance(ns, Tag) and ns.name == 'noscript':
            m = re.search(r'src=["\' ](https?://[^"\'>\s]+)["\' ]', str(ns))
            if m:
                fname = m.group(1).split('/')[-1].split('?')[0]
                if fname and len(fname) > 3:
                    orig_url_hint = fname.replace('-', ' ').replace('_', ' ').replace('.png','').replace('.jpg','').replace('.gif','')
                    context_parts.append(orig_url_hint)

        # Check surrounding text for image description cues
        prev_text = ''
        prev = img.find_previous_sibling()
        if isinstance(prev, Tag):
            prev_text = prev.get_text(strip=True)
        elif img.parent and isinstance(img.parent, Tag):
            prev_text = img.parent.get_text(strip=True)[:200]

        # Build suggestion text
        if context_parts:
            suggestion = ', '.join(context_parts)
        elif prev_text:
            # Use last sentence of preceding text as hint
            sentences = re.split(r'[.!?]', prev_text)
            hint = [s.strip() for s in sentences if s.strip()][-1:][0] if sentences else ''
            suggestion = hint[:80] if hint else 'content image'
        else:
            suggestion = 'content image'

        # Create placeholder box
        placeholder_html = (
            f'<blockquote class="missing-image"><strong>📷 Missing image</strong> — '
            f'<em>{suggestion}</em></blockquote>'
        )
        placeholder = BeautifulSoup(placeholder_html, 'html.parser').find()
        # Replace the outermost wrapping element (figure > a > img, or a > img, or just img)
        target = img
        if isinstance(img.parent, Tag) and img.parent.name == 'a':
            target = img.parent
        if isinstance(target.parent, Tag) and target.parent.name in ('figure', 'p', 'div'):
            # Check if parent only contains this element (and noscript)
            siblings = [s for s in target.parent.children
                        if isinstance(s, Tag) and s.name not in ('noscript',)]
            if len(siblings) <= 1:
                target = target.parent
        target.replace_with(placeholder)
        # Clean up any orphaned noscript
        if isinstance(ns, Tag) and ns.name == 'noscript' and ns.parent:
            ns.decompose()

    # ── Step: Detect language patterns suggesting an image should follow ──────────
    # Insert placeholder after paragraphs that end with image-indicating language
    # but are NOT followed by an image
    for p in article.find_all(['p', 'div']):
        if not isinstance(p, Tag): continue
        text = p.get_text(strip=True)
        if not text or len(text) > 300: continue
        if not any(sig.search(text) for sig in MISSING_IMG_SIGNALS): continue
        # Skip if the element itself contains an image — text is a caption,
        # not a dangling reference to a missing image.
        if p.find('img'): continue
        # Check if next sibling is already an image or placeholder
        nxt = p.find_next_sibling()
        if nxt and isinstance(nxt, Tag):
            if nxt.name in ('img', 'figure') or 'missing-image' in nxt.get('class', []):
                continue
            if nxt.find('img'): continue
        # Insert a placeholder
        placeholder_html = (
            f'<blockquote class="missing-image"><strong>📷 Missing image</strong> — '
            f'<em>{text[:80]}</em></blockquote>'
        )
        placeholder = BeautifulSoup(placeholder_html, 'html.parser').find()
        p.insert_after(placeholder)

    # ── Strip navigation <a href> links from inside heading elements ───────────
    # DocBook/CMS HTML often makes heading text a link back to the blog URL:
    #   <h4><a href="http://blog.athico.com/">Section Name</a></h4>
    # html2text converts this to: #### [Section Name](<url>)
    # The link carries no useful information and pollutes the MD output.
    # Unwrapping these <a> elements inside headings gives clean heading text.
    for hd in article.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        for a in hd.find_all('a'):
            a.unwrap()

    # ── Unwrap navigation-only <a href> links that wrap block or inline content ──
    # CMS/DocBook platforms often wrap every section or paragraph in <a href="blog-url">
    # for navigation purposes.  These produce markdown link artifacts:
    #   "[text](<url>)"  or  "[](<url>)"
    #
    # Detection strategy — generic, no domain hardcoding:
    #   1. Block-level wrappers: <a> whose direct Tag children are all block elements.
    #      These are NEVER real content links (real links are inline).
    #   2. Repeated-href links: any href appearing 5+ times in the article is a
    #      navigation template, not a real external link.  Real content links rarely
    #      repeat that many times; nav templates do (e.g. 119× blog.athico.com).
    from collections import Counter
    href_counts = Counter(
        a.get('href', '') for a in article.find_all('a')
        if (a.get('href', '') or '').startswith('http')
    )
    nav_hrefs = {href for href, count in href_counts.items() if count >= 5}

    block_tags = {'div', 'pre', 'table', 'p', 'ul', 'ol',
                  'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
    for a in list(article.find_all('a')):
        if not isinstance(a, Tag): continue
        href = a.get('href', '')
        children = [c for c in a.children if isinstance(c, Tag)]
        if children and all(c.name in block_tags for c in children):
            # Block-level wrapper — always a navigation/template artifact
            a.unwrap()
        elif 'linkurl=' in href or 'link_url=' in href:
            # Social sharing widget — any platform (addtoany, sharethis, buffer…)
            # embeds the target URL as a ?linkurl= query parameter.
            # Remove the entire element: the label text (Facebook, Twitter…)
            # has no value without the link.
            a.decompose()
        elif 'send_to_friend' in href or 'sendtofriend' in href.lower():
            # Email-marketing "Forward this message to a friend" links from
            # newsletter platforms (vresp.com, mailchimp, etc.).  These appear in
            # blog posts that were originally distributed as email newsletters —
            # the link is template chrome with no value in an archived context.
            parent = a.parent
            a.decompose()
            # Remove the containing <p> if it is now empty
            if isinstance(parent, Tag) and not parent.get_text(strip=True):
                parent.decompose()
        elif href in nav_hrefs:
            # Repeated-href link — navigation template, not a real content link
            if a.get_text(strip=True):
                a.unwrap()
            else:
                a.decompose()

    # ── Write the cleaned HTML back to the archive file ───────────────────────
    # This is done AFTER all content-preserving transforms (placeholder insertion,
    # heading-link unwrap, nav-link removal) but BEFORE the markdown-only transforms
    # (code-block placeholder substitution, inline trailing-space reordering).
    # Writing before code extraction is critical: the @@CODEBLOCK_nnn@@ strings are
    # temporary markdown artefacts and must never appear in the archive HTML.
    #
    # MIGRATION NOTE (Quarkus/Java): This write uses html_path which may be either
    # the enriched copy (sparge-projects/.../enriched/{slug}.html) or the original
    # archive file (legacy/posts/{author}/{slug}.html), depending on which exists.
    # In Java, use the same resolution logic: enriched copy takes priority.
    updated_html = str(soup)
    if not updated_html.startswith('<!DOCTYPE'):
        updated_html = '<!DOCTYPE html>\n' + updated_html
    html_path.write_text(updated_html, encoding='utf-8')

    # ── Replace <pre><code class="language-X"> with fenced code block placeholders ──
    # html2text produces 4-space indented blocks which lose language info.
    # We extract code blocks before conversion and restore them as ```lang fences.
    #
    # LESSON LEARNED: Never use numeric-suffix keys like FENCE_0, FENCE_1 because
    # str.replace('FENCE_1', ...) partially matches 'FENCE_10', 'FENCE_11' etc.,
    # leaving stray digits in the output. Use unique delimiters that cannot
    # appear in normal text and cannot be partial-matched by any other key.
    # Format: @@CODEBLOCK_nnn@@ where nnn is zero-padded to 3 digits.
    # Zero-padding + @@ delimiters make every key a fixed-width unique string —
    # no key is a substring of any other key.
    code_blocks = {}  # placeholder_key -> (lang, code_text)

    for pre in list(article.find_all('pre')):
        if not isinstance(pre, Tag): continue
        code_el = pre.find('code')
        target = code_el if code_el else pre
        classes = target.get('class', [])
        lang = next((c.replace('language-', '') for c in classes if c.startswith('language-')), None)
        # Replace <br/> tags with newlines before get_text() so that Blogger-style
        # <pre> blocks that use <br/> for line breaks preserve their structure.
        # get_text() silently drops all tags including <br/>, collapsing every line.
        for br in target.find_all('br'):
            br.replace_with('\n')
        code_text = target.get_text()
        # Normalise non-breaking spaces (\xa0) introduced by html2text inside code.
        # They break syntax highlighters (tokenisers treat \xa0 as non-identifier chars).
        code_text = code_text.replace('\xa0', ' ')
        # Remap language tags that are obviously wrong for their content.
        # DocBook XSLT sometimes assigns 'sql' as a default to Java programlistings.
        if lang == 'sql' and re.search(r'\b(class|import|public|void|new|return|throws|interface|extends|implements)\b', code_text):
            lang = 'java'
        # Zero-padded key with @@ delimiters — no key is a substring of another
        key = f'@@CODEBLOCK_{len(code_blocks):03d}@@'
        code_blocks[key] = (lang or '', code_text)
        from bs4 import BeautifulSoup as _BS
        repl = _BS(f'<p>{key}</p>', 'html.parser').find()
        pre.replace_with(repl)

    # Move trailing whitespace from inside inline elements to after the closing tag.
    # html2text strips trailing whitespace inside bold/italic markers (via an
    # internal data.strip() on the stressed text node), so:
    #   <b>Name </b>(Org)  →  **Name**(Org)   ← space lost
    # By moving the space to AFTER the tag before html2text sees it:
    #   <b>Name</b> (Org)  →  **Name** (Org)  ← space preserved
    # This only runs when there actually IS trailing whitespace inside the tag —
    # <b>Name</b>(Org) (no space) is left unchanged, producing **Name**(Org).
    for tag in list(article.find_all(['b', 'strong', 'em', 'i',
                                      'del', 's', 'strike', 'code', 'u', 'a'])):
        if not isinstance(tag, Tag) or not tag.contents:
            continue
        last = tag.contents[-1]
        if isinstance(last, NavigableString):
            stripped = str(last).rstrip()
            trailing = str(last)[len(stripped):]
            if trailing:
                last.replace_with(NavigableString(stripped))
                sib = tag.next_sibling
                if isinstance(sib, NavigableString):
                    sib.replace_with(NavigableString(trailing + str(sib)))
                else:
                    tag.insert_after(NavigableString(trailing))

    # Convert to Markdown
    # MIGRATION NOTE (Quarkus/Java): html2text has no direct Java equivalent.
    # The closest is flexmark-java (HtmlToMarkdown) or commonmark-java.
    # Critical flags and their effects — ALL md_validator.py cross-checks depend on these:
    #
    #   protect_links=True   → links rendered as [text](<url>) WITH angle brackets.
    #                          EVERY validator regex that searches for links uses \]\(<
    #                          (e.g. lines 559, 672, 674 in md_validator.py).  If the
    #                          Java generator uses [text](url) without brackets, ALL
    #                          phrase/link cross-checks will silently fail to strip links
    #                          before comparison, producing widespread false positives.
    #
    #   unicode_snob=True    → preserves Unicode characters (em-dashes, curly quotes)
    #                          rather than converting them to ASCII approximations.
    #
    #   body_width=0         → no line-wrapping. The MD validator regex patterns assume
    #                          no hard line breaks mid-sentence.
    #
    #   wrap_links=False     → link URLs are not wrapped onto a new line. Validators
    #                          search for phrase text that may directly precede a link.
    #
    #   ignore_links=False   → links are preserved (not stripped). The validator's
    #                          cross_link_count check expects link counts to be preserved.
    #
    # Also note: html2text's internal `stressed` flag (set True on bold/italic open)
    # calls data.strip() on the first text node inside the element, eating trailing
    # spaces (see the trailing-space DOM fix above).  This is an undocumented internal
    # behaviour — only discoverable by reading html2text/__init__.py source.
    # ── Step: Ensure <figcaption> renders on its own line in MD ─────────────
    # html2text does not insert a newline between <img> and <figcaption> inside
    # a <figure>, so "![alt](src)" and the caption text run together on one line.
    # Adding <br/> between them forces html2text to emit a line break.
    for fig in article.find_all('figure'):
        cap = fig.find('figcaption')
        img = fig.find('img')
        if cap and img:
            img.insert_after(BeautifulSoup('<br/>', 'html.parser'))

    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = False
    h.body_width = 0
    h.unicode_snob = True
    h.protect_links = True
    h.wrap_links = False

    body = h.handle(str(article)).strip()

    # Restore fenced code blocks.
    # Keys are @@CODEBLOCK_nnn@@ — fixed width, delimited — safe to replace in any order.
    orphans = []
    for key, (lang, code_text) in code_blocks.items():
        # Use a fence longer than any backtick run inside the code so embedded
        # backtick sequences can never close the fence prematurely.
        max_run = max((len(m) for m in re.findall(r'`+', code_text)), default=0)
        fence_len = max(3, max_run + 1)
        fence_mark = '`' * fence_len
        # Surround with blank lines so the fence is always block-level, even when
        # html2text rendered the placeholder inline (e.g. inside a DocBook-style
        # [Example N. title @@KEY@@] wrapper).  The re.sub below normalises excess \n.
        fence = f'\n\n{fence_mark}{lang}\n{code_text.strip()}\n{fence_mark}\n\n'
        if key not in body:
            orphans.append(key)  # placeholder got dropped during html2text conversion
        body = body.replace(key, fence)
    # Safety net: warn if any placeholder was not found (indicates html2text ate it)
    if orphans:
        for key in orphans:
            _, code_text = code_blocks[key]
            body += f'\n\n> ⚠️ Code block could not be placed inline\n\n```\n{code_text.strip()}\n```'

    # Strip [](<url>) empty-link artifacts from the start of lines.
    # html2text renders empty <a href="url"> anchors (no text) as [](<url>).
    # When multiple appear at the start of a line before real content —
    # e.g. [](<url>)[](<url>)A recent Decision Modeling Day... — the JUNK_LINES
    # pattern would remove the entire line and lose the real paragraph.
    # Stripping the prefix here preserves the following content.
    body = re.sub(r'^(?:\[\]\(<https?://[^)]*>\))+\s*', '', body, flags=re.MULTILINE)

    # Clean up Markdown line-by-line
    lines = []
    for line in body.splitlines():
        if any(p.match(line.strip()) for p in JUNK_LINES):
            continue
        # Convert lines of pure '=' used as visual separators to proper HR.
        # IMPORTANT: both '===' and '---' after text create setext headings in Markdown.
        # A blank line BEFORE '---' is required to make it an unambiguous <hr>.
        # We append an empty line first, then '---', ensuring the preceding text
        # ends its paragraph before the horizontal rule begins.
        if re.match(r'^={4,}\s*$', line.strip()):
            lines.append('')   # blank line prevents setext heading interpretation
            lines.append('---')
            continue
        lines.append(line)
    body = '\n'.join(lines)
    body = re.sub(r'\n{3,}', '\n\n', body).strip()

    # Remove blank/whitespace-only lines within Markdown table blocks.
    # html2text inserts blank lines between rows of complex HTML tables
    # (spacer rows, rows with <br/> content). These break MD table rendering —
    # marked.js requires all rows to be contiguous with no blank lines.
    # A blank line is considered "within a table" when both the nearest non-blank
    # lines before and after it contain a pipe character ('|').
    def _collapse_table_blanks(text):
        lines = text.splitlines()
        result = []
        for i, line in enumerate(lines):
            if not line.strip():
                # Look backwards for the nearest non-blank line
                prev_pipe = any(
                    '|' in lines[j]
                    for j in range(i - 1, max(-1, i - 10), -1)
                    if lines[j].strip()
                )
                # Look forwards for the nearest non-blank line
                next_pipe = any(
                    '|' in lines[j]
                    for j in range(i + 1, min(len(lines), i + 10))
                    if lines[j].strip()
                )
                if prev_pipe and next_pipe:
                    continue  # drop this blank line — it's inside a table
            result.append(line)
        return '\n'.join(result)
    body = _collapse_table_blanks(body)

    # Build front matter
    title = meta.get('title', '')
    title = re.sub(r'\s*[-–]\s*KIE Community\s*$', '', title).strip()
    title = title.replace('"', '\\"')
    date = meta.get('date', '')[:10]
    cats = [str(c).strip() for c in meta.get('categories', []) if str(c).strip()]
    tags = [str(t).strip() for t in meta.get('tags', []) if str(t).strip()]
    original_url = meta.get('original_url', '')

    def yaml_list(items):
        if not items: return '[]'
        return '\n' + '\n'.join(f'  - {i}' for i in items)

    fm = (f'---\n'
          f'layout: post\n'
          f'title: "{title}"\n'
          f'date: {date}\n'
          f'author: Mark Proctor\n'
          f'categories: {yaml_list(cats)}\n'
          f'tags: {yaml_list(tags)}\n'
          f'original_url: {original_url}\n'
          f'---\n\n')

    # ── Validate the generated Markdown against both MD and original HTML ────
    try:
        from md_validator import validate
        from issues_list import add_validation_issues, remove as remove_issue
        issues = validate(fm + body, html_path.stem, html_path=html_path)
        for issue in issues:
            print(f'  ⚠ {issue}')
        title = meta.get('title', html_path.stem)
        if issues:
            add_validation_issues(html_path.stem, title, issues)
        else:
            remove_issue(html_path.stem)  # clean — remove from issues list
    except ImportError:
        pass  # validator not available

    return fm + body


if __name__ == '__main__':
    from scripts.config import cfg
    _root = cfg['_root']
    html = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        _root / 'legacy/posts/mark-proctor/2006-05-31-what-is-a-rule-engine.html'
    )
    result = convert_post(html)
    out = _root / 'mark-proctor' / (html.stem + '.md')
    out.parent.mkdir(exist_ok=True)
    out.write_text(result, encoding='utf-8')
    print(f'Written: {out}')
