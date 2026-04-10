"""
Auto-fix routines for code block quality issues detected by scan_html.py.

Exported:
  reformat_drl(text)           -> str  — insert newlines at DRL keyword boundaries
  reformat_xml(text)           -> str  — pretty-print well-formed XML; return as-is if malformed
  apply_code_block_fixes(soup) -> bool — apply both fixers to all <pre><code> in soup
"""
from __future__ import annotations

import re
from xml.dom.minidom import parseString
from xml.parsers.expat import ExpatError

from bs4 import BeautifulSoup, Tag

# ── DRL reformatter ───────────────────────────────────────────────────────────

# Top-level DRL keywords that must each start a new line.
# Ordered longest-first to avoid partial matches (e.g. "rule" before "ruleflow-group").
_DRL_KEYWORDS = [
    'agenda-group', 'lock-on-active', 'no-loop', 'auto-focus',
    'activation-group', 'date-effective', 'date-expires', 'ruleflow-group',
    'salience', 'dialect', 'duration', 'enabled', 'timer',
    'declare', 'function', 'package', 'import', 'global', 'query',
    'rule', 'when', 'then', 'end',
]

# Regex: any of the keywords followed by whitespace or end-of-string,
# not already at the start of a line.
# Keywords that must be alone on their own line (no content follows on same line)
_DRL_LINE_ALONE = {'when', 'then', 'end'}

_DRL_KW_RE = re.compile(
    r'\b(' + '|'.join(re.escape(k) for k in _DRL_KEYWORDS) + r')\b'
)

# Signals that a string of text is DRL (not Java or XML or other)
_DRL_SIGNALS = [
    re.compile(r'\brule\s*["|\xa0]', re.I),   # rule "Name" or rule\xa0"Name" or rule"Name"
    re.compile(r'\bquery\s+[\w"]', re.I),      # query Name(...) or query "Name"
    re.compile(r'\bwhen\b.*\bthen\b', re.I | re.S),
    re.compile(r'^\s*end\s*$', re.M),
    re.compile(r'\bdrools\b', re.I),
    re.compile(r'\binsert\b|\bretract\b|\bmodify\b|\bupdate\b', re.I),
]


def _is_drl(text: str) -> bool:
    return any(sig.search(text) for sig in _DRL_SIGNALS)


def reformat_drl(text: str) -> str:
    """Insert newlines before top-level DRL keywords.

    Only processes text that already has no newlines (or very few) and
    contains DRL signals.  Returns the original text unchanged when:
      - it already has newlines (already formatted)
      - it is too short to be a real block
      - it doesn't look like DRL
    """
    if not text or '\n' in text:
        return text
    if len(text) < 15:
        return text
    if not _is_drl(text):
        return text

    # Insert \n before DRL keywords, but ONLY outside quoted strings.
    # The regex can match 'rule' inside "start rule" or 'end' inside "end game"
    # — those are part of rule names, not DRL keywords.
    result_chars: list[str] = []
    in_quote = False
    i = 0
    text_len = len(text)
    while i < text_len:
        ch = text[i]
        if ch == '"':
            in_quote = not in_quote
            result_chars.append(ch)
            i += 1
            continue
        if not in_quote:
            # Try to match a DRL keyword at this position
            m = _DRL_KW_RE.match(text, i)
            if m:
                kw = m.group(1)
                # Only insert \n before the keyword if not at start of text/line
                if result_chars and result_chars[-1] != '\n':
                    result_chars.append('\n')
                result_chars.append(kw)
                if kw in _DRL_LINE_ALONE:
                    result_chars.append('\n')
                i = m.end()
                continue
        result_chars.append(ch)
        i += 1

    result = ''.join(result_chars)
    # Clean up each line
    lines = [line.strip() for line in result.split('\n')]
    return '\n'.join(line for line in lines if line)


# ── XML pretty-printer ────────────────────────────────────────────────────────

def reformat_xml(text: str) -> str:
    """Pretty-print well-formed XML.  Returns the original text unchanged
    if the input is empty, already has newlines, or is a malformed fragment.
    """
    if not text or '\n' in text:
        return text
    try:
        pretty = parseString(text).toprettyxml(indent='  ')
        # toprettyxml adds an XML declaration — remove it if not in original
        if not text.startswith('<?xml'):
            lines = pretty.split('\n')
            if lines and lines[0].startswith('<?xml'):
                lines = lines[1:]
            pretty = '\n'.join(lines)
        # Remove trailing blank lines added by toprettyxml
        return pretty.strip()
    except ExpatError:
        return text


