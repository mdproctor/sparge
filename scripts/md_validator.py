#!/usr/bin/env python3
"""
MD Validation Suite — maximum fidelity checks for HTML→Markdown transformation.
Cross-validates MD against the original HTML archive when available.

Every check documents the lesson or failure mode that motivated it.
Add new checks whenever a new class of corruption is discovered.

Usage:
    from md_validator import validate
    issues = validate(md_content, slug, html_path=Path("..."))

CLI:
    python3 scripts/md_validator.py               # all existing MD+HTML pairs
    python3 scripts/md_validator.py path/to.md    # specific file
"""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class Issue:
    level: str      # 'ERROR' or 'WARN'
    check: str
    detail: str

    def __str__(self):
        return f'[{self.level}] {self.check}: {self.detail}'


def validate(md: str, slug: str = '', html_path: Optional[Path] = None) -> List[Issue]:
    issues = []
    for fn in MD_CHECKS:
        issues.extend(fn(md, slug))
    if html_path and html_path.exists():
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_path.read_text(errors='replace'), 'lxml')
            article = soup.find('article') or soup.find('body')
            if article:
                # Strip scripts/noscripts from article for all cross-checks
                for t in article.find_all(['script', 'style', 'noscript']): t.decompose()
                for fn in CROSS_CHECKS:
                    issues.extend(fn(md, slug, article))
        except Exception as e:
            issues.append(Issue('WARN', 'cross_check_error', f'Could not load HTML: {e}'))
    return issues


def _body(md):
    """Return body after front matter."""
    parts = md.split('\n---\n', 1)
    return parts[1] if len(parts) > 1 else md


def _article_words(article):
    return re.sub(r'\s+', ' ', article.get_text()).strip().split()


# ══════════════════════════════════════════════════════════════════════════════
# MD-ONLY CHECKS
# ══════════════════════════════════════════════════════════════════════════════

def chk_orphaned_placeholders(md, slug):
    """Unreplaced @@CODEBLOCK_nnn@@ or CODEBLOCK_FENCE_N means code is missing."""
    found = re.findall(r'@@CODEBLOCK_\d+@@|CODEBLOCK_FENCE_\d+', md)
    if found:
        return [Issue('ERROR', 'orphaned_placeholder', f'Unreplaced code placeholders: {found[:3]}')]
    return []


def chk_stray_digit_after_fence(md, slug):
    """Partial-replacement bug leaves digit after closing fence (e.g. ```0)."""
    stray = re.findall(r'^```\d', md, re.MULTILINE)
    if stray:
        return [Issue('ERROR', 'stray_digit_after_fence', f'Fence followed by digit: {stray[:3]}')]
    return []


def chk_balanced_fences(md, slug):
    """Odd number of ``` = unclosed block = rest of doc renders as code."""
    fences = re.findall(r'^```', _body(md), re.MULTILINE)
    if len(fences) % 2 != 0:
        return [Issue('ERROR', 'unbalanced_fences', f'Odd fence count ({len(fences)}) — block unclosed')]
    return []


def chk_empty_code_blocks(md, slug):
    """Empty fenced blocks (``` immediately followed by ```) add noise."""
    empties = re.findall(r'^```\w*\n```', md, re.MULTILINE)
    if empties:
        return [Issue('WARN', 'empty_code_blocks', f'{len(empties)} empty code block(s)')]
    return []


def chk_front_matter_valid(md, slug):
    """Missing/malformed Jekyll front matter causes post to be skipped."""
    issues = []
    if not md.startswith('---\n'):
        return [Issue('ERROR', 'missing_front_matter', 'MD does not start with ---')]
    end = md.find('\n---\n', 4)
    if end < 0:
        return [Issue('ERROR', 'unclosed_front_matter', 'Front matter never closed')]
    fm = md[4:end]
    for field in ('title:', 'date:', 'author:'):
        if field not in fm:
            issues.append(Issue('ERROR', 'missing_fm_field', f'Required field missing: {field}'))
    # Date format
    date_m = re.search(r'^date:\s*(\S+)', fm, re.MULTILINE)
    if date_m and not re.match(r'^\d{4}-\d{2}-\d{2}$', date_m.group(1)):
        issues.append(Issue('WARN', 'bad_date_format', f'Date not YYYY-MM-DD: {date_m.group(1)}'))
    # Title not empty
    title_m = re.search(r'^title:\s*"?(.+)"?\s*$', fm, re.MULTILINE)
    if title_m and len(title_m.group(1).strip()) < 3:
        issues.append(Issue('WARN', 'empty_title', 'Title is very short or empty'))
    return issues


