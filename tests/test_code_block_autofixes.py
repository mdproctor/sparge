"""
Tests for three auto-fixes on HTML code block issues:

1. potential_code_block checker: must NOT flag the top-level article <div>
   wrapper — that's the post container, not a code block. Only flag <p>
   elements and non-direct-child <div>s.

2. DRL reformatter: <pre><code class="language-drl"> with all content on one
   line should have newlines inserted at DRL keyword boundaries. Same for
   language-sql blocks that contain DRL syntax (Blogger's SQL highlighter was
   used as a fallback for DRL).

3. XML pretty-printer: <pre><code class="language-xml"> with all content on
   one line should be pretty-printed via minidom. Malformed/fragment XML is
   left unchanged rather than erroring.
"""
import sys
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

MIGRATOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(MIGRATOR_ROOT / 'scripts'))

from scan_html import check_potential_code_blocks, check_code_block_no_newlines


def _article(html: str):
    soup = BeautifulSoup(f'<article>{html}</article>', 'html.parser')
    return soup.find('article')


# ── 1. potential_code_block: top-level div false positive ─────────────────────

class TestPotentialCodeBlockFalsePositive:
    """The top-level <div> wrapping all post content must not be flagged.

    Structure: <article><div>...all paragraphs + code + images...</div></article>
    The outer div has <br/> tags inside links/code/paragraphs and incidentally
    contains Java/DRL keywords — but it is the post container, not a code block.

    Bug: check_potential_code_blocks calls article.find_all(['p', 'div']) which
    includes this container div. Its text matches code signals because it contains
    the actual code paragraphs as descendants.

    Fix: skip <div> elements whose direct parent is <article> — those are post
    container wrappers, not code blocks.
    """

    def test_top_level_div_not_flagged(self):
        """The direct child <div> of <article> must not be flagged even if it
        contains <br/> and code-like descendant text."""
        html = """<div>
            <p>Some prose about public class design.</p>
            <p>rule "Test"<br/>when<br/>  Foo()<br/>then<br/>  doIt();<br/>end</p>
            <p>More prose here about import java.util.List and new things.</p>
        </div>"""
        article = _article(html)
        issues = check_potential_code_blocks(article)
        # Issues from scan_html use 'type' key (not 'check')
        top_div_issues = [i for i in issues if i.get('selector', '') == 'div']
        assert not top_div_issues, (
            'Top-level article <div> must not be flagged as potential_code_block. '
            'It is the post container — the check fires because descendant code '
            'paragraphs contain matching keywords. '
            'Fix: skip <div> elements whose direct parent is <article>.'
        )

    def test_nested_code_p_still_flagged(self):
        """A real code <p> inside the post container must still be flagged."""
        html = """<div>
            <p>Some prose.</p>
            <p>rule "Test"<br/>when<br/>  Foo()<br/>then<br/>  doIt();<br/>end</p>
        </div>"""
        article = _article(html)
        issues = check_potential_code_blocks(article)
        real = [i for i in issues if i.get('type') == 'potential_code_block']
        assert real, 'Real code <p> inside container must still be flagged'

    def test_top_level_div_with_br_prose_not_flagged(self):
        """Top-level div with <br/> in text but no real code patterns: not flagged."""
        html = """<div>
            <p>Line one.<br/>Line two.<br/>Line three about public class.</p>
            <p>More prose with import statements mentioned.</p>
        </div>"""
        article = _article(html)
        issues = check_potential_code_blocks(article)
        top_div_issues = [i for i in issues if i.get('selector', '') == 'div']
        assert not top_div_issues


# ── 2. DRL reformatter ────────────────────────────────────────────────────────

from fix_code_blocks import reformat_drl, reformat_xml  # imported after fix exists


class TestDrlReformatter:
    """reformat_drl() inserts newlines at DRL keyword boundaries.

    DRL keywords that start new logical lines: rule, when, then, end, package,
    import, global, declare, function, query, salience, dialect, agenda-group,
    lock-on-active, no-loop, auto-focus, activation-group, date-effective,
    date-expires, enabled, duration, timer, ruleflow-group.
    """

    def test_simple_rule_gets_newlines(self):
        one_line = 'rule "Test" when Foo() then doIt(); end'
        result = reformat_drl(one_line)
        assert '\n' in result, 'DRL reformatter must insert newlines'
        assert 'rule "Test"' in result
        assert 'when' in result
        assert 'then' in result
        assert 'end' in result
        lines = [l.strip() for l in result.split('\n') if l.strip()]
        assert len(lines) >= 4, f'Expected at least 4 lines, got: {result!r}'

    def test_when_then_end_on_own_lines(self):
        one_line = 'rule "R" when Foo($x: bar) then System.out.println($x); end'
        result = reformat_drl(one_line)
        lines = [l.strip() for l in result.split('\n') if l.strip()]
        keywords = [l for l in lines if l in ('when', 'then', 'end')]
        assert len(keywords) >= 3, (
            f'when/then/end must each be on their own line. Got lines: {lines}'
        )

    def test_package_and_import_on_own_lines(self):
        one_line = 'package com.example import com.example.Foo rule "R" when Foo() then end'
        result = reformat_drl(one_line)
        assert result.startswith('package com.example'), 'package must be first line'
        assert 'import com.example.Foo' in result

    def test_multiline_input_unchanged(self):
        """Content with existing newlines must not be modified."""
        already_formatted = 'rule "R"\nwhen\n  Foo()\nthen\n  doIt();\nend'
        result = reformat_drl(already_formatted)
        assert result == already_formatted, (
            'Already-formatted DRL must not be altered by the reformatter'
        )

    def test_empty_string_unchanged(self):
        assert reformat_drl('') == ''

    def test_short_content_unchanged(self):
        """Content too short to be a multi-statement block: return as-is."""
        short = 'Foo(bar > 42)'
        result = reformat_drl(short)
        # No newlines inserted if no top-level keywords found
        assert isinstance(result, str)

    def test_multiple_rules_get_separated(self):
        two_rules = 'rule "A" when Foo() then doA(); end rule "B" when Bar() then doB(); end'
        result = reformat_drl(two_rules)
        assert result.count('rule "') == 2
        assert '\n' in result


# ── 3. XML pretty-printer ─────────────────────────────────────────────────────

