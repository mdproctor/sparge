---
layout: post
title: "Phase 3: BeautifulSoup to Jsoup — porting DOM manipulation"
date: 2026-04-15
type: phase-update
entry_type: note
subtype: diary
projects: [sparge]
tags: [Quarkus, Java, Python, migration, Jsoup, BeautifulSoup, DOM]
typora-root-url: /Users/mdproctor/claude/sparge/docs
---

Phase 3 ports the HTML manipulation layer: a DRL code reformatter, an XML
pretty-printer, a code block fixer, and the HTML prettifier for the editor
view. Three different kinds of text transformation, each with its own story.

## The easy one: DRL reformatter

`reformat_drl()` takes a flat one-liner of Drools Rule Language and inserts
newlines at keyword boundaries. No DOM involved — pure text with a state
machine to track quoted strings.

```python
# Python
while i < text_len:
    ch = text[i]
    if ch == '"':
        in_quote = not in_quote
    if not in_quote:
        m = _DRL_KW_RE.match(text, i)
        if m:
            kw = m.group(1)
            if result_chars and result_chars[-1] != '\n':
                result_chars.append('\n')
            result_chars.append(kw)
            i = m.end()
            continue
    result_chars.append(ch)
    i += 1
```

```java
// Java — identical state machine
while (i < text.length()) {
    char ch = text.charAt(i);
    if (ch == '"') { inQuote = !inQuote; result.append(ch); i++; continue; }
    if (!inQuote) {
        Matcher m = DRL_KW_RE.matcher(text).region(i, text.length());
        if (m.lookingAt()) {
            String kw = m.group(1);
            if (!result.isEmpty() && result.charAt(result.length() - 1) != '\n')
                result.append('\n');
            result.append(kw);
            i = m.end();
            continue;
        }
    }
    result.append(ch);
    i++;
}
```

Pure text is pure text in any language. This is the lowest-friction port in
the whole migration. The only Java-specific choice: `Matcher.region()` to avoid
creating a substring for each position — the Python regex engine handles this
implicitly.

## The XML pretty-printer

Python uses `xml.dom.minidom`; Java uses `javax.xml`. Different API, identical
behaviour — both return the original text unchanged on malformed input. The
`javax.xml` API was designed in 2002 and it shows (TransformerFactory,
DOMSource, StreamResult, OutputKeys — a lot of scaffolding for indented XML).
But the logic is a straight port and the 5 test cases all pass on first run.

## The hard one: HTML prettification and the MARKER trick

![The MARKER trick — preserving inline adjacency through prettification](/blog-images/marker-trick.png)

BeautifulSoup (and Jsoup) puts every element on its own line when prettifying.
For inline elements like `<b>` and `<strong>`, this hides whether the closing
tag was immediately adjacent to the following character. That adjacency matters
— it's why html2text produces `**Bob Kowalski**(Imperial College London)` with
no space before the bracket, and why the editor needs to show the original
adjacency to make that visible.

The fix uses U+2060 (WORD JOINER) as an invisible marker. Before prettifying,
scan the DOM for inline elements whose next sibling starts with non-whitespace.
Prefix that sibling with ⁠. After prettification, two regex passes rejoin the
split lines. The marker distinguishes "was adjacent" from "happened to be on
the next line" — without it, both look identical after prettification.

The Java port uses the same approach. One gotcha: **Jsoup escapes non-ASCII
characters by default.** U+2060 becomes `&#x2060;` in the output, and the
regex stops matching.

```java
Document doc = Jsoup.parse(raw);
doc.outputSettings()
    .charset(StandardCharsets.UTF_8)   // U+2060 passes through unescaped
    .prettyPrint(true)
    .indentAmount(1);
```

With UTF-8 output set, Jsoup only escapes characters that are genuinely unsafe
in HTML (`<`, `>`, `&`, `"`, `'`). U+2060 passes through as the character
itself. One setting, found after the adjacency test failed and the output
revealed `&#x2060;` where ⁠ was expected.

## BeautifulSoup vs Jsoup: the syntax

Both APIs are pleasant. Jsoup's CSS selectors are more concise:

```python
# BeautifulSoup
soup = BeautifulSoup(html, 'html.parser')
for pre in soup.find_all('pre'):
    code = pre.find('code')
    classes = set(code.get('class', []))
    code.clear()
    code.append(formatted)
```

```java
// Jsoup
Document doc = Jsoup.parse(html);
for (Element pre : doc.select("pre")) {
    Element code = pre.selectFirst("code");
    Set<String> classes = code.classNames();
    code.text(formatted);
}
```

`select()` and `selectFirst()` take CSS selector strings. `classNames()` returns
a `Set<String>`. The mental model is identical; the Jsoup API is a bit cleaner.

## The XML-inside-code discovery

One genuine surprise: Jsoup parses `<root><child>text</child></root>` inside a
`<code>` element as actual DOM nodes, not as escaped text. `wholeOwnText()`
returns empty — there are no direct text node children, only element children.
BeautifulSoup treats code content as escaped text and doesn't have this
behaviour.

```java
// Doesn't work for XML content inside <code>
String text = code.wholeOwnText();   // returns "" if XML tags inside

// Works: use .html() when the element has child elements
String text = code.children().isEmpty()
    ? code.wholeOwnText()   // plain text content
    : code.html();          // XML or HTML markup
```

One line, found by running the test that checks XML code blocks get
pretty-printed, and seeing it produce no change instead of indented XML.

## The code block fixer

The code block fixer (`fix_code_blocks.py`) applies four separate passes to a
BeautifulSoup document:

1. `<pre><code>` blocks with no newlines — DRL and XML get formatted
2. Blogger span-tokenised DRL blocks — converted to `<pre><code class="language-drl">`
3. Plain `<p>/<div>` with `<br/>` line breaks containing DRL — same conversion
4. Two-column line-number + code tables — stripped of line numbers, converted to `<pre><code>`

All four passes use the same DRL detection signals (six regex patterns covering
`rule`, `query`, `when/then`, `drools`, `insert/retract/modify`). The Java port
uses `Matcher.find()` against the same patterns; the soup-manipulation methods
use Jsoup's `select()`, `clone()`, and `replaceWith()`.

14 JUnit tests, all written before the implementation. All 14 pass.

## Where we are

JEP call count: **27 → 26**. The HTML editor view now runs entirely in Java —
`HtmlUtils.prettifyHtml()` reads the file, prettifies with Jsoup, returns
text/plain. Phase 4 is the scan pipeline: `scan_html.py`, nine issue types,
Jsoup CSS selectors. That one removes far more JEP calls at once.