def chk_empty_body(md, slug):
    """Over-aggressive cleaning can strip all body content."""
    body = _body(md)
    if len(body.strip()) < 20:
        return [Issue('ERROR', 'empty_body', 'Post body is empty or near-empty')]
    return []


def chk_wordpress_junk(md, slug):
    """WordPress/Blogger metadata must be stripped by the converter."""
    body = _body(md)
    JUNK = [
        (r'^by [A-Z]\w+ [A-Z]\w+\s*$', 'WordPress byline'),
        (r'\[View all posts\]', 'WordPress author link'),
        (r'\[Post Comment\]', 'Blogger comment link'),
        (r'addtoany|AddToAny', 'Social sharing markup'),
        (r'\[Rules\]\(https://blog\.kie\.org/category', 'Category link'),
    ]
    return [Issue('WARN', 'wordpress_junk', f'{label} in body')
            for p, label in JUNK if re.search(p, body, re.MULTILINE)]


def chk_html_entities_in_body(md, slug):
    """Raw HTML entities (&amp; &lt; etc.) should be decoded, not left as-is."""
    body = _body(md)
    # Exclude code blocks
    no_code = re.sub(r'```.*?```', '', body, flags=re.DOTALL)
    entities = re.findall(r'&(amp|lt|gt|quot|apos|nbsp);', no_code)
    if len(entities) > 5:
        return [Issue('WARN', 'html_entities_in_body',
                      f'{len(entities)} HTML entities (&amp; etc.) in body — should be decoded')]
    return []


def chk_local_image_paths(md, slug):
    """Images must use /legacy/assets/... not ../../assets/ for GitHub Pages."""
    bad = re.findall(r'!\[.*?\]\(\.\./\.\./', md)
    if bad:
        return [Issue('WARN', 'relative_image_path',
                      f'{len(bad)} image(s) use ../../ — should be /legacy/assets/...')]
    return []


def chk_broken_md_links(md, slug):
    """Links with empty href [text]() are broken and should not appear."""
    bad = re.findall(r'\[[^\]]+\]\(\s*\)', md)
    if bad:
        return [Issue('WARN', 'broken_links', f'{len(bad)} empty link(s) [text]()')]
    return []


def chk_no_triple_blanks(md, slug):
    """3+ blank lines = converter not collapsing whitespace."""
    if re.search(r'\n{4,}', md):
        return [Issue('WARN', 'excessive_blank_lines', '3+ consecutive blank lines found')]
    return []


def chk_prose_in_code(md, slug):
    """Multiple English sentences inside a code block = text/code boundary wrong."""
    for block in re.findall(r'```\w*\n(.*?)```', md, re.DOTALL):
        sentences = re.findall(r'[A-Z][^.!?]{25,}[.!?]', block)
        if len(sentences) >= 3:
            return [Issue('WARN', 'prose_in_code',
                          f'Code block has {len(sentences)} English sentences — possible misplaced prose')]
    return []


def chk_duplicate_paragraphs(md, slug):
    """Same paragraph appearing twice = double-processing bug.

    LESSON: Use full content hash as key. Prefix matching causes false positives
    when two different code blocks share a long common header (e.g. Spring XML
    configs with identical <?xml...><beans...> preambles, or Java classes in the
    same package with matching 'package com.acme;import java.util.Arr' prefixes).
    """
    body = _body(md)
    paras = [p.strip() for p in body.split('\n\n') if len(p.strip()) > 80]
    seen = {}
    for p in paras:
        if p in seen:
            return [Issue('ERROR', 'duplicate_paragraph',
                          f'Paragraph repeated: "{p[:50]}..."')]
        seen[p] = True
    return []


def chk_excessive_line_length(md, slug):
    """Lines > 8000 chars usually mean missing line breaks (code not wrapped)."""
    for i, line in enumerate(md.splitlines(), 1):
        if len(line) > 8000:
            return [Issue('WARN', 'excessive_line_length',
                          f'Line {i} is {len(line)} chars — possible missing line breaks')]
    return []


def chk_many_missing_images(md, slug):
    """>10 missing image placeholders suggests systematic extraction failure."""
    count = len(re.findall(r'Missing image', md))
    if count > 10:
        return [Issue('WARN', 'many_missing_images',
                      f'{count} missing image placeholders — check extraction')]
    return []