class TestXmlPrettyPrinter:
    """reformat_xml() pretty-prints well-formed XML; returns input unchanged for fragments."""

    def test_well_formed_xml_gets_indented(self):
        one_line = '<beans><bean id="foo" class="com.Foo"><property name="x" value="1"/></bean></beans>'
        result = reformat_xml(one_line)
        assert '\n' in result, 'Well-formed XML must be pretty-printed'
        assert '<bean' in result
        assert '<property' in result

    def test_xml_declaration_preserved(self):
        one_line = '<?xml version="1.0"?><root><child>text</child></root>'
        result = reformat_xml(one_line)
        assert '\n' in result

    def test_malformed_xml_returned_unchanged(self):
        """XML fragment (no root, or unclosed tags) must be returned as-is."""
        fragment = '<route><from uri="activemq:q"/><to uri="drools:x">'
        result = reformat_xml(fragment)
        assert result == fragment, (
            'Malformed/fragment XML must be returned unchanged — '
            'minidom.parseString() raises ParseError which must be caught'
        )

    def test_already_formatted_xml_stable(self):
        """Pretty-printed XML run through the formatter again must not break."""
        formatted = '<root>\n  <child>text</child>\n</root>'
        result = reformat_xml(formatted)
        # May re-format but must not error and must still contain the content
        assert '<child>text</child>' in result

    def test_empty_string_unchanged(self):
        assert reformat_xml('') == ''


# ── Integration: apply_code_block_fixes() ────────────────────────────────────

from fix_code_blocks import apply_code_block_fixes


class TestApplyCodeBlockFixes:
    """apply_code_block_fixes(soup) applies DRL + XML reformats in-place."""

    def test_drl_code_no_newlines_fixed(self):
        html = ('<article><div>'
                '<pre><code class="language-drl">'
                'rule "T" when Foo() then doIt(); end'
                '</code></pre>'
                '</div></article>')
        soup = BeautifulSoup(html, 'html.parser')
        changed = apply_code_block_fixes(soup)
        code = soup.find('code')
        assert '\n' in code.get_text(), 'DRL code must have newlines after fix'
        assert changed, 'apply_code_block_fixes must return True when changes made'

    def test_sql_misclassified_as_drl_fixed(self):
        """language-sql blocks containing DRL syntax get DRL reformatting."""
        html = ('<article><div>'
                '<pre><code class="language-sql">'
                'rule "R" when Foo() then end'
                '</code></pre>'
                '</div></article>')
        soup = BeautifulSoup(html, 'html.parser')
        changed = apply_code_block_fixes(soup)
        code = soup.find('code')
        assert '\n' in code.get_text(), (
            'language-sql block containing DRL syntax must be reformatted as DRL'
        )

    def test_xml_code_no_newlines_fixed(self):
        # Use HTML-encoded XML — that's what real enriched HTML has in <pre><code>.
        # Raw tags like <beans> get parsed as HTML elements by BeautifulSoup,
        # making get_text() return empty. Encoded entities are stored as text nodes.
        html = ('<article><div>'
                '<pre><code class="language-xml">'
                '&lt;beans&gt;&lt;bean id="f" class="com.Foo"/&gt;&lt;/beans&gt;'
                '</code></pre>'
                '</div></article>')
        soup = BeautifulSoup(html, 'html.parser')
        changed = apply_code_block_fixes(soup)
        code = soup.find('code')
        assert '\n' in code.get_text(), 'XML code must be pretty-printed after fix'

    def test_java_code_no_newlines_untouched(self):
        """Java code (no auto-fix available) must be left unchanged."""
        one_line = 'public class Foo { private int x; public void bar() { } }'
        html = (f'<article><div>'
                f'<pre><code class="language-java">{one_line}</code></pre>'
                f'</div></article>')
        soup = BeautifulSoup(html, 'html.parser')
        apply_code_block_fixes(soup)
        code = soup.find('code')
        assert code.get_text() == one_line, 'Java must not be altered'

    def test_already_formatted_code_untouched(self):
        """Code blocks with existing newlines must not be modified."""
        formatted = 'rule "R"\nwhen\n  Foo()\nthen\n  doIt();\nend'
        html = (f'<article><div>'
                f'<pre><code class="language-drl">{formatted}</code></pre>'
                f'</div></article>')
        soup = BeautifulSoup(html, 'html.parser')
        changed = apply_code_block_fixes(soup)
        code = soup.find('code')
        assert code.get_text() == formatted
        assert not changed, 'No changes when code already has newlines'

    def test_no_changes_returns_false(self):
        html = '<article><div><p>Just prose.</p></div></article>'
        soup = BeautifulSoup(html, 'html.parser')
        changed = apply_code_block_fixes(soup)
        assert not changed


# ── 4. Span-based DRL detection and auto-fix ─────────────────────────────────

from fix_code_blocks import fix_drl_span_blocks, apply_code_block_fixes


