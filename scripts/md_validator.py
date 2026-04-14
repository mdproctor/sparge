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


def _load_article(html_path: Path):
    """Parse HTML and return the article element ready for cross-validation.

    Applies the same chrome-stripping as convert_post.py so the HTML the
    validator checks against matches what the converter actually saw.  Without
    this, headings/sections that the converter intentionally removes (author bio,
    share widgets, bylines) appear in the HTML but not the MD, generating false
    positives for every cross-check that compares the two.

    COHERENCE REQUIREMENT: Every time a new strip is added to convert_post.py,
    an equivalent strip must be added here.  Mismatches are the leading cause
    of false-positive MD warnings.  Known gaps as of 2026-04-07:
      - JUNK_SELECTORS (.jp-relatedposts, .entry-header, etc.) — not mirrored
      - addtoany/wpDiscuz class-based removal — not mirrored
      - Byline length guard (converter: < 500 chars; validator: < 200 chars)
    These are left as-is because the affected elements rarely contain
    paragraph text that cross-checks would sample.  If false positives appear
    on specific posts, check convert_post.py for a strip that is missing here.

    MIGRATION NOTE (Quarkus/Java): this function must be re-implemented using
    the same Jsoup selector logic as convert_post.py.  The key invariant is
    that both functions process the HTML with identical chrome-removal so the
    validator's HTML matches the converter's HTML.  Use constants.py
    JUNK_SELECTORS_CONVERTER for the selector list.
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_path.read_text(errors='replace'), 'html.parser')
    article = soup.find('article') or soup.find('body')
    if not article:
        return None
    # Strip scripts/styles/noscripts
    for t in article.find_all(['script', 'style', 'noscript']):
        t.decompose()
    # Strip known chrome sections — same headings convert_post.py removes.
    # "Author", "Related Posts", "Feedback", "Share" are blog template headings,
    # not content.  The converter strips them and everything after; the validator
    # must do the same or it will flag them as missing in the MD.
    _CHROME_HEADINGS = {'author', 'related posts', 'feedback', 'share', 'about'}
    for h in list(article.find_all(['h2', 'h3'])):
        if h.get_text(strip=True).lower() in _CHROME_HEADINGS:
            for sib in list(h.find_next_siblings()):
                sib.decompose()
            h.decompose()
            break  # only the first occurrence triggers section removal
    # Strip bylines — same as scan_html.py pre-processing
    for tag in list(article.find_all(['p', 'div', 'span'])):
        text = tag.get_text(separator=' ', strip=True)
        if len(text) < 200 and re.match(r'^by\s+[A-Z]', text, re.I):
            tag.decompose()
    # Decompose any <p> that contains ==== separator strings.
    # HTML posts use "Supported by\n====...\nW3C" — sections separated by an
    # ASCII visual rule inside a single <p> via <br/> elements.  The converter
    # splits these into separate MD sections (each with a blank+--- HR), so the
    # merged HTML text "supported by w3c" is never a phrase in the MD.  Removing
    # the whole paragraph avoids the false positives; its content is still
    # indirectly covered by cross_word_count and cross_link_count.
    for p in list(article.find_all('p')):
        for s in p.strings:
            if re.match(r'^={4,}\s*$', s):
                p.decompose()
                break
    # Strip email-marketing "Forward this message to a friend" links — same
    # as convert_post.py's send_to_friend detection.  These are newsletter
    # template chrome; the converter removes them, so the validator must too.
    from bs4 import Tag as _Tag
    for a in list(article.find_all('a', href=True)):
        href = a.get('href', '')
        if 'send_to_friend' in href or 'sendtofriend' in href.lower():
            parent = a.parent
            a.decompose()
            if isinstance(parent, _Tag) and not parent.get_text(strip=True):
                parent.decompose()
    return article


def validate(md: str, slug: str = '', html_path: Optional[Path] = None) -> List[Issue]:
    """Run CONTENT FIXING checks: detect losses/defects compared to the HTML source."""
    issues = []
    for fn in MD_CHECKS:
        issues.extend(fn(md, slug))
    if html_path and html_path.exists():
        try:
            article = _load_article(html_path)
            if article:
                for fn in CROSS_CHECKS:
                    issues.extend(fn(md, slug, article))
        except Exception as e:
            issues.append(Issue('WARN', 'cross_check_error', f'Could not load HTML: {e}'))
    return issues


def refine(md: str, slug: str = '', html_path: Optional[Path] = None) -> List[Issue]:
    """Run CONTENT REFINEMENT checks: identify quality improvements for a future pass.

    These checks detect characteristics present in BOTH the HTML source and the MD —
    the conversion was faithful, but the original content could be improved.
    Stored as 'suggestions' in state (not 'issues') and surfaced in a separate UI view.
    """
    suggestions = []
    for fn in MD_REFINEMENT_CHECKS:
        suggestions.extend(fn(md, slug))
    if html_path and html_path.exists():
        try:
            article = _load_article(html_path)
            if article:
                for fn in CROSS_REFINEMENT_CHECKS:
                    suggestions.extend(fn(md, slug, article))
        except Exception:
            pass  # refinement failures are silent — not critical path
    return suggestions


def _body(md):
    """Return body after front matter."""
    parts = md.split('\n---\n', 1)
    return parts[1] if len(parts) > 1 else md


def _article_words(article):
    """Count prose words in an article, excluding <pre>/<code> content.

    Mirrors the MD word count which strips fenced code blocks — both sides
    must exclude code content for the comparison to be fair.  Technical posts
    with large <pre> blocks would otherwise appear to have 'lost' content
    that is actually present in the MD as properly fenced code.
    """
    import copy as _copy
    article_copy = _copy.copy(article)
    for el in article_copy.find_all(['pre', 'code']):
        el.decompose()
    return re.sub(r'\s+', ' ', article_copy.get_text()).strip().split()


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
    """Detect unclosed fenced code blocks using a length-aware state machine.

    A naive '^```' prefix regex counts content lines that start with backticks
    (e.g. nested ``` inside a 4-backtick fence) as fence delimiters, producing
    false positives. The correct rule (CommonMark): a closing fence must use at
    least as many backticks as the opening fence.
    """
    in_fence = 0  # length of current opening fence; 0 = outside a fence
    for line in _body(md).splitlines():
        m = re.match(r'^(`{3,})', line)
        if m:
            run = len(m.group(1))
            if in_fence == 0:
                in_fence = run          # opening fence (info string allowed after backticks)
            elif run >= in_fence and re.fullmatch(r'`+\s*', line):
                in_fence = 0            # valid closing fence: only backticks + optional space
            # else: shorter run, or has non-space content after backticks (e.g. ```])
            #       — treat as content inside the current fence
    if in_fence != 0:
        return [Issue('ERROR', 'unbalanced_fences', 'Code fence opened but never closed')]
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
    """Multiple English sentences inside a code block = text/code boundary wrong.

    False-positive filter: exclude regex matches that contain code operators
    (= ; ( ) < >) — these appear in Java method chains, XML attributes, and
    comment+code spans, but never in real English sentences.
    """
    _CODE_CHARS = re.compile(r'[=;()<>{}]')
    for block in re.findall(r'```\w*\n(.*?)```', md, re.DOTALL):
        raw = re.findall(r'[A-Z][^.!?]{25,}[.!?]', block)
        sentences = [s for s in raw if not _CODE_CHARS.search(s)]
        if len(sentences) >= 3:
            return [Issue('WARN', 'prose_in_code',
                          f'Code block has {len(sentences)} English sentences — possible misplaced prose')]
    return []