def chk_code_fence_language(md, slug):
    """Code fences with unknown/garbage language tags won't highlight."""
    KNOWN = {'java','python','javascript','typescript','xml','json','yaml','sql',
             'drl','bash','shell','html','css','kotlin','scala','groovy','ruby',
             'go','rust','c','cpp','csharp','php','swift','r','perl','lua',''}
    unknown = set(re.findall(r'^```(\w+)', md, re.MULTILINE)) - KNOWN
    if unknown:
        return [Issue('WARN', 'unknown_fence_language',
                      f'Unrecognised language tag(s): {sorted(unknown)}')]
    return []


# ══════════════════════════════════════════════════════════════════════════════
# CROSS-VALIDATION CHECKS (MD vs HTML article)
# ══════════════════════════════════════════════════════════════════════════════

def cross_code_block_count(md, slug, article):
    """Every <pre> in HTML → one fenced block in MD. Mismatch = code dropped."""
    from bs4 import Tag
    html_pres = len([p for p in article.find_all('pre') if isinstance(p, Tag)])
    md_blocks = len(re.findall(r'^```', _body(md), re.MULTILINE)) // 2
    if html_pres > 0 and md_blocks == 0:
        return [Issue('ERROR', 'code_blocks_dropped',
                      f'HTML has {html_pres} <pre> block(s) but MD has 0')]
    if html_pres > 0 and abs(html_pres - md_blocks) > 1:
        return [Issue('WARN', 'code_block_count_mismatch',
                      f'HTML: {html_pres} blocks, MD: {md_blocks} blocks')]
    return []


def cross_code_content_integrity(md, slug, article):
    """Full code block content must match — not just first line. Detects truncation/mangling."""
    from bs4 import Tag
    issues = []
    for pre in article.find_all('pre'):
        if not isinstance(pre, Tag): continue
        code_el = pre.find('code')
        code_text = (code_el or pre).get_text().strip()
        if len(code_text) < 15: continue
        # Check first AND last distinctive token
        first = next((l.strip() for l in code_text.splitlines() if l.strip()), '')[:40]
        last = next((l.strip() for l in reversed(code_text.splitlines()) if l.strip()), '')[-30:]
        if first and first[:25] not in md:
            issues.append(Issue('ERROR', 'code_content_missing',
                                f'Code start not in MD: "{first[:40]}"'))
        elif last and len(last) > 5 and last not in md:
            issues.append(Issue('WARN', 'code_content_truncated',
                                f'Code end not in MD: "...{last}"'))
        if len(issues) >= 2: break
    return issues


def cross_language_tags(md, slug, article):
    """Every language-X class in HTML should have a matching ```X fence in MD."""
    from bs4 import Tag
    html_langs = set()
    for code in article.find_all('code'):
        if not isinstance(code, Tag): continue
        for c in code.get('class', []):
            if c.startswith('language-') and len(c) > 9:
                html_langs.add(c[9:])
    md_langs = set(re.findall(r'^```(\w+)', md, re.MULTILINE))
    missing = html_langs - md_langs - {''}
    if missing:
        return [Issue('WARN', 'language_tag_missing',
                      f'HTML language(s) missing from MD fences: {sorted(missing)}')]
    return []


def cross_word_count(md, slug, article):
    """MD word count < 35% of HTML = likely content loss from over-aggressive stripping."""
    html_words = len(_article_words(article))
    body_no_code = re.sub(r'```.*?```', '', _body(md), flags=re.DOTALL)
    md_words = len(body_no_code.split())
    if html_words > 150 and md_words < html_words * 0.35:
        pct = md_words * 100 // html_words
        return [Issue('WARN', 'word_count_low',
                      f'MD body {md_words} words vs HTML {html_words} ({pct}%) — possible loss')]
    return []


def cross_heading_match(md, slug, article):
    """h2/h3 text from HTML should appear in MD. Missing headings = section dropped."""
    from bs4 import Tag
    issues = []
    body = _body(md).lower()
    for h in article.find_all(['h2', 'h3']):
        if not isinstance(h, Tag): continue
        text = h.get_text(strip=True)
        if len(text) < 5 or len(text) > 120: continue
        # Allow for minor formatting differences
        first_words = ' '.join(text.lower().split()[:4])
        if first_words and first_words not in body:
            issues.append(Issue('WARN', 'heading_missing',
                                f'Heading not found in MD: "{text[:60]}"'))
        if len(issues) >= 3: break
    return issues


