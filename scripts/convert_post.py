#!/usr/bin/env python3
"""Convert a single KIE archive HTML post to clean Jekyll Markdown."""
import json, re, sys
from pathlib import Path
from bs4 import BeautifulSoup, Tag
import html2text

ROOT = Path('/Users/mdproctor/mdproctor.github.io')

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
    re.compile(r'addtoany|linkedin|twitter|facebook|reddit|tumblr', re.I),
    re.compile(r'View all posts', re.I),
    re.compile(r'mailto:'),
    re.compile(r'^\[?\s*Rules?\s*\]?\s*\[?\s*Article', re.I),
]

JUNK_LINES = [
    re.compile(r'^\[\]\(<https://www\.addtoany'),
    re.compile(r'^\[Post Comment\]'),
    re.compile(r'^## Author\s*$'),
    re.compile(r'^\* \!\[.*?\]\(/legacy/assets/images.*?\)\s*$'),
    re.compile(r'^\[Mark Proctor\].*?title="Mark Proctor"\)'),
    re.compile(r'^\[ View all posts \]'),
    re.compile(r'^\[ \]\(<mailto:'),
]


def convert_post(html_path: Path) -> str:
    sidecar = html_path.with_suffix('.json')
    meta = json.loads(sidecar.read_text())
    soup = BeautifulSoup(html_path.read_text(errors='replace'), 'lxml')
    article = soup.find('article')
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

    # Remove [class*="wpDiscuz"] and [class*="author"] manually
    for tag in list(article.find_all(True)):
        if not isinstance(tag, Tag): continue
        classes = ' '.join(tag.get('class', []))
        if any(k in classes.lower() for k in ('wpdiscuz', 'addtoany')):
            tag.decompose()

    # Remove author avatar links
    for a in list(article.find_all('a', href=re.compile(r'search_authors|/author/'))):
        img = a.find('img')
        if img:
            a.decompose()

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
        placeholder = BeautifulSoup(placeholder_html, 'lxml').body.next
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
        placeholder = BeautifulSoup(placeholder_html, 'lxml').body.next
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
        placeholder = BeautifulSoup(placeholder_html, 'lxml').body.next
        p.insert_after(placeholder)

    # ── Write placeholders back to the archive HTML so both views show them ──────
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
        code_text = target.get_text()
        # Zero-padded key with @@ delimiters — no key is a substring of another
        key = f'@@CODEBLOCK_{len(code_blocks):03d}@@'
        code_blocks[key] = (lang or '', code_text)
        from bs4 import BeautifulSoup as _BS
        repl = _BS(f'<p>{key}</p>', 'lxml').body.next
        pre.replace_with(repl)

    # Convert to Markdown
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
        fence = f'```{lang}\n{code_text.strip()}\n```'
        if key not in body:
            orphans.append(key)  # placeholder got dropped during html2text conversion
        body = body.replace(key, fence)
    # Safety net: warn if any placeholder was not found (indicates html2text ate it)
    if orphans:
        for key in orphans:
            _, code_text = code_blocks[key]
            body += f'\n\n> ⚠️ Code block could not be placed inline\n\n```\n{code_text.strip()}\n```'

    # Clean up Markdown line-by-line
    lines = []
    for line in body.splitlines():
        if any(p.match(line.strip()) for p in JUNK_LINES):
            continue
        lines.append(line)
    body = '\n'.join(lines)
    body = re.sub(r'\n{3,}', '\n\n', body).strip()

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
    html = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        ROOT / 'legacy/posts/mark-proctor/2006-05-31-what-is-a-rule-engine.html'
    )
    result = convert_post(html)
    out = ROOT / 'mark-proctor' / (html.stem + '.md')
    out.parent.mkdir(exist_ok=True)
    out.write_text(result, encoding='utf-8')
    print(f'Written: {out}')