def cross_duplicate_paragraphs(md, slug, article):
    """Same paragraph appearing twice in the MD = possible double-processing bug.

    Cross-checks against the HTML: if the paragraph appears the same number of
    times in the HTML as in the MD, the repetition is faithful to the source
    (the author wrote it twice) — not a conversion error.

    LESSON: Use full content hash as key. Prefix matching causes false positives
    when two different code blocks share a long common header (e.g. Spring XML
    configs with identical <?xml...><beans...> preambles, or Java classes in the
    same package with matching 'package com.acme;import java.util.Arr' prefixes).
    """
    body = _body(md)
    paras = [p.strip() for p in body.split('\n\n') if len(p.strip()) > 80]
    seen: dict = {}
    # Strip all non-alphanumeric characters for HTML comparison — markdown list
    # markers (  * , - ), code fences, and whitespace differences between the
    # MD (formatted) and HTML (plain text) would otherwise cause false positives.
    # We compare only the character sequence, not the formatting.
    html_alnum = re.sub(r'[^a-z0-9]', '', (article.get_text() if article else '').lower())
    for p in paras:
        if p in seen:
            # Only report if the duplication is NOT in the source HTML.
            # If the author wrote the same block twice (e.g. the same JVM flags
            # for WildFly and Tomcat sections), the HTML also has it twice and it
            # is faithful to the source — not a conversion error.
            p_alnum = re.sub(r'[^a-z0-9]', '', p.lower())[:30]
            if html_alnum.count(p_alnum) < 2:
                return [Issue('ERROR', 'duplicate_paragraph',
                              f'Paragraph repeated: "{p[:50]}..."')]
            # else: duplicate exists in HTML too — faithful to source, skip
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
             'go','rust','c','cpp','csharp','php','swift','r','perl','lua',
             'text','plaintext','plain','ebnf','properties','mvel',''}
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
    # Normalise MD once: replace non-breaking spaces so \xa0 in HTML matches spaces in MD
    md_norm = md.replace('\xa0', ' ')
    for pre in article.find_all('pre'):
        if not isinstance(pre, Tag): continue
        code_el = pre.find('code')
        code_text = (code_el or pre).get_text().strip().replace('\xa0', ' ')
        if len(code_text) < 15: continue
        first = next((l.strip() for l in code_text.splitlines() if l.strip()), '')[:40]
        last = next((l.strip() for l in reversed(code_text.splitlines()) if l.strip()), '')[-30:]
        if first and first[:25] not in md_norm:
            issues.append(Issue('ERROR', 'code_content_missing',
                                f'Code start not in MD: "{first[:40]}"'))
        elif last and len(last) > 5 and last not in md_norm:
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
    """h2/h3 text from HTML should appear in MD. Missing headings = section dropped.

    Skips headings that match the post's front matter title — WordPress and similar
    CMS platforms insert the post title as both an h1/h2 in the article body AND
    as the page title.  In the MD it lives in the 'title:' front matter field, not
    in the body.  Flagging it as 'missing' is a false positive.
    """
    from bs4 import Tag
    issues = []
    # Normalise body whitespace so headings split by <br/> ("Conference\non") still match.
    body = re.sub(r'\s+', ' ', _body(md)).lower()
    # Extract title from front matter to skip duplicate title headings
    fm_title = ''
    fm_m = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', md, re.MULTILINE | re.IGNORECASE)
    if fm_m:
        fm_title = fm_m.group(1).strip().lower()
    for h in article.find_all(['h2', 'h3']):
        if not isinstance(h, Tag): continue
        # separator=' ' prevents <br/> from merging adjacent words into one token
        text = re.sub(r'\s+', ' ', h.get_text(separator=' ', strip=True))
        if len(text) < 5 or len(text) > 120: continue
        # Skip headings matching the post title — it's in the front matter, not body
        if fm_title and text.lower()[:len(fm_title)] == fm_title[:len(text)]:
            continue
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
    # Allow optional leading whitespace or blockquote markers — html2text indents
    # list items from nested structures ("  * item") and prefixes blockquoted lists
    # with ">" ("> * item" when <blockquote><ul> is used as an indent wrapper).
    # Bug fix: the original r'^\s*[-*]\s|\s*^\d+\.\s' had a broken second alternative —
    # \s*^ is invalid in MULTILINE (^ must begin the alternative, not follow \s*).
    md_list_items = len(re.findall(r'^[>\s]*[-*]\s|^[>\s]*\d+\.', _body(md), re.MULTILINE))
    if md_list_items == 0:
        return [Issue('WARN', 'lists_dropped',
                      f'HTML has {html_lists} list(s) but MD has no list items')]
    return []