def cross_list_preservation(md, slug, article):
    """<ul>/<ol> in HTML should produce bullet/numbered lists in MD."""
    from bs4 import Tag
    html_lists = len([t for t in article.find_all(['ul','ol']) if isinstance(t, Tag)
                      and len(t.find_all('li')) > 1])
    if html_lists == 0: return []
    md_list_items = len(re.findall(r'^[-*]\s|^\d+\.\s', _body(md), re.MULTILINE))
    if md_list_items == 0:
        return [Issue('WARN', 'lists_dropped',
                      f'HTML has {html_lists} list(s) but MD has no list items')]
    return []


def cross_link_count(md, slug, article):
    """External link count should be in same ballpark. Massive drop = links stripped."""
    from bs4 import Tag
    html_links = [a for a in article.find_all('a', href=True)
                  if isinstance(a, Tag) and (a['href'] or '').startswith('http')]
    html_count = len(html_links)
    # html2text may produce ](<https://...>) with angle brackets — match both forms
    md_count = len(re.findall(r'\]\(<?\s*https?://', _body(md)))
    if html_count > 5 and md_count < html_count * 0.3:
        return [Issue('WARN', 'links_dropped',
                      f'HTML has {html_count} external links, MD has {md_count} — possible loss')]
    return []


def cross_table_acknowledged(md, slug, article):
    """HTML <table> should produce a Markdown table or at minimum table content."""
    from bs4 import Tag
    tables = [t for t in article.find_all('table') if isinstance(t, Tag)]
    if not tables: return []
    md_has_table = bool(re.search(r'^\|.+\|', _body(md), re.MULTILINE))
    md_has_table_text = any(t.get_text(strip=True)[:20] in _body(md) for t in tables)
    if not md_has_table and not md_has_table_text:
        return [Issue('WARN', 'table_dropped',
                      f'{len(tables)} HTML table(s) have no representation in MD')]
    return []


def cross_last_section_present(md, slug, article):
    """Last paragraph of HTML should appear in MD — checks for truncation at the end."""
    from bs4 import Tag
    paras = [p for p in article.find_all('p') if isinstance(p, Tag)]
    # Walk backwards to find last substantial paragraph
    for p in reversed(paras):
        text = p.get_text(strip=True)
        if len(text) > 60:
            first_words = ' '.join(text.split()[:6]).lower()
            if first_words and first_words not in _body(md).lower():
                return [Issue('WARN', 'truncated_at_end',
                              f'Last HTML paragraph not in MD: "{text[:60]}"')]
            break
    return []


def cross_image_count(md, slug, article):
    """Total images (real + missing placeholders) should roughly match HTML content images."""
    from bs4 import Tag
    AVATAR = ('2016/04/', 'gravatar', 'author', '96-c', 'profile')
    html_imgs = [i for i in article.find_all('img')
                 if isinstance(i, Tag) and isinstance(i.attrs, dict)
                 and not any(h in (i.get('src','') or '') for h in AVATAR)]
    html_count = len(html_imgs)
    body = _body(md)
    md_real = len(re.findall(r'!\[.*?\]\(/legacy/assets/', body))
    md_missing = len(re.findall(r'Missing image', body))
    md_count = md_real + md_missing
    if html_count > 3 and md_count == 0:
        return [Issue('WARN', 'images_dropped',
                      f'HTML has {html_count} content image(s) but MD has none')]
    return []


def cross_youtube_count(md, slug, article):
    """YouTube thumbnail figures in HTML should appear as images/links in MD."""
    from bs4 import Tag
    yt_html = len([f for f in article.find_all('figure')
                   if isinstance(f, Tag) and 'video-embed' in ' '.join(f.get('class', []))])
    yt_md = len(re.findall(r'youtube\.com/watch', _body(md)))
    if yt_html > 0 and yt_md == 0:
        return [Issue('WARN', 'youtube_links_dropped',
                      f'HTML has {yt_html} YouTube embed(s) but none in MD')]
    return []