# ── Apply to a full soup document ─────────────────────────────────────────────

# language classes that contain DRL (Blogger used 'sql' as fallback highlighter)
_DRL_CLASSES = {'language-drl', 'language-sql'}
# language classes that are XML
_XML_CLASSES = {'language-xml', 'language-typescript'}


def fix_drl_br_blocks(soup: BeautifulSoup) -> bool:
    """Convert plain <p>/<div> elements with <br/> line breaks containing DRL
    to <pre><code class="language-drl">.

    Pattern (from KIE blog posts that used Blogger's plain text code blocks):
      <p>rule "Calculate Dead"<br/>agenda-group "calculate"<br/>when<br/>...</p>

    Conditions for conversion:
    - At least 3 <br/> tags (2 could be a two-line note or link list)
    - is_drl() returns True on the joined text
    - avg line length < 80 (code lines are short; prose with DRL keywords is long)
    - Does not already contain a <pre> or <code> element
    - Is not a direct child of <article> (those are top-level wrappers)
    - Is not inside a <pre>/<code>
    """
    changed = False

    for el in soup.find_all(['p', 'div']):
        if not isinstance(el, Tag):
            continue
        if el.find_parent(['pre', 'code']):
            continue
        if el.name == 'div' and isinstance(el.parent, Tag) and el.parent.name == 'article':
            continue
        if el.find(['pre', 'code']):
            continue
        brs = el.find_all('br')
        if len(brs) < 3:
            continue

        # Extract text with br→newline
        import copy
        el_copy = copy.copy(el)
        for br in el_copy.find_all('br'):
            br.replace_with('\n')
        text = el_copy.get_text(separator='').replace('\xa0', ' ').strip()

        if not _is_drl(text):
            continue

        lines = [l.strip() for l in text.split('\n') if l.strip()]
        if not lines:
            continue
        avg_len = sum(len(l) for l in lines) / len(lines)
        if avg_len > 80:
            continue  # long lines = prose with DRL keywords mentioned, not code

        formatted = reformat_drl(text)
        new_block = BeautifulSoup(
            '<pre><code class="language-drl"></code></pre>', 'html.parser'
        )
        new_block.find('code').append(formatted)
        el.replace_with(new_block)
        changed = True

    return changed


_SPAN_DRL_RE = re.compile(r'<span>\s*rule\s*</span>', re.I)


def fix_drl_span_blocks(soup: BeautifulSoup) -> bool:
    """Convert Blogger-style span-tokenised DRL code blocks to <pre><code>.

    Blogger's syntax highlighter wraps each token in a <span> with <br/> for
    line breaks, producing markup like:
      <div><span>rule</span><span>"IsChild"\xa0</span><span>when</span>...

    When these spans are joined without separators, `rule` and `"Name"` merge
    as `rule"IsChild"` (no space), which the standard DRL signal misses.

    This function:
    1. Finds <div>/<p> elements where a <span> contains only the word "rule"
       AND the element has <br/> children AND the joined text is DRL.
    2. Extracts the text: replaces <br/> with \\n, joins all spans with '',
       normalises \\xa0 → space.
    3. Applies reformat_drl() then wraps in <pre><code class="language-drl">.
    """
    changed = False

    for el in soup.find_all(['div', 'p']):
        if not isinstance(el, Tag):
            continue
        if el.find_parent(['pre', 'code']):
            continue
        # Must have at least one <br/>
        if not el.find('br'):
            continue
        # Must have a <span> whose text is just "rule"
        rule_spans = [
            s for s in el.find_all('span')
            if s.get_text(strip=True).lower() == 'rule'
               and not s.find()  # leaf span only
        ]
        if not rule_spans:
            continue
        # Must contain no <pre>/<code> blocks (already handled)
        if el.find(['pre', 'code']):
            continue

        # Extract text: br→\n, join all text nodes, normalise nbsp
        import copy
        el_copy = copy.copy(el)
        for br in el_copy.find_all('br'):
            br.replace_with('\n')
        text = el_copy.get_text(separator='').replace('\xa0', ' ').strip()

        if not _is_drl(text):
            continue

        formatted = reformat_drl(text)
        new_code = BeautifulSoup(
            f'<pre><code class="language-drl"></code></pre>', 'html.parser'
        )
        new_code.find('code').append(formatted)
        el.replace_with(new_code)
        changed = True

    return changed


