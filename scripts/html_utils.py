"""
HTML prettification utilities for the Sparge editor view.
"""
import re


def prettify_html(raw: str) -> str:
    """Prettify HTML for the editor while preserving inline element adjacency.

    BeautifulSoup prettify() puts every element on its own line, including
    inline elements like <b>, <strong>, <em>. This hides whether </b> was
    immediately adjacent to the following character in the original HTML — a
    crucial signal for understanding the md_notation_in_text warning.

    Example: <b>Bob Kowalski</b>(Imperial College London) would display as:
        <b>
         Bob Kowalski
        </b>
        (Imperial College London)
    making it impossible to see that </b> and ( are adjacent.

    After this function:
        <b>Bob Kowalski</b>(Imperial College London)
    The adjacency is visible; the user can immediately understand why
    html2text produces **Bob Kowalski**(Imperial with no space.

    When there IS a real space — <b>text</b> (more) — the closing tag and
    the following content stay on separate lines, preserving the distinction.

    Also uses html.parser (not lxml) to avoid double-encoding non-ASCII
    characters (em dashes, curly quotes) via lxml's charset sniffing.
    """
    from bs4 import BeautifulSoup, NavigableString, Tag

    soup = BeautifulSoup(raw, 'html.parser')

    # WORD JOINER (U+2060) — invisible, won't appear in normal HTML text.
    # We prefix the following sibling with it to mark adjacent inline elements.
    MARKER = '\u2060'

    INLINE_TAGS = frozenset({
        'b', 'strong', 'em', 'i', 'code', 'a', 'abbr',
        'cite', 'q', 's', 'u', 'del', 'ins', 'mark', 'small', 'sub', 'sup',
    })

    # Mark inline elements whose closing tag is immediately adjacent to a
    # non-whitespace character in the original HTML. We prefix the following
    # NavigableString sibling with MARKER so prettify() preserves the info
    # (as a leading character on its own line) and we can rejoin them after.
    for tag in list(soup.find_all(list(INLINE_TAGS))):
        if not isinstance(tag, Tag):
            continue
        if tag.find_parent(['pre', 'code']):
            continue
        sib = tag.next_sibling
        if isinstance(sib, NavigableString) and sib and not sib[0].isspace():
            sib.replace_with(NavigableString(MARKER + str(sib)))

    content = soup.prettify()

    # Garbling detection — ÃÂÃÂ is the signature of lxml double-encoding
    # UTF-8 as Latin-1. Should not happen with html.parser, but guard anyway.
    if 'ÃÂÃÂ' in content or '\xc3\x82' in content:
        return raw

    # Inline element pattern — matches tag names that should stay on one line.
    _INLINE = r'(?:b|strong|em|i|code|a|abbr|cite|q|s|u|del|ins|mark|small|sub|sup)'

    # Step 1: Collapse simple text inside inline elements to a single line.
    #   Before: <b>↵   Bob Kowalski ↵  </b>
    #   After:  <b>Bob Kowalski</b>
    # Only collapses when the content is plain text (no child tags).
    content = re.sub(
        rf'(<(?:{_INLINE})(?:\s[^>]*)?>)\n[ \t]*(.*?)\n[ \t]*(</(?:{_INLINE})>)',
        lambda m: m.group(1) + m.group(2) + m.group(3),
        content,
        flags=re.IGNORECASE,
    )

    # Step 2: Rejoin closing tags with MARKER-prefixed content (adjacent in original).
    #   Before: </b>↵   ⁠(Imperial College London)
    #   After:  </b>(Imperial College London)
    # The MARKER identifies lines where the original had no space before content.
    content = re.sub(
        rf'(</(?:{_INLINE})>)\n[ \t]*{re.escape(MARKER)}',
        r'\1',
        content,
        flags=re.IGNORECASE,
    )

    # Clean up any remaining MARKER characters (e.g. inside nested inline elements
    # where Step 1 did not collapse the outer element's content).
    content = content.replace(MARKER, '')

    return content