def cross_technical_terms(md, slug, article):
    """Key KIE/Drools technical terms from HTML must appear in MD body."""
    html_text = article.get_text().lower()
    body = _body(md).lower()
    TERMS = ['drools', 'jbpm', 'kie', 'optaplanner', 'kogito', 'guvnor', 'rete']
    present_in_html = [t for t in TERMS if t in html_text]
    if not present_in_html: return []
    missing_in_md = [t for t in present_in_html if t not in body]
    if missing_in_md:
        return [Issue('WARN', 'technical_terms_missing',
                      f'Technical term(s) in HTML but not MD: {missing_in_md}')]
    return []


def cross_blockquote_preserved(md, slug, article):
    """<blockquote> in HTML should produce > blockquote in MD."""
    from bs4 import Tag
    bqs = [b for b in article.find_all('blockquote')
           if isinstance(b, Tag) and len(b.get_text(strip=True)) > 20]
    if not bqs: return []
    md_bqs = len(re.findall(r'^>', _body(md), re.MULTILINE))
    if md_bqs == 0:
        return [Issue('WARN', 'blockquotes_dropped',
                      f'{len(bqs)} HTML blockquote(s) have no > in MD')]
    return []


def cross_key_phrase_sample(md, slug, article):
    """Sample HTML paragraphs — key phrases must appear in MD body."""
    from bs4 import Tag
    body = _body(md).lower()
    STOP = {'which','these','their','there','about','would','could','should',
            'where','when','have','from','that','this','with','been','also',
            'more','some','into','than','such','over','after','before'}
    issues = []
    checked = 0
    for p in article.find_all('p'):
        if not isinstance(p, Tag): continue
        text = p.get_text(strip=True)
        if len(text) < 80 or len(text) > 600: continue
        words = [w for w in re.sub(r'[^\w\s]','',text.lower()).split()
                 if len(w) > 5 and w not in STOP]
        if len(words) < 5: continue
        phrase = ' '.join(words[1:5])  # skip first word (often a link)
        if phrase and phrase not in body:
            issues.append(Issue('WARN', 'content_phrase_missing',
                                f'HTML para phrase not in MD: "{text[:60]}..."'))
        checked += 1
        if checked >= 8 or len(issues) >= 2: break
    return issues[:2]


def cross_chrome_leakage(md, slug, article):
    """Text from WordPress chrome (sidebar, related posts) must not appear in MD."""
    body = _body(md)
    CHROME = [
        (r'Recent Posts', 'sidebar widget'),
        (r'Leave a Reply', 'comment form'),
        (r'You might also like', 'related posts'),
    ]
    return [Issue('WARN', 'chrome_leakage', f'WordPress {label} text in MD')
            for pattern, label in CHROME if re.search(pattern, body)]


# ── Registries ────────────────────────────────────────────────────────────────
MD_CHECKS = [
    chk_orphaned_placeholders,
    chk_stray_digit_after_fence,
    chk_balanced_fences,
    chk_empty_code_blocks,
    chk_front_matter_valid,
    chk_empty_body,
    chk_wordpress_junk,
    chk_html_entities_in_body,
    chk_local_image_paths,
    chk_broken_md_links,
    chk_no_triple_blanks,
    chk_prose_in_code,
    chk_duplicate_paragraphs,
    chk_excessive_line_length,
    chk_many_missing_images,
    chk_code_fence_language,
]

CROSS_CHECKS = [
    cross_code_block_count,
    cross_code_content_integrity,
    cross_language_tags,
    cross_word_count,
    cross_heading_match,
    cross_list_preservation,
    cross_link_count,
    cross_table_acknowledged,
    cross_last_section_present,
    cross_image_count,
    cross_youtube_count,
    cross_technical_terms,
    cross_blockquote_preserved,
    cross_key_phrase_sample,
    cross_chrome_leakage,
]


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import sys
    ROOT = Path(__file__).parent.parent
    MD_DIR  = ROOT / 'mark-proctor'
    HTML_DIR = ROOT / 'legacy/posts/mark-proctor'

    files = [Path(sys.argv[1])] if len(sys.argv) >= 2 else sorted(MD_DIR.glob('*.md'))
    error_count = warn_count = 0
    for md_path in files:
        md = md_path.read_text(errors='replace')
        html_path = HTML_DIR / (md_path.stem + '.html')
        issues = validate(md, md_path.stem, html_path if html_path.exists() else None)
        for issue in issues:
            print(f'{md_path.name}: {issue}')
            if issue.level == 'ERROR': error_count += 1
            else: warn_count += 1
    print(f'\n{len(files)} file(s) — {error_count} errors, {warn_count} warnings')