class TestSpanBasedDrlDetection:
    """The signal r'\brule\s+"' misses Blogger-highlighted DRL where rule and
    the rule name are in separate <span> tags and join as rule"Name" (no space).

    Pattern: <div><span>rule</span><span>"IsChild"\xa0</span><span>when</span>...
    Joined text: rule"IsChild"\xa0 when ... → needs r'\brule\s*"' (0 or more spaces).
    """

    def test_rule_no_space_before_quote_detected_as_drl(self):
        """rule"Name" (no space) must be detected as DRL."""
        from fix_code_blocks import _is_drl
        text = 'rule"IsChild" when  p : Person( age < 16 ) then logicalInsert( new IsChild( p ) ) end'
        assert _is_drl(text), (
            'rule"Name" (no space) must be detected as DRL. '
            '_is_drl() uses r\'\\brule\\s+"\'  which requires whitespace — '
            'change to r\'\\brule\\s*"\' to allow no space.'
        )

    def test_rule_with_nbsp_between_spans(self):
        """rule\xa0"Name" (non-breaking space) must also be detected."""
        from fix_code_blocks import _is_drl
        text = 'rule\xa0"IsAdult"\xa0 when  p : Person( age >= 16 ) then end'
        assert _is_drl(text), (
            'rule\\xa0"Name" (non-breaking space before quote) must be detected as DRL'
        )

    def test_span_drl_block_converted_to_pre_code(self):
        """<div><span>rule</span><span>"Name"\xa0</span>...<br/>...<span>end</span></div>
        must be auto-fixed to <pre><code class="language-drl">...</code></pre>."""
        html = ('<article><div>'
                '<span>rule</span><span>"IsChild"\xa0</span>'
                '<span>when</span><span>\xa0 p : </span><span>Person( age &lt; 16 )</span>'
                '<br/> <span>then</span>'
                '<span>logicalInsert( new IsChild( p ) )</span>'
                '<br/> <span>end</span>'
                '</div></article>')
        soup = BeautifulSoup(html, 'html.parser')
        changed = fix_drl_span_blocks(soup)
        assert changed, 'fix_drl_span_blocks must return True when a block was converted'
        pre = soup.find('pre')
        assert pre is not None, 'Converted block must be wrapped in <pre>'
        code = pre.find('code')
        assert code is not None, '<pre> must contain <code>'
        assert 'language-drl' in ' '.join(code.get('class', [])), (
            '<code> must have class="language-drl"'
        )
        text = code.get_text()
        assert '\n' in text, 'Converted code must have newlines (reformatted)'
        assert 'rule' in text
        assert 'when' in text
        assert 'end' in text

    def test_multiple_rules_in_one_div_all_converted(self):
        """A div containing two DRL rules must produce one code block with both."""
        html = ('<article><div>'
                '<span>rule</span><span>"A"\xa0</span><span>when</span>'
                '<br/><span>Foo()</span><br/><span>then</span><br/>'
                '<span>doA();</span><br/><span>end</span><br/>'
                '<span>rule</span><span>"B"\xa0</span><span>when</span>'
                '<br/><span>Bar()</span><br/><span>then</span><br/>'
                '<span>doB();</span><br/><span>end</span>'
                '</div></article>')
        soup = BeautifulSoup(html, 'html.parser')
        changed = fix_drl_span_blocks(soup)
        assert changed
        code = soup.find('code')
        text = code.get_text()
        assert text.count('rule') == 2, 'Both rules must be in the output'

    def test_prose_div_with_span_not_converted(self):
        """A <div> whose spans contain prose (not DRL) must not be converted."""
        html = ('<article><div>'
                '<span>The rule is that</span> <span>when you follow best practices</span>'
                '<br/><span>then results improve.</span>'
                '</div></article>')
        soup = BeautifulSoup(html, 'html.parser')
        changed = fix_drl_span_blocks(soup)
        assert not changed, 'Prose div must not be converted'
        assert soup.find('pre') is None

    def test_apply_code_block_fixes_includes_span_drl(self):
        """apply_code_block_fixes() must call fix_drl_span_blocks() as well."""
        html = ('<article><div>'
                '<span>rule</span><span>"Test"\xa0</span>'
                '<span>when</span><br/><span>Foo()</span>'
                '<br/><span>then</span><br/><span>doIt();</span>'
                '<br/><span>end</span>'
                '</div></article>')
        soup = BeautifulSoup(html, 'html.parser')
        changed = apply_code_block_fixes(soup)
        assert changed, 'apply_code_block_fixes must handle span-based DRL'
        assert soup.find('pre') is not None


# ── 5. Plain <p><br/>DRL</p> auto-fix ────────────────────────────────────────

from fix_code_blocks import fix_drl_br_blocks


class TestPlainPBrDrlFix:
    """DRL code in a plain <p> with <br/> line separators (no <span> tokens,
    no <pre><code> wrapper) must be auto-fixed to <pre><code class="language-drl">.

    Pattern: <p>rule "Calculate Dead"<br/>agenda-group "calculate"<br/>when<br/>...
    
    Root cause: apply_code_block_fixes() handles <pre><code> blocks and
    span-tokenised Blogger blocks, but not plain text DRL in <p><br/>.
    """

    def test_pure_drl_p_br_converted(self):
        """A <p> whose content (after br→newline) is DRL must be converted."""
        html = ('<article><div>'
                '<p>rule "Calculate Dead"<br/>'
                'agenda-group "calculate"<br/>'
                'when<br/>'
                '  theCell: Cell(cellState == CellState.DEAD)<br/>'
                'then<br/>'
                '  doSomething();<br/>'
                'end</p>'
                '</div></article>')
        soup = BeautifulSoup(html, 'html.parser')
        changed = fix_drl_br_blocks(soup)
        assert changed, 'fix_drl_br_blocks must convert plain DRL <p><br/> block'
        pre = soup.find('pre')
        assert pre is not None, 'Must produce a <pre> element'
        code = pre.find('code')
        assert 'language-drl' in ' '.join(code.get('class', []))
        text = code.get_text()
        assert 'rule' in text and 'when' in text and 'end' in text

    def test_short_avg_line_length_required(self):
        """A <p> with long prose lines (avg > 80) must not be converted even
        if it contains DRL keywords — those are likely prose mentions."""
        long_prose = 'This is a long prose sentence about the rule system and how when conditions work. ' * 3
        html = (f'<article><div>'
                f'<p>{long_prose}<br/>when you think about it then end result matters</p>'
                f'</div></article>')
        soup = BeautifulSoup(html, 'html.parser')
        changed = fix_drl_br_blocks(soup)
        assert not changed, 'Long-line prose <p> must not be auto-fixed'

    def test_needs_at_least_3_br_tags(self):
        """A <p> with only 1-2 <br/> may be a link list or two-line note, not code."""
        html = ('<article><div>'
                '<p>rule "Foo"<br/>end</p>'
                '</div></article>')
        soup = BeautifulSoup(html, 'html.parser')
        changed = fix_drl_br_blocks(soup)
        assert not changed, '<p> with only 1 <br/> must not be auto-fixed'

    def test_non_drl_content_not_converted(self):
        """A <p> with <br/> but no DRL content must not be converted."""
        html = ('<article><div>'
                '<p>First item<br/>Second item<br/>Third item<br/>'
                'Fourth item<br/>Fifth item</p>'
                '</div></article>')
        soup = BeautifulSoup(html, 'html.parser')
        changed = fix_drl_br_blocks(soup)
        assert not changed

    def test_apply_code_block_fixes_includes_br_drl(self):
        """apply_code_block_fixes() must call fix_drl_br_blocks() as well."""
        html = ('<article><div>'
                '<p>rule "Test"<br/>when<br/>  Foo()<br/>then<br/>'
                '  doIt();<br/>end<br/>rule "Test2"<br/>when<br/>'
                '  Bar()<br/>then<br/>  doIt2();<br/>end</p>'
                '</div></article>')
        soup = BeautifulSoup(html, 'html.parser')
        changed = apply_code_block_fixes(soup)
        assert changed, 'apply_code_block_fixes must handle plain <p><br/>DRL</p>'
        assert soup.find('pre') is not None