def cross_link_count(md, slug, article):
    """External link count should be in same ballpark. Massive drop = links stripped.

    Counts unique destinations only, excluding social sharing widgets.
    Social sharing widgets (addtoany, sharethis, buffer, etc.) generate unique hrefs
    per post by encoding the post URL as a query parameter (?linkurl=https%3A...).
    These are blog chrome — not content links — and must be excluded from the count.
    The ?linkurl= pattern is a universal signature across all sharing widget platforms.
    """
    from bs4 import Tag
    html_hrefs = set(
        a['href'] for a in article.find_all('a', href=True)
        if isinstance(a, Tag)
        and (a.get('href') or '').startswith('http')
        and 'linkurl=' not in (a.get('href') or '')   # sharing widget: encodes target URL
        and 'link_url=' not in (a.get('href') or '')  # variant spelling
    )
    html_count = len(html_hrefs)
    # Count both Markdown-style links [text](<url>) AND bare <http://...> autolinks.
    # html2text renders plain URLs in HTML as <http://...> autolinks — the original
    # regex only matched [text](<url>) format, causing links_dropped false positives
    # when the MD uses autolink format for bare URLs.
    md_count = len(re.findall(r'(?:\]\(<?\s*https?://|<https?://)', _body(md)))
    if html_count > 5 and md_count < html_count * 0.3:
        return [Issue('WARN', 'links_dropped',
                      f'HTML has {html_count} external links, MD has {md_count} — possible loss')]
    return []