def _is_linenumber_pre(pre: Tag) -> bool:
    """True if a <pre> contains only line numbers (digits + newlines)."""
    text = pre.get_text().strip()
    return bool(text) and all(c.isdigit() or c in '\n ' for c in text)


def _is_linenumber_divs(td: Tag) -> bool:
    """True if a <td> contains only <div> children that are single numbers."""
    children = [c for c in td.children if hasattr(c, 'name') and c.name]
    if not children:
        return False
    return all(c.name == 'div' and c.get_text().strip().isdigit() for c in children)


def _extract_code_from_td(td: Tag) -> str:
    """Extract code text from a <td>, joining fragments with newlines."""
    # Pattern A: single <pre>
    pre = td.find('pre')
    if pre:
        for br in pre.find_all('br'):
            br.replace_with('\n')
        return pre.get_text()
    # Pattern B: multiple <div><code> fragments — each div is a line
    lines = []
    for div in td.find_all('div', recursive=False) or td.find_all('div'):
        for br in div.find_all('br'):
            br.replace_with('\n')
        line = div.get_text()
        if line.strip():
            lines.append(line.rstrip())
    return '\n'.join(lines)


def fix_linenumber_table_blocks(soup: BeautifulSoup) -> bool:
    """Convert two-column line-number + code tables to <pre><code> blocks.

    Old SyntaxHighlighter WordPress/Blogger plugin rendered code in a table:
    left column = line numbers, right column = code content.

    Pattern A — <pre> in both columns:
      <table><td><pre>1\\n2\\n3\\n</pre></td><td><pre>code...</pre></td></table>

    Pattern B — <div> line numbers, <code> fragments per line:
      <table><td><div>1</div><div>2</div></td>
             <td><div><code>line1</code></div><div><code>line2</code></div></td></table>

    Both are replaced with a single <pre><code class="language-?">code</code></pre>.
    """
    changed = False

    for table in list(soup.find_all('table')):
        if not isinstance(table, Tag):
            continue

        tds = table.find_all('td')
        if len(tds) < 2:
            continue

        left_td = tds[0]
        right_td = tds[1]

        # Detect Pattern A
        left_pre = left_td.find('pre')
        is_a = left_pre is not None and _is_linenumber_pre(left_pre)

        # Detect Pattern B
        is_b = not is_a and _is_linenumber_divs(left_td) and bool(right_td.find(['code', 'pre']))

        if not is_a and not is_b:
            continue

        # Extract code and determine language from existing class
        code_text = _extract_code_from_td(right_td).strip()
        if not code_text:
            continue

        # Inherit language class from the right column's pre/code if present
        right_code = right_td.find(['pre', 'code'])
        existing_classes = right_code.get('class', []) if right_code else []
        lang_cls = next((c for c in existing_classes if c.startswith('language-')), None)

        # Build replacement
        code_tag_str = f'<code class="{lang_cls}">' if lang_cls else '<code>'
        new_block = BeautifulSoup(
            f'<pre>{code_tag_str}</code></pre>', 'html.parser'
        )
        new_block.find('code').append(code_text)
        table.replace_with(new_block)
        changed = True

    return changed


def apply_code_block_fixes(soup: BeautifulSoup) -> bool:
    """Apply DRL + XML reformatters to all <pre><code> blocks in soup.

    Modifies soup in-place.  Returns True if any block was changed.
    """
    changed = False
    for pre in soup.find_all('pre'):
        if not isinstance(pre, Tag):
            continue
        code = pre.find('code')
        if not isinstance(code, Tag):
            continue
        text = code.get_text()
        if not text or '\n' in text:
            continue  # already formatted or empty

        classes = set(code.get('class', []) or [])

        if classes & _DRL_CLASSES:
            fixed = reformat_drl(text)
            if fixed != text:
                code.clear()
                code.append(fixed)
                changed = True

        elif classes & _XML_CLASSES:
            fixed = reformat_xml(text)
            if fixed != text:
                code.clear()
                code.append(fixed)
                changed = True

    changed |= fix_drl_span_blocks(soup)
    changed |= fix_drl_br_blocks(soup)
    changed |= fix_linenumber_table_blocks(soup)
    return changed