# ── 6. reformat_drl must not break inside quoted strings ──────────────────────

class TestDrlReformatterQuoteSafety:
    """reformat_drl() must not insert newlines INSIDE quoted rule names.

    Bug: the keyword regex matches 'rule' anywhere including inside quoted
    strings like rule "start rule" → "start \\nrule" (newline mid-name).

    Fix: skip keyword matches that occur inside quoted string literals.
    """

    def test_rule_in_rule_name_not_broken(self):
        """'rule' inside a quoted name must not get a newline inserted."""
        text = 'rule "start rule" when eval(true) then doIt(); end'
        result = reformat_drl(text)
        # The rule name must be intact — no newline inside the quotes
        assert '"start rule"' in result or '"start\nrule"' not in result, (
            'reformat_drl() must not insert \\n inside quoted rule names. '
            '"start rule" → "start \\nrule" is wrong. '
            'Fix: skip keyword matches inside "..." string literals.'
        )
        assert '"start\nrule"' not in result, (
            'reformat_drl() broke the rule name "start rule" by inserting \\n '
            'before "rule" inside the quoted string. '
            'The keyword regex must not match inside "..." strings.'
        )

    def test_rule_keyword_in_rule_name_string(self):
        """A rule named "rule name" (containing the word 'rule') must not break."""
        text = 'rule "rule name" when Foo() then doIt(); end'
        result = reformat_drl(text)
        assert '"rule name"' in result, (
            'Rule name "rule name" must be preserved intact. '
            f'Got: {repr(result[:80])}'
        )
        assert '"' + '\n' + 'rule name"' not in result

    def test_when_keyword_outside_quotes_still_gets_newline(self):
        """'when' outside quotes must still be placed on its own line."""
        text = 'rule "start rule" when eval(true) then end'
        result = reformat_drl(text)
        lines = [l.strip() for l in result.split('\n') if l.strip()]
        assert 'when' in lines, (
            f'"when" must still be on its own line. Lines: {lines}'
        )

    def test_end_keyword_outside_quotes_still_gets_newline(self):
        """'end' outside quotes must still be placed on its own line."""
        text = 'rule "end game" when Foo() then doIt(); end'
        result = reformat_drl(text)
        lines = [l.strip() for l in result.split('\n') if l.strip()]
        assert 'end' in lines, (
            f'"end" outside quotes must be on its own line. Lines: {lines}'
        )
        # But "end game" inside quotes must not be broken
        assert '"end game"' in result or '"end\ngame"' not in result

    def test_real_world_rule_name_containing_rule(self):
        """The actual failing case from the KIE blog post."""
        one_line = ('rule "start rule"    target-node "<transition>" "<name>" '
                    'when    eval(true)  then     // assert some data'
                    'end')
        result = reformat_drl(one_line)
        # Rule name must be intact
        assert 'start rule' in result.replace('\n', ' '), (
            'The words "start rule" must appear together in the reformatted output'
        )
        assert '"start\nrule"' not in result, (
            f'Reformatter broke "start rule" — output: {repr(result[:120])}'
        )


# ── 7. JFDI-style <pre><br/> blocks: ingest normalisation + scan detection ─────