def cross_table_acknowledged(md, slug, article):
    """HTML <table> should produce a Markdown table or at minimum table content.

    html2text renders tables with content BEFORE the first pipe:
      'Company:| [JDM Systems](<url>)  \\n---|---'
    so the regex must detect pipes mid-line, not just at line-start.
    Text comparison uses separator=' ' and a 4-word phrase to avoid word-merge
    mismatches from inline links wrapping individual table cell values.
    """
    from bs4 import Tag
    tables = [t for t in article.find_all('table') if isinstance(t, Tag)]
    if not tables: return []
    body = _body(md)
    # Match lines with 2+ pipe characters (covers both |col|col| and col|col| formats)
    md_has_table = bool(re.search(r'.+\|.+\|', body))
    # Also check for the '---|---' separator line that html2text always produces
    md_has_separator = bool(re.search(r'^-+\|-', body, re.MULTILINE))
    if md_has_table or md_has_separator:
        return []
    # Fall back to text content check with proper normalisation.
    # Strip inline links and bold/italic markers so the table text phrase can be
    # found even when the MD wraps the content in formatting.
    body_plain = re.sub(r'\[\s*([^\]]+?)\s*\]\(<[^>]+>\)', r'\1', body)  # [text](<url>)→text
    body_plain = re.sub(r'\*{1,2}|_{1,2}', ' ', body_plain)
    body_lower = re.sub(r'\s+', ' ', body_plain).replace('\xa0', ' ').lower()
    # Only check tables with substantial content.  Single-cell layout wrappers
    # (e.g. a "PRESS RELEASE" header) have no meaningful Markdown equivalent.
    # A table is significant when it has 2+ cells (it is a data table, even
    # with short cell values) OR has a single cell with > 20 chars of text.
    def _is_significant(t):
        cells = t.find_all(['td', 'th'])
        return len(cells) >= 2 or len(t.get_text(strip=True)) > 20
    significant = [t for t in tables if _is_significant(t)]
    if not significant:
        return []  # all tables are trivial layout elements — nothing to check
    md_has_table_text = any(
        ' '.join(t.get_text(separator=' ', strip=True).replace('\xa0', ' ').split()[:4]).lower()
        in body_lower
        for t in significant
    )
    if not md_has_table_text:
        return [Issue('WARN', 'table_dropped',
                      f'{len(tables)} HTML table(s) have no representation in MD')]
    return []


def cross_last_section_present(md, slug, article):
    """Last paragraph of HTML should appear in MD — checks for truncation at the end.

    Two fixes vs the naive implementation:
    1. separator=' ' in get_text(): prevents word-merge when inline links are
       adjacent to text — 'Peter Lin<a>has</a>' → 'Peter Lin has' not 'Linhas'.
    2. Search entire MD body, not just the tail: html2text may reorder elements
       (e.g. <span>heading</span><br/>text gets placed earlier in output than
       HTML source order implies). The paragraph is still in the MD — not lost.
    """
    from bs4 import Tag
    paras = [p for p in article.find_all('p') if isinstance(p, Tag)]
    # Strip inline links from MD body so hyperlinked terms still match
    # Pad link text with spaces so adjacent text never merges: "Registration:[link]" → "Registration: link "
    # Handle optional title attribute: [text](<url> "title") or [text](<url>)
    # Strip [text](<url>) links. When the link text IS a URL (e.g. [http://x.com](<url>))
    # discard it — it's a bare URL that first_words will also strip, so keeping it in
    # the body creates a mismatch. For meaningful text (e.g. [Rule Engine](<url>)) keep it.
    def _strip_link(m):
        text = m.group(1).strip()
        return ' ' if re.match(r'https?://', text) else ' ' + text + ' '
    md_plain = re.sub(r'\[\s*([^\]]+?)\s*\]\(<[^>]+>[^)]*\)', _strip_link, _body(md))
    md_plain = re.sub(r'<https?://[^>]+>', ' ', md_plain)  # strip bare <http://...> autolinks
    md_plain = re.sub(r'\*{1,2}|_{1,2}', ' ', md_plain)  # strip bold/italic markers
    # Normalise all whitespace to single spaces so <br/>-split content ('DBM  \nSo far')
    # matches as a continuous phrase when searching for 'dbm so far'
    body_raw = re.sub(r'\s+', ' ', md_plain).replace('\xa0', ' ').lower()
    # Normalise punctuation spacing: remove spaces before commas/colons that
    # get_text(separator=' ') inserts between inline elements and following punct.
    body = re.sub(r'\s+([,;:!?.])', r'\1', body_raw)  # also normalise space before period
    for p in reversed(paras):
        # Skip paragraphs containing images — the MD interleaves image links
        # between caption text, so the plain-text phrase never appears as a
        # continuous substring regardless of whether the content is present.
        if p.find('img'):
            continue
        # separator=' ' avoids word-merge from adjacent inline elements
        text = p.get_text(separator=' ', strip=True).replace('\xa0', ' ')
        if len(text) > 60:
            # For URL-starting paragraphs, strip all URLs and check the remaining
            # text.  URLs render differently in MD (<http://...> or [text](<url>))
            # and the domain alone is not reliably searchable in the stripped body.
            words = text.split()
            if words and re.match(r'https?://', words[0]):
                # Strip every URL from the paragraph; check what's left
                remaining = re.sub(r'\s+', ' ',
                                   re.sub(r'https?://\S+', '', text)).strip()
                if len(remaining) < 20:
                    # Paragraph is effectively URL-only — no text to verify.
                    # Skip to the next (earlier) paragraph.
                    continue
                # Meaningful text follows the URL; use it as the comparison phrase
                r_words = remaining.split()
                first_words = re.sub(r'\s+([,;:!?.])', r'\1',
                                     ' '.join(r_words[:6]).lower())
                first_words = re.sub(r'\*+', ' ', first_words)
                first_words = re.sub(r'\s+', ' ', first_words).strip()
                first_words = re.sub(r'([\u201c\u2018"\'])\s+', r'\1', first_words)
                # Normalise digit + ordinal suffix split by whitespace ("5 th" → "5th")
                first_words = re.sub(r'(\d)\s+(st|nd|rd|th)\b', r'\1\2', first_words)
                first_words = re.sub(r'\s+', ' ', first_words).strip()
            else:
                first_words = re.sub(r'\s+([,;:!?.])', r'\1',  # incl. period
                                     ' '.join(words[:6]).lower())
                # Strip '*' — HTML get_text() keeps literal '*' (e.g. inline list
                # markers "* item1 * item2", footnote "[* Note:]"). After removal,
                # renormalise whitespace so "enhancements  slimmed" → single space.
                first_words = re.sub(r'\*+', ' ', first_words)
                first_words = re.sub(r'\s+', ' ', first_words).strip()
                # Strip bare URLs — they render as <http://...> or [text](<url>)
                # in MD (format differs from HTML plain text).  The remaining words
                # are sufficient to confirm the paragraph is present.
                first_words = re.sub(r'\bhttps?(?:://\S*)?', '', first_words)
                first_words = re.sub(r'\s+', ' ', first_words).strip().rstrip(' ()')
                # Strip space after an opening quotation mark — HTML text nodes
                # sometimes have '" text' (quote + space + word) while the MD
                # renders it as '"text' (no space), so '" the' ≠ '"the' in body.
                first_words = re.sub(r'([\u201c\u2018"\'])\s+', r'\1', first_words)
                # Normalise digit + ordinal suffix split by whitespace ("5 th" → "5th")
                first_words = re.sub(r'(\d)\s+(st|nd|rd|th)\b', r'\1\2', first_words)
                first_words = re.sub(r'\s+', ' ', first_words).strip()
            if first_words and first_words not in body:
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
    """Key technical terms from HTML must appear somewhere in the MD.

    Searches the full MD (front matter + body) not just the body — terms that
    appear in the post title are correctly placed in the 'title:' front matter
    field and are not missing from the document.
    """
    html_text = article.get_text().lower()
    md_full = md.lower()  # includes front matter title, not just body
    TERMS = ['drools', 'jbpm', 'kie', 'optaplanner', 'kogito', 'guvnor', 'rete']
    present_in_html = [t for t in TERMS if t in html_text]
    if not present_in_html: return []
    missing_in_md = [t for t in present_in_html if t not in md_full]
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
    """Sample HTML paragraphs — key content must appear in MD body.

    Uses a raw substring of the HTML text (not reconstructed from extracted words)
    to avoid false positives where the phrase-extraction joins stripped words into
    a sequence that never appears literally in the MD even though the content is there.
    Also normalises \xa0 to space for comparison.
    """
    from bs4 import Tag
    # Strip markdown inline links [text](<url>) and [text](<url> "title") → " text "
    # (padded with spaces to prevent word-merge when a link is adjacent to text with
    # no space: "Taylor,[Smart Enough](<url>)" → "Taylor, Smart Enough").
    # The [^)]* after > handles the optional title attribute that html2text emits
    # when protect_links=True and the original link had a title attribute.
    # MIGRATION NOTE: html2text protect_links=True emits [text](<url> "title") format.
    md_plain = re.sub(
        r'\[\s*([^\]]+?)\s*\]\(<[^>]+>[^)]*\)',
        lambda m: ' ' + m.group(1).strip() + ' ',
        _body(md))
    md_plain = re.sub(r'\*{1,2}|_{1,2}', ' ', md_plain)  # strip bold/italic markers
    md_plain = re.sub(r'(\d+)\\\.', r'\1.', md_plain)    # unescape list markers: "1\." → "1."
    body_raw = re.sub(r'\s+', ' ', md_plain).replace('\xa0', ' ').lower()
    # Normalise smart/curly quotes in the MD body to straight ASCII quotes —
    # html2text may preserve curly quotes from the original HTML (e.g. \u201c
    # left double, \u2019 right single/apostrophe), while the phrase extracted
    # from the HTML is also normalised to straight quotes for comparison.
    # Both sides must use the same quote style for substring matching to work.
    body_raw = body_raw.replace('\u201c', '"').replace('\u201d', '"')
    body_raw = body_raw.replace('\u2018', "'").replace('\u2019', "'")
    # Normalise punctuation spacing — get_text(separator=' ') inserts spaces
    # between inline elements and following punctuation ("Fest , hosted"), but
    # the MD link-stripping leaves no space ("Fest, hosted").
    # Also normalise space before period ("v4.0.3 . this" → "v4.0.3. this").
    body_raw = re.sub(r'\s*>\s*', ' ', body_raw)  # > path separator → space
    body = re.sub(r'\s+([,;:!?.])', r'\1', body_raw)
    issues = []
    checked = 0
    for p in article.find_all('p'):
        if not isinstance(p, Tag): continue
        # Skip paragraphs containing images — the MD interleaves image links
        # between caption text, breaking any continuous phrase match.
        if p.find('img'):
            continue
        # Skip paragraphs containing inline <code> elements — code content
        # (rule syntax, expressions, identifiers) appears in code blocks or
        # pre-formatted sections in the MD with different quoting/spacing.
        if p.find('code'):
            continue
        text = p.get_text(separator=' ', strip=True).replace('\xa0', ' ')
        if len(text) < 80 or len(text) > 600: continue
        first_space = text.find(' ')
        start = first_space + 1 if first_space >= 0 else 0
        # Normalise the phrase to match how the MD body is normalised:
        # - collapse whitespace and normalise punctuation spacing (incl. period)
        # - strip * (inline list markers become proper list items in MD)
        # - strip _ (underscores appear in body as spaces after bold/path stripping)
        # - strip URLs — full and partial (phrase boundary may cut mid-URL leaving
        #   bare "http" or "htt" that never appears in the body's stripped links)
        phrase_raw = re.sub(r'\s+', ' ', text[start:start + 35])
        phrase = re.sub(r'\s+([,;:!?.])', r'\1', phrase_raw).lower().strip()
        phrase = re.sub(r'\*+', ' ', phrase)                      # * list markers → space
        phrase = re.sub(r'_+', ' ', phrase)                       # _ (path/italic) → space
        phrase = re.sub(r'\b(?:https?|htt?)[:/]*\S*', '', phrase) # strip full & partial URLs
        phrase = re.sub(r'\s*>\s*', ' ', phrase)                  # > path sep → space
        # Strip space after opening curly quote only — HTML text nodes sometimes
        # have '\u201c text' (curly open + space + word) while MD renders it as
        # '"text' (straight quote, no space).  Only strip after opening curly quotes
        # (\u201c \u2018), NOT after straight " ' which may be closing quotes whose
        # following space must be preserved for the phrase to match the MD body.
        phrase = re.sub(r'[\u201c\u2018]\s+', '', phrase)         # strip open curly quote+space
        # Normalise smart/curly quotes to straight ASCII quotes — HTML may use
        # typographic quotes while MD uses straight quotes (" '), so the same text
        # won't match without normalisation.  Done after the open-quote strip above
        # so we don't confuse opening vs closing positions once all quotes are straight.
        phrase = phrase.replace('\u201c', '"').replace('\u201d', '"')
        phrase = phrase.replace('\u2018', "'").replace('\u2019', "'")
        # Normalise digit + ordinal suffix split by whitespace ("4 th" → "4th") —
        # HTML ordinal superscripts sometimes have a space between digit and suffix
        # ("4<sup>th</sup>") that html2text collapses in MD but get_text() preserves.
        phrase = re.sub(r'(\d)\s+(st|nd|rd|th)\b', r'\1\2', phrase)
        phrase = re.sub(r'\s+', ' ', phrase).strip()              # renormalise after removals
        if phrase and len(phrase) > 20 and phrase not in body:
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
#
# Two separate check sets:
#
# MD_CHECKS / CROSS_CHECKS — CONTENT FIXING
#   Detect things that were LOST or BROKEN compared to the HTML source.
#   "HTML has it, MD doesn't" → conversion defect → fix now.
#
# REFINEMENT_CHECKS / CROSS_REFINEMENT_CHECKS — CONTENT REFINEMENT
#   Detect quality characteristics that exist in BOTH the HTML and MD
#   (faithful conversion, but original content could be improved).
#   "HTML also has this" → not a conversion bug → improve later via refine pipeline.

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
    chk_excessive_line_length,
    chk_many_missing_images,
    chk_code_fence_language,
    # chk_prose_in_code removed → REFINEMENT: author put prose in <pre> in source HTML
]