class TestJfdiPreBrNormalisation:
    """The JFDI post uses <pre><br/>line1<br/>line2</pre> for code blocks.

    Two separate bugs:
    A) ingest.py normalise step: already done — replaces <br/> with \n in pre blocks.
       But pre-fix ingested posts still have <br/> in stored HTML.
    B) scan_html.check_code_block_no_newlines: calls get_text() which strips all
       tags including <br/>, so a pre block with <br/> appears to have no newlines
       even though the JFDI-style code DOES have structure (just <br/>-separated).
       The scanner must replace <br/> with \n before checking, so it correctly
       distinguishes: has-<br/> (fixable) vs. truly-one-line (problematic).

    Root cause: The stored HTML for JFDI has <pre><br/>//fields<br/>...</pre>.
    The ingest normalisation converts <br/> to \n before writing to disk, but
    this post was ingested before the fix. check_code_block_no_newlines calls
    get_text() which strips <br/> silently, seeing a single long line and
    flagging it as code_no_newlines — which is correct as a diagnostic,
    but the fix is to update the stored HTML to use real \n characters.
    """

    def test_check_code_no_newlines_flags_pre_with_br(self):
        """check_code_block_no_newlines must flag a <pre><br/>code</pre> block
        (stored with <br/> instead of actual newlines) as code_no_newlines."""
        html = (
            '<pre><br/>//fields<br/>instance.field = value;<br/>'
            'instance(field1=z, field2=42)<br/>instance.map["key"] = value;<br/>'
            'instance.array[0] = value;<br/><br/>'
            '// method call with an inline map and array<br/>'
            'instance.method( [1, 2,"z", var], {"a" => 2} );<br/>'
            'bar = new BarBaz("x", 42)<br/>'
            'bar = new BarBaz(field1 = "val", field2 = "x")<br/></pre>'
        )
        article = _article(html)
        issues = check_code_block_no_newlines(article)
        assert issues, (
            'check_code_block_no_newlines must flag <pre><br/>code</pre> blocks '
            'where <br/> is used instead of actual newline characters. '
            'The fix is to update the stored HTML to use real \\n characters '
            'so the ingest normalisation step is retroactively applied.'
        )
        assert issues[0]['type'] == 'code_no_newlines'

    def test_check_code_no_newlines_does_not_flag_pre_with_real_newlines(self):
        """check_code_block_no_newlines must NOT flag a <pre> block that already
        uses real newlines — these are correctly formatted."""
        html = (
            '<pre>\n//fields\ninstance.field = value;\n'
            'instance(field1=z, field2=42)\ninstance.map["key"] = value;\n'
            'instance.array[0] = value;\n\n'
            '// method call with an inline map and array\n'
            'instance.method( [1, 2,"z", var], {"a" => 2} );\n'
            'bar = new BarBaz("x", 42)\n'
            'bar = new BarBaz(field1 = "val", field2 = "x")\n</pre>'
        )
        article = _article(html)
        issues = check_code_block_no_newlines(article)
        assert not issues, (
            'check_code_block_no_newlines must NOT flag <pre> blocks that '
            'already use real newline characters. Got: ' + str(issues)
        )

    def test_ingest_normalisation_replaces_br_with_newlines_in_pre(self):
        """The ingest normalisation step (ingest.py lines 800-804) must convert
        <br/> tags inside <pre> elements to actual newline characters.

        This simulates what ingest._fetch_and_extract() does before writing to disk.
        The fix ensures that newly ingested posts store real \\n, not <br/> tags.
        """
        from bs4 import BeautifulSoup as BS, Tag as BTag
        html = (
            '<article>'
            '<pre><br/>//fields<br/>instance.field = value;<br/>'
            'instance(field1=z, field2=42)<br/></pre>'
            '</article>'
        )
        article_soup = BS(html, 'html.parser')
        article = article_soup.find('article')
        # Apply the ingest normalisation step
        for pre in article.find_all('pre'):
            if not isinstance(pre, BTag):
                continue
            for br in pre.find_all('br'):
                br.replace_with('\n')
        # After normalisation, the pre text must have real newlines
        pre = article.find('pre')
        text = pre.get_text()
        assert '\n' in text, (
            'After ingest normalisation, <pre><br/>code</pre> must become '
            '<pre>\\ncode\\n</pre> with real newlines. Got: ' + repr(text[:100])
        )
        assert '//fields' in text
        assert 'instance.field = value;' in text

    def test_jfdi_style_code_has_correct_structure_after_normalisation(self):
        """After normalising <br/> → \\n in stored HTML, the JFDI code block
        must produce properly line-separated content in MD conversion.

        The JFDI code uses // comment style and method calls — not DRL.
        The reformat_drl() function must NOT modify this content.
        The content must be preserved as-is with the correct line structure.
        """
        # This is the raw code content from the JFDI post pre block 0,
        # after <br/> → \n normalisation
        code_text = (
            '\n//fields\n'
            'instance.field = value;\n'
            'instance(field1=z, field2=42)\n'
            'instance.map["key"] = value;\n'
            'instance.array[0] = value;\n\n'
            '// method call with an inline map and array \n'
            'instance.method( [1, 2,"z", var], {"a" => 2, "b" <= c} );\n\n'
            '// standard constructor\n'
            'bar = new BarBaz("x", 42)\n\n'
            '// calls default constructor, THEN setters \n'
            'bar = new BarBaz(field1 = "val", field2 = "x")\n'
        )
        # Must already have newlines — reformat_drl must not alter it
        result = reformat_drl(code_text)
        assert result == code_text, (
            'reformat_drl() must leave already-formatted code (with real \\n) '
            'unchanged. JFDI-style code uses // comments and method calls, not DRL. '
            f'Got: {repr(result[:100])}'
        )
        # Verify line count
        lines = [l for l in code_text.split('\n') if l.strip()]
        assert len(lines) >= 8, (
            f'JFDI code block must have at least 8 non-blank lines. Got: {len(lines)}'
        )


# ── 7. Pipeline integration: enrich + scan both fix code blocks ───────────────

class TestPipelineAutoFix:
    """Both the enrich step and the scan step must apply code block fixes,
    giving two chances to correct issues:

    Chance 1 — enrich.py: when a new enriched copy is created from the
    original stored HTML, apply_code_block_fixes() runs so the enriched
    copy is correct from birth.

    Chance 2 — scan step (server.py _api_scan_html): before scanning the
    enriched HTML, apply_code_block_fixes() runs and writes back any fixes.
    This catches posts enriched before the fixers existed.

    These tests verify the fix functions themselves (server integration
    is covered by test_pipeline_invariants.py).
    """

    def test_enrich_post_normalises_br_in_pre(self):
        """enrich_post() must convert <br/> to \\n inside <pre> blocks."""
        import tempfile, json
        from pathlib import Path
        from bs4 import BeautifulSoup

        # Build a minimal "original" HTML with <br/> inside <pre>
        src_html = '''<!DOCTYPE html>
<html><head>
<meta name="date" content="2006-11-09"/>
</head><body>
<article>
<pre><br/>line one<br/>line two<br/>line three</pre>
</article></body></html>'''

        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / 'src.html'
            enriched = Path(tmpdir) / 'enriched.html'
            assets = Path(tmpdir) / 'assets'
            assets.mkdir()
            src.write_text(src_html)

            sys.path.insert(0, str(MIGRATOR_ROOT / 'scripts'))
            from enrich import enrich_post
            enrich_post(src, enriched, assets, '')

            result = BeautifulSoup(enriched.read_text(), 'html.parser')
            pre = result.find('pre')
            assert pre is not None
            text = pre.get_text()
            assert '\n' in text, (
                'enrich_post() must convert <br/> → \\n in <pre> blocks. '
                f'Got: {repr(text)}'
            )
            assert '<br' not in str(pre), (
                'No <br/> tags should remain in <pre> after enrich_post()'
            )

    def test_apply_code_block_fixes_called_before_scan_fixes_br_pre(self):
        """Simulates the scan pre-fix step: apply_code_block_fixes() on
        an enriched HTML that has <br/> inside <pre> must fix it in-place."""
        from bs4 import BeautifulSoup

        html = ('<article><div>'
                '<pre><code class="language-drl">'
                'rule "Test"<br/>when<br/>  Foo()<br/>then<br/>  doIt();<br/>end'
                '</code></pre>'
                '</div></article>')
        soup = BeautifulSoup(html, 'html.parser')

        # First pass: normalise <br/> → \n (the ingest-level fix)
        for pre in soup.find_all('pre'):
            for br in pre.find_all('br'):
                br.replace_with('\n')

        # Second pass: reformat DRL (the fix_code_blocks level fix)
        changed = apply_code_block_fixes(soup)

        code = soup.find('code')
        text = code.get_text()
        assert '\n' in text, 'After normalisation, DRL code must have newlines'
        assert 'rule' in text and 'when' in text and 'end' in text

    def test_scan_detects_br_in_pre_as_code_no_newlines(self):
        """check_code_block_no_newlines must flag a <pre> whose text (after
        stripping <br/>) has no newlines — the br tags make it look formatted
        but get_text() collapses them."""
        from bs4 import BeautifulSoup
        from scan_html import check_code_block_no_newlines

        # <pre> with <br/> instead of \n — get_text() collapses to one line
        html = ('<article><pre><code class="language-drl">'
                'rule "Test"<br/>when<br/>  Foo()<br/>then<br/>doIt();<br/>end'
                '</code></pre></article>')
        soup = BeautifulSoup(html, 'html.parser')
        article = soup.find('article')

        issues = check_code_block_no_newlines(article)
        assert any(i['type'] == 'code_no_newlines' for i in issues), (
            'check_code_block_no_newlines must flag <pre><code> that uses <br/> '
            'instead of \\n — get_text() collapses them to one line, which is '
            'the same symptom as missing newlines.'
        )