CROSS_CHECKS = [
    cross_duplicate_paragraphs,
    cross_code_block_count,
    cross_code_content_integrity,
    cross_word_count,
    cross_heading_match,
    cross_list_preservation,
    cross_link_count,
    cross_table_acknowledged,
    cross_last_section_present,
    cross_image_count,
    cross_technical_terms,
    cross_blockquote_preserved,
    cross_key_phrase_sample,
    cross_chrome_leakage,
    # cross_language_tags removed → REFINEMENT: HTML code had no/wrong tag; conversion faithful
    # cross_youtube_count removed → REFINEMENT: YouTube embeds handled separately in refine pipeline
]

# ── Refinement registries ─────────────────────────────────────────────────────
# Checks that identify content quality improvements applicable to BOTH HTML and
# MD.  The conversion was faithful — the original source has the same characteristic.
# These are stored in state.suggestions (not state.issues) and surfaced in a
# future "Content Refinement" UI view, not in the current issue panel.

MD_REFINEMENT_CHECKS = [
    chk_prose_in_code,       # prose in <pre>: original author put narrative in code blocks
]

CROSS_REFINEMENT_CHECKS = [
    cross_language_tags,     # missing/wrong lang tag: HTML code had no language annotation
    cross_youtube_count,     # YouTube embeds: need separate enrichment/embed strategy
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