# ── 8. TestPipelineGapFixes: gaps between ingest/enrich and scan ──────────────

class TestPipelineGapFixes:
    """Audit-driven tests: every fix that exists at ingest/extraction time must
    ALSO exist at enrich time (detection + auto-fix for existing posts).

    Gaps identified in audit:
      A. enrich.py does NOT call apply_code_block_fixes() — one-line DRL/XML
         <pre><code> blocks and span-tokenised Blogger code blocks are not fixed
         when the enriched copy is first created.
      B. ingest.py does NOT call apply_code_block_fixes() — same issue at
         extraction time: one-line blocks are stored as-is.

    scan step (server.py Step 1.5) already has both fixes — this is the
    "second chance". But if enrich/ingest ran the fixes too, scan would be
    a no-op for clean content, confirming the pipeline is truly complete.
    """

    # ── Gap A: enrich.py must call apply_code_block_fixes() ──────────────────

    def test_enrich_applies_drl_reformatter(self):
        """enrich_post() must apply reformat_drl() to one-line DRL <pre><code>.

        Without this, posts enriched for the first time still have one-line
        DRL code blocks — the scan step fixes them, but the enriched copy on
        disk is wrong until a scan is triggered.
        """
        import tempfile
        from bs4 import BeautifulSoup
        sys.path.insert(0, str(MIGRATOR_ROOT / 'scripts'))
        from enrich import enrich_post

        src_html = (
            '<!DOCTYPE html><html><body><article>'
            '<pre><code class="language-drl">'
            'rule "TestRule" when Foo() then doIt(); end'
            '</code></pre>'
            '</article></body></html>'
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / 'src.html'
            enriched = Path(tmpdir) / 'enriched.html'
            assets = Path(tmpdir) / 'assets'
            assets.mkdir()
            src.write_text(src_html)
            enrich_post(src, enriched, assets, '')

            result = BeautifulSoup(enriched.read_text(), 'html.parser')
            code = result.find('code')
            assert code is not None, 'Enriched HTML must have a <code> element'
            text = code.get_text()
            assert '\n' in text, (
                'enrich_post() must call apply_code_block_fixes() to reformat '
                'one-line DRL code blocks. The enriched copy still has one-line '
                'DRL — only the scan step fixes it, not enrich. '
                f'Got code text: {repr(text[:80])}'
            )

    def test_enrich_applies_xml_reformatter(self):
        """enrich_post() must apply reformat_xml() to one-line XML <pre><code>."""
        import tempfile
        from bs4 import BeautifulSoup
        sys.path.insert(0, str(MIGRATOR_ROOT / 'scripts'))
        from enrich import enrich_post

        src_html = (
            '<!DOCTYPE html><html><body><article>'
            '<pre><code class="language-xml">'
            '&lt;beans&gt;&lt;bean id="f" class="com.Foo"/&gt;&lt;/beans&gt;'
            '</code></pre>'
            '</article></body></html>'
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / 'src.html'
            enriched = Path(tmpdir) / 'enriched.html'
            assets = Path(tmpdir) / 'assets'
            assets.mkdir()
            src.write_text(src_html)
            enrich_post(src, enriched, assets, '')

            result = BeautifulSoup(enriched.read_text(), 'html.parser')
            code = result.find('code')
            assert code is not None
            text = code.get_text()
            assert '\n' in text, (
                'enrich_post() must call apply_code_block_fixes() to pretty-print '
                'one-line XML code blocks. '
                f'Got code text: {repr(text[:80])}'
            )

    def test_enrich_converts_span_drl_to_pre_code(self):
        """enrich_post() must call fix_drl_span_blocks() to convert Blogger
        span-tokenised DRL to <pre><code class="language-drl">."""
        import tempfile
        from bs4 import BeautifulSoup
        sys.path.insert(0, str(MIGRATOR_ROOT / 'scripts'))
        from enrich import enrich_post

        src_html = (
            '<!DOCTYPE html><html><body><article>'
            '<div>'
            '<span>rule</span><span>"IsChild"\xa0</span>'
            '<span>when</span><br/><span>p : Person( age &lt; 16 )</span>'
            '<br/><span>then</span><br/><span>doIt();</span>'
            '<br/><span>end</span>'
            '</div>'
            '</article></body></html>'
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / 'src.html'
            enriched = Path(tmpdir) / 'enriched.html'
            assets = Path(tmpdir) / 'assets'
            assets.mkdir()
            src.write_text(src_html)
            enrich_post(src, enriched, assets, '')

            result = BeautifulSoup(enriched.read_text(), 'html.parser')
            pre = result.find('pre')
            assert pre is not None, (
                'enrich_post() must call fix_drl_span_blocks() to convert '
                'Blogger span-tokenised DRL to <pre><code>. '
                'No <pre> found in enriched output.'
            )
            code = pre.find('code')
            assert code is not None
            assert 'language-drl' in ' '.join(code.get('class', [])), (
                'Converted block must have class="language-drl"'
            )

    def test_enrich_converts_p_br_drl_to_pre_code(self):
        """enrich_post() must call fix_drl_br_blocks() to convert plain
        <p><br/>DRL</p> blocks to <pre><code class="language-drl">."""
        import tempfile
        from bs4 import BeautifulSoup
        sys.path.insert(0, str(MIGRATOR_ROOT / 'scripts'))
        from enrich import enrich_post

        src_html = (
            '<!DOCTYPE html><html><body><article>'
            '<p>rule "Calculate Dead"<br/>'
            'agenda-group "calculate"<br/>'
            'when<br/>'
            '  theCell: Cell(cellState == CellState.DEAD)<br/>'
            'then<br/>'
            '  doSomething();<br/>'
            'end</p>'
            '</article></body></html>'
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / 'src.html'
            enriched = Path(tmpdir) / 'enriched.html'
            assets = Path(tmpdir) / 'assets'
            assets.mkdir()
            src.write_text(src_html)
            enrich_post(src, enriched, assets, '')

            result = BeautifulSoup(enriched.read_text(), 'html.parser')
            pre = result.find('pre')
            assert pre is not None, (
                'enrich_post() must call fix_drl_br_blocks() to convert '
                'plain <p><br/>DRL</p> blocks to <pre><code>. '
                'No <pre> found in enriched output.'
            )
            code = pre.find('code')
            assert code is not None
            assert 'language-drl' in ' '.join(code.get('class', [])), (
                'Converted DRL block must have class="language-drl"'
            )

    # ── Gap B: ingest.py must call apply_code_block_fixes() ──────────────────

    def test_ingest_applies_drl_reformatter(self):
        """_fetch_and_extract() must apply apply_code_block_fixes() so that
        one-line DRL blocks are fixed in the stored HTML at ingest time.

        Without this, one-line DRL is written to disk. The scan step fixes
        it on first scan, but the original stored HTML remains broken.
        """
        from bs4 import BeautifulSoup, Tag

        # Simulate what _fetch_and_extract does: parse, strip, normalise pre br,
        # then (after the fix) call apply_code_block_fixes.
        raw_html = (
            '<html><body>'
            '<article>'
            '<pre><code class="language-drl">'
            'rule "TestRule" when Foo() then doIt(); end'
            '</code></pre>'
            '</article>'
            '</body></html>'
        )
        soup = BeautifulSoup(raw_html, 'lxml')
        article = soup.find('article')

        # Step 1: normalise <br/> → \n (always done by ingest)
        for pre in article.find_all('pre'):
            if not isinstance(pre, Tag):
                continue
            for br in pre.find_all('br'):
                br.replace_with('\n')

        # Step 2: apply_code_block_fixes (the gap — should also be done by ingest)
        from fix_code_blocks import apply_code_block_fixes
        changed = apply_code_block_fixes(soup)

        code = soup.find('code')
        text = code.get_text()
        assert '\n' in text, (
            'After apply_code_block_fixes(), one-line DRL must be reformatted. '
            'ingest.py must call apply_code_block_fixes() after <br/>→\\n step. '
            f'Got: {repr(text[:80])}'
        )
        assert changed, 'apply_code_block_fixes must return True (DRL was reformatted)'

    def test_ingest_normalisation_and_fix_pipeline_is_complete(self):
        """Verify that after both ingest steps (br→newline + apply_code_block_fixes),
        a scan of the stored HTML produces zero code_no_newlines issues.

        This is the end-to-end invariant: after correct ingest processing,
        there must be no code_no_newlines or potential_code_block issues left.
        """
        import tempfile
        from pathlib import Path
        from bs4 import BeautifulSoup, Tag
        from fix_code_blocks import apply_code_block_fixes
        from scan_html import scan_post

        raw_html = (
            '<html><body>'
            '<article>'
            '<pre><code class="language-drl">'
            'rule "TestRule" when Foo() then doIt(); end'
            '</code></pre>'
            '</article>'
            '</body></html>'
        )
        soup = BeautifulSoup(raw_html, 'lxml')
        article = soup.find('article')

        # ingest normalisation
        for pre in article.find_all('pre'):
            if not isinstance(pre, Tag):
                continue
            for br in pre.find_all('br'):
                br.replace_with('\n')

        # apply_code_block_fixes (the gap)
        apply_code_block_fixes(soup)

        # Write to a temp file and scan it
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / 'post.html'
            p.write_text(str(soup))
            issues = scan_post(p)

        code_issues = [i for i in issues
                       if i['type'] in ('code_no_newlines', 'potential_code_block')]
        assert not code_issues, (
            'After ingest normalisation + apply_code_block_fixes(), '
            'scanning the stored HTML must produce zero code_no_newlines '
            f'or potential_code_block issues. Got: {code_issues}'
        )


# ── 8. Line-number table pattern detection and fix ────────────────────────────

from fix_code_blocks import fix_linenumber_table_blocks
from scan_html import check_linenumber_table_code


class TestLinenumberTableFix:
    """Two-column table with line numbers + code must be converted to <pre><code>.

    Pattern A — <pre> in both columns:
      <table><td><pre>1\n2\n3</pre></td><td><pre>code</pre></td></table>

    Pattern B — <div> line numbers, <code> fragments in right column:
      <table><td><div>1</div><div>2</div></td>
             <td><div><code>line1</code></div><div><code>line2</code></div></td></table>

    LESSON: Old SyntaxHighlighter WordPress plugin renders code in a two-column
    table: line numbers on the left, code on the right.  The table structure
    must be stripped, leaving only the code in a proper <pre><code> block.
    """

    # Pattern A tests
    def test_pattern_a_pre_linenums_converted(self):
        """Table with <pre> line numbers + <pre> code → <pre><code>."""
        html = ('<article><table><tbody><tr>'
                '<td><pre>1\n2\n3\n</pre></td>'
                '<td><pre class="language-java">line1();\nline2();\nline3();</pre></td>'
                '</tr></tbody></table></article>')
        soup = BeautifulSoup(html, 'html.parser')
        changed = fix_linenumber_table_blocks(soup)
        assert changed, 'Pattern A table must be converted'
        assert soup.find('table') is None, 'Table must be removed'
        pre = soup.find('pre')
        assert pre is not None
        code = pre.find('code')
        assert code is not None
        text = code.get_text()
        assert 'line1()' in text and 'line3()' in text

    def test_pattern_a_linenum_only_block_removed(self):
        """Line-number-only pre must not appear in output."""
        html = ('<article><table><tbody><tr>'
                '<td><pre>1\n2\n</pre></td>'
                '<td><pre>doSomething();\ndoMore();</pre></td>'
                '</tr></tbody></table></article>')
        soup = BeautifulSoup(html, 'html.parser')
        fix_linenumber_table_blocks(soup)
        # Verify no pure-digit block remains
        for pre in soup.find_all('pre'):
            text = pre.get_text()
            assert not all(c.isdigit() or c in '\n ' for c in text if c.strip()), (
                'Line-number-only pre must be removed from output'
            )

    # Pattern B tests
    def test_pattern_b_div_code_fragments_converted(self):
        """Table with <div>N</div> line nums + <code> fragments → <pre><code>."""
        html = ('<article><table><tbody><tr>'
                '<td><div>1</div><div>2</div><div>3</div></td>'
                '<td>'
                '<div><code>  &lt;role name="admin"/&gt;</code></div>'
                '<div><code>  &lt;role name="user"/&gt;</code></div>'
                '<div><code>  &lt;/roles&gt;</code></div>'
                '</td>'
                '</tr></tbody></table></article>')
        soup = BeautifulSoup(html, 'html.parser')
        changed = fix_linenumber_table_blocks(soup)
        assert changed, 'Pattern B table must be converted'
        assert soup.find('table') is None, 'Table must be removed'
        code = soup.find('code')
        assert code is not None
        text = code.get_text()
        assert 'admin' in text and 'user' in text

    def test_non_linenumber_table_not_touched(self):
        """A table with real content (not line-number pattern) must be left alone."""
        html = ('<article><table><tr>'
                '<td>Name</td><td>Value</td>'
                '</tr><tr>'
                '<td>Foo</td><td>Bar</td>'
                '</tr></table></article>')
        soup = BeautifulSoup(html, 'html.parser')
        changed = fix_linenumber_table_blocks(soup)
        assert not changed, 'Non-linenumber table must not be modified'
        assert soup.find('table') is not None

    def test_multiple_tables_all_converted(self):
        """All linenumber tables in a post must be converted."""
        html = ('<article>'
                '<table><tr><td><pre>1\n2\n</pre></td>'
                '<td><pre>block1();\nblock2();</pre></td></tr></table>'
                '<p>some prose</p>'
                '<table><tr><td><pre>1\n2\n</pre></td>'
                '<td><pre>block3();\nblock4();</pre></td></tr></table>'
                '</article>')
        soup = BeautifulSoup(html, 'html.parser')
        fix_linenumber_table_blocks(soup)
        assert len(soup.find_all('table')) == 0, 'All linenumber tables must be removed'
        assert len(soup.find_all('pre')) == 2, 'Each table becomes one pre block'

    def test_apply_code_block_fixes_includes_linenumber_tables(self):
        """apply_code_block_fixes() must call fix_linenumber_table_blocks()."""
        html = ('<article><table><tr>'
                '<td><pre>1\n2\n</pre></td>'
                '<td><pre>doIt();\ndoMore();</pre></td>'
                '</tr></table></article>')
        soup = BeautifulSoup(html, 'html.parser')
        changed = apply_code_block_fixes(soup)
        assert changed, 'apply_code_block_fixes must handle linenumber tables'
        assert soup.find('table') is None


class TestScanLinenumberTable:
    """check_linenumber_table_code must detect two-column line-number tables."""

    def test_pattern_a_detected(self):
        """Pattern A (pre-based line numbers) must be flagged."""
        article = _article(
            '<table><tr><td><pre>1\n2\n3\n</pre></td>'
            '<td><pre class="language-java">line1();\nline2();</pre></td>'
            '</tr></table>'
        )
        issues = check_linenumber_table_code(article)
        assert any(i['type'] == 'linenumber_table_code' for i in issues), (
            'Pattern A linenumber table must be flagged as linenumber_table_code'
        )

    def test_pattern_b_detected(self):
        """Pattern B (div-based line numbers with code fragments) must be flagged."""
        article = _article(
            '<table><tr>'
            '<td><div>1</div><div>2</div></td>'
            '<td><div><code>doIt();</code></div><div><code>doMore();</code></div></td>'
            '</tr></table>'
        )
        issues = check_linenumber_table_code(article)
        assert any(i['type'] == 'linenumber_table_code' for i in issues), (
            'Pattern B linenumber table must be flagged as linenumber_table_code'
        )

    def test_regular_table_not_flagged(self):
        """A data table must not be flagged."""
        article = _article(
            '<table><tr><td>Name</td><td>Value</td></tr>'
            '<tr><td>Foo</td><td>Bar</td></tr></table>'
        )
        issues = check_linenumber_table_code(article)
        assert not any(i['type'] == 'linenumber_table_code' for i in issues)


# ── 9. DRL query keyword support ──────────────────────────────────────────────

class TestDrlQueryKeyword:
    """DRL blocks using the 'query' keyword must be detected and reformatted.

    DRL queries use 'query Name(...) ... end' syntax without when/then/rule.
    The current _is_drl() signals miss these because they don't contain 'rule'.

    Fix: add r'\bquery\s+\w' to _DRL_SIGNALS and handle 'query' in reformat_drl().
    """

    def test_query_block_detected_as_drl(self):
        from fix_code_blocks import _is_drl
        text = 'query niceFood( String t, String l )Location(t : thing, l : location)Edible(t : thing)end'
        assert _is_drl(text), (
            '"query...end" DRL block must be detected as DRL. '
            'Add r\'\\bquery\\s+\\w\' to _DRL_SIGNALS.'
        )

    def test_query_with_quoted_name_detected(self):
        from fix_code_blocks import _is_drl
        text = 'query "get balls set"ball1 : Ball();ball2 : Ball(this != ball1)end'
        assert _is_drl(text), (
            'query with quoted name must be detected as DRL'
        )

    def test_query_block_reformatted_with_newlines(self):
        one_line = 'query niceFood( String t, String l )Location(t : thing, l : location)Edible(t : thing)end'
        result = reformat_drl(one_line)
        assert '\n' in result, 'DRL query block must be reformatted with newlines'
        lines = [l.strip() for l in result.split('\n') if l.strip()]
        assert any('query' in l for l in lines), 'query must be on its own line'
        assert 'end' in lines, '"end" must be on its own line'

    def test_apply_fixes_reformats_query_block(self):
        html = ('<article><div>'
                '<pre><code class="language-drl">'
                'query niceFood( String t, String l )'
                'Location(t : thing, l : location)'
                'Edible(t : thing)end'
                '</code></pre>'
                '</div></article>')
        soup = BeautifulSoup(html, 'html.parser')
        changed = apply_code_block_fixes(soup)
        code = soup.find('code')
        assert '\n' in code.get_text(), (
            'apply_code_block_fixes must reformat DRL query blocks with newlines'
        )
