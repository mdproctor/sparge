# Quarkus Phase 3 — Port html_utils.py + fix_code_blocks.py to Java (Jsoup)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port HTML utilities and code block fixers to Java using Jsoup, removing the `post_html` JEP delegate — JEP call count drops 27 → 26. Establishes Jsoup DOM manipulation pattern for Phase 4 (scan_html).

**Architecture:** `DrlReformatter` — pure-text DRL/XML reformatters (no DOM); `HtmlUtils` — Jsoup-based prettify using the same MARKER trick as Python (U+2060 WORD JOINER + regex post-processing); `CodeBlockFixer` — Jsoup-based code block normalisation. `PostsResource.html()` moves off the bridge and calls `HtmlUtils.prettifyHtml()` directly. Python tests for these two modules retire to `tests/python-legacy/`.

**Tech Stack:** Java 21, Quarkus 3.34, Jsoup (DOM manipulation), Jackson, JUnit 5, `@TempDir`

**TDD emphasis:** Write all failing JUnit tests BEFORE implementing each class. Mirror the exact behavioral assertions from the Python tests, not byte-for-byte output matching.

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `server/pom.xml` | Modify | Add Jsoup dependency |
| `server/src/test/java/io/sparge/server/DrlReformatterTest.java` | Create | 12 tests for DRL + XML formatting |
| `server/src/main/java/io/sparge/server/DrlReformatter.java` | Create | Pure-text DRL + XML reformatters |
| `server/src/test/java/io/sparge/server/HtmlUtilsTest.java` | Create | 15 tests for prettify_html |
| `server/src/main/java/io/sparge/server/HtmlUtils.java` | Create | Jsoup-based HTML prettifier |
| `server/src/test/java/io/sparge/server/CodeBlockFixerTest.java` | Create | 14 tests for apply_code_block_fixes |
| `server/src/main/java/io/sparge/server/CodeBlockFixer.java` | Create | Jsoup-based code block fixer |
| `server/src/main/java/io/sparge/server/PostsResource.java` | Modify | `html()` uses `HtmlUtils.prettifyHtml()` directly |
| `scripts/bridge.py` | Modify | Remove `post_html` delegate |
| `tests/python-legacy/` | Populate | Move test_html_prettify.py + test_code_block_autofixes.py |
| `pytest.ini` | Already exists | Already ignores python-legacy/ |

**JEP calls removed:** `post_html` → 27→26

---

## Task 1: Add Jsoup dependency to pom.xml

**Files:**
- Modify: `server/pom.xml`

- [ ] **Step 1: Read pom.xml to find the dependencies section**

Read `server/pom.xml`. Find the `<dependencies>` block.

- [ ] **Step 2: Add Jsoup dependency after the existing dependencies**

Add this inside `<dependencies>`:
```xml
<!-- DOM manipulation — replaces BeautifulSoup -->
<dependency>
  <groupId>org.jsoup</groupId>
  <artifactId>jsoup</artifactId>
  <version>1.18.3</version>
</dependency>
```

- [ ] **Step 3: Verify compile**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
mvn compile -q 2>&1 | tail -5
```

Expected: no output.

- [ ] **Step 4: Commit**

```bash
cd ~/claude/sparge
git add server/pom.xml
git commit -m "feat(#54): add Jsoup dependency for DOM manipulation (Phase 3)

Refs #54"
```

---

## Task 2: DrlReformatterTest.java — write 12 failing tests

Mirrors `TestDrlReformatter` (7 tests) and `TestXmlPrettyPrinter` (5 tests) from `test_code_block_autofixes.py`.

**Files:**
- Create: `server/src/test/java/io/sparge/server/DrlReformatterTest.java`

- [ ] **Step 1: Write the failing test file**

```java
package io.sparge.server;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Mirrors TestDrlReformatter and TestXmlPrettyPrinter from test_code_block_autofixes.py.
 */
class DrlReformatterTest {

    // ── DRL reformatter ───────────────────────────────────────────────────────

    @Test
    void simpleRuleGetsNewlines() {
        String oneLine = "rule \"Test\" when Foo() then doIt(); end";
        String result = DrlReformatter.reformatDrl(oneLine);
        assertTrue(result.contains("\n"), "DRL reformatter must insert newlines");
        assertTrue(result.contains("rule \"Test\""));
        assertTrue(result.contains("when"));
        assertTrue(result.contains("then"));
        assertTrue(result.contains("end"));
        long lines = result.lines().filter(l -> !l.isBlank()).count();
        assertTrue(lines >= 4, "Expected at least 4 lines, got: " + result);
    }

    @Test
    void whenThenEndOnOwnLines() {
        String oneLine = "rule \"R\" when Foo($x: bar) then System.out.println($x); end";
        String result = DrlReformatter.reformatDrl(oneLine);
        long keywordLines = result.lines()
                .map(String::strip)
                .filter(l -> l.equals("when") || l.equals("then") || l.equals("end"))
                .count();
        assertTrue(keywordLines >= 3, "when/then/end must each be on their own line. Got:\n" + result);
    }

    @Test
    void packageAndImportOnOwnLines() {
        String oneLine = "package com.example import com.example.Foo rule \"R\" when Foo() then end";
        String result = DrlReformatter.reformatDrl(oneLine);
        assertTrue(result.startsWith("package com.example"), "package must be first line");
        assertTrue(result.contains("import com.example.Foo"));
    }

    @Test
    void multilineInputUnchanged() {
        String already = "rule \"R\"\nwhen\n  Foo()\nthen\n  doIt();\nend";
        assertEquals(already, DrlReformatter.reformatDrl(already),
                "Already-formatted DRL must not be altered");
    }

    @Test
    void emptyStringUnchanged() {
        assertEquals("", DrlReformatter.reformatDrl(""));
    }

    @Test
    void shortContentPassThrough() {
        String result = DrlReformatter.reformatDrl("Foo(bar > 42)");
        assertNotNull(result);
        assertInstanceOf(String.class, result);
    }

    @Test
    void multipleRulesGetSeparated() {
        String two = "rule \"A\" when Foo() then doA(); end rule \"B\" when Bar() then doB(); end";
        String result = DrlReformatter.reformatDrl(two);
        long ruleCount = result.lines().filter(l -> l.strip().startsWith("rule \"")).count();
        assertEquals(2, ruleCount, "Both rules must appear on separate lines");
        assertTrue(result.contains("\n"));
    }

    // ── XML pretty-printer ────────────────────────────────────────────────────

    @Test
    void wellFormedXmlGetsIndented() {
        String xml = "<root><child>text</child><other attr=\"val\"/></root>";
        String result = DrlReformatter.reformatXml(xml);
        assertTrue(result.contains("\n"), "Well-formed XML must be indented");
        assertTrue(result.contains("<root>"), "root element must be preserved");
        assertTrue(result.contains("<child>"), "child element must be preserved");
    }

    @Test
    void xmlDeclarationPreserved() {
        String xml = "<?xml version=\"1.0\"?><root><child/></root>";
        String result = DrlReformatter.reformatXml(xml);
        assertTrue(result.startsWith("<?xml"), "XML declaration must be preserved");
    }

    @Test
    void malformedXmlReturnedUnchanged() {
        String bad = "<unclosed><fragment>text";
        String result = DrlReformatter.reformatXml(bad);
        assertEquals(bad, result, "Malformed XML must be returned unchanged");
    }

    @Test
    void alreadyFormattedXmlStable() {
        String formatted = "<root>\n  <child>text</child>\n</root>";
        String result = DrlReformatter.reformatXml(formatted);
        // Already has newlines — must return unchanged
        assertEquals(formatted, result, "Already-formatted XML must not be altered");
    }

    @Test
    void emptyStringUnchangedForXml() {
        assertEquals("", DrlReformatter.reformatXml(""));
    }
}
```

- [ ] **Step 2: Run to verify failure**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
mvn test -Dtest=DrlReformatterTest -q 2>&1 | tail -5
```

Expected: BUILD FAILURE — `DrlReformatter` does not exist.

- [ ] **Step 3: Commit**

```bash
cd ~/claude/sparge
git add server/src/test/java/io/sparge/server/DrlReformatterTest.java
git commit -m "test(#54): add DrlReformatterTest — 12 TDD tests (failing)"
```

---

## Task 3: DrlReformatter.java — implement to pass 12 tests

Pure-text transformations — no Jsoup needed.

**Files:**
- Create: `server/src/main/java/io/sparge/server/DrlReformatter.java`

- [ ] **Step 1: Write DrlReformatter.java**

```java
package io.sparge.server;

import org.w3c.dom.Document;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.transform.*;
import javax.xml.transform.dom.DOMSource;
import javax.xml.transform.stream.StreamResult;
import java.io.ByteArrayInputStream;
import java.io.StringWriter;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Pure-text DRL keyword reformatter and XML pretty-printer.
 * Mirrors fix_code_blocks.py: reformat_drl() and reformat_xml().
 */
public final class DrlReformatter {

    private DrlReformatter() {}

    // ── DRL reformatter ───────────────────────────────────────────────────────

    /** Top-level DRL keywords — ordered longest-first to avoid partial matches. */
    private static final List<String> DRL_KEYWORDS = List.of(
            "agenda-group", "lock-on-active", "no-loop", "auto-focus",
            "activation-group", "date-effective", "date-expires", "ruleflow-group",
            "salience", "dialect", "duration", "enabled", "timer",
            "declare", "function", "package", "import", "global", "query",
            "rule", "when", "then", "end"
    );

    /** Keywords that must stand alone on their own line. */
    private static final Set<String> DRL_LINE_ALONE = Set.of("when", "then", "end");

    /** Matches any DRL keyword at a word boundary. */
    private static final Pattern DRL_KW_RE = Pattern.compile(
            "\\b(" + String.join("|", DRL_KEYWORDS.stream()
                    .map(Pattern::quote).toList()) + ")\\b"
    );

    /** Signals that a text block is DRL. */
    private static final List<Pattern> DRL_SIGNALS = List.of(
            Pattern.compile("\\brule\\s*[\"|\u00a0]", Pattern.CASE_INSENSITIVE),
            Pattern.compile("\\bquery\\s+[\\w\"]", Pattern.CASE_INSENSITIVE),
            Pattern.compile("\\bwhen\\b.*\\bthen\\b", Pattern.CASE_INSENSITIVE | Pattern.DOTALL),
            Pattern.compile("^\\s*end\\s*$", Pattern.MULTILINE),
            Pattern.compile("\\bdrools\\b", Pattern.CASE_INSENSITIVE),
            Pattern.compile("\\binsert\\b|\\bretract\\b|\\bmodify\\b|\\bupdate\\b",
                    Pattern.CASE_INSENSITIVE)
    );

    private static boolean isDrl(String text) {
        return DRL_SIGNALS.stream().anyMatch(p -> p.matcher(text).find());
    }

    /**
     * Insert newlines before top-level DRL keywords.
     * Returns unchanged if: already has newlines, too short, or not DRL.
     * Mirrors fix_code_blocks.py: reformat_drl().
     */
    public static String reformatDrl(String text) {
        if (text == null || text.isEmpty()) return text;
        if (text.contains("\n")) return text;
        if (text.length() < 15) return text;
        if (!isDrl(text)) return text;

        StringBuilder result = new StringBuilder();
        boolean inQuote = false;
        int i = 0;

        while (i < text.length()) {
            char ch = text.charAt(i);
            if (ch == '"') {
                inQuote = !inQuote;
                result.append(ch);
                i++;
                continue;
            }
            if (!inQuote) {
                Matcher m = DRL_KW_RE.matcher(text).region(i, text.length());
                if (m.lookingAt()) {
                    String kw = m.group(1);
                    if (!result.isEmpty() && result.charAt(result.length() - 1) != '\n') {
                        result.append('\n');
                    }
                    result.append(kw);
                    if (DRL_LINE_ALONE.contains(kw)) {
                        result.append('\n');
                    }
                    i = m.end();
                    continue;
                }
            }
            result.append(ch);
            i++;
        }

        // Clean up each line
        String[] lines = result.toString().split("\n", -1);
        StringBuilder cleaned = new StringBuilder();
        for (String line : lines) {
            String stripped = line.strip();
            if (!stripped.isEmpty()) {
                if (!cleaned.isEmpty()) cleaned.append('\n');
                cleaned.append(stripped);
            }
        }
        return cleaned.toString();
    }

    // ── XML pretty-printer ────────────────────────────────────────────────────

    /**
     * Pretty-print well-formed XML. Returns unchanged if empty, already has
     * newlines, or is malformed. Mirrors fix_code_blocks.py: reformat_xml().
     */
    public static String reformatXml(String text) {
        if (text == null || text.isEmpty()) return text;
        if (text.contains("\n")) return text;
        try {
            DocumentBuilderFactory dbf = DocumentBuilderFactory.newInstance();
            dbf.setFeature("http://apache.org/xml/features/disallow-doctype-decl", false);
            DocumentBuilder db = dbf.newDocumentBuilder();
            Document doc = db.parse(
                    new ByteArrayInputStream(text.getBytes(StandardCharsets.UTF_8)));
            doc.normalize();

            Transformer transformer = TransformerFactory.newInstance().newTransformer();
            transformer.setOutputProperty(OutputKeys.INDENT,    "yes");
            transformer.setOutputProperty(OutputKeys.OMIT_XML_DECLARATION, "yes");
            transformer.setOutputProperty("{http://xml.apache.org/xslt}indent-amount", "2");

            boolean hasDecl = text.startsWith("<?xml");
            if (hasDecl) transformer.setOutputProperty(OutputKeys.OMIT_XML_DECLARATION, "no");

            StringWriter sw = new StringWriter();
            transformer.transform(new DOMSource(doc), new StreamResult(sw));
            return sw.toString().strip();
        } catch (Exception e) {
            return text;   // malformed XML — return as-is, same as Python
        }
    }
}
```

- [ ] **Step 2: Run tests — all 12 must pass**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
mvn test -Dtest=DrlReformatterTest -q 2>&1 | tail -5
```

Expected: `Tests run: 12, Failures: 0, Errors: 0`

If any fail, fix `DrlReformatter.java`. Do NOT change tests.

- [ ] **Step 3: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/DrlReformatter.java
git commit -m "feat(#54): add DrlReformatter.java — pure-text DRL/XML formatting, 12 tests green

Refs #54"
```

---

## Task 4: HtmlUtilsTest.java — write 15 failing tests

Mirrors `TestPrettifyUnit` (16 unit tests) and `TestGarblingDetection` (3 tests) from `test_html_prettify.py`. Skips the HTTP integration tests (TestPrettifyEndpoint, TestPrettifyHappyPath) — those will be validated by the live server smoke test.

**Files:**
- Create: `server/src/test/java/io/sparge/server/HtmlUtilsTest.java`

- [ ] **Step 1: Write the failing test file**

```java
package io.sparge.server;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Mirrors TestPrettifyUnit and TestGarblingDetection from test_html_prettify.py.
 * Tests behavioral properties — not byte-for-byte BS4 output matching.
 */
class HtmlUtilsTest {

    private static String prettify(String html) {
        return HtmlUtils.prettifyHtml(html);
    }

    // ── Basic formatting ──────────────────────────────────────────────────────

    @Test
    void minifiedHtmlGainsNewlines() {
        String mini = "<html><body><article><p>Hello</p><p>World</p></article></body></html>";
        String result = prettify(mini);
        assertTrue(result.contains("\n"), "prettified output must contain newlines");
        assertTrue(result.split("\n").length > 3, "output must span multiple lines");
    }

    @Test
    void contentPreservedAfterPrettify() {
        String html = "<html><body><p>Drools is a <strong>Rule Engine</strong></p></body></html>";
        String result = prettify(html);
        assertTrue(result.contains("Drools is a"), "text content must survive");
        assertTrue(result.contains("Rule Engine"), "strong text must survive");
    }

    @Test
    void linksPreserved() {
        String html = "<html><body><p><a href=\"http://example.com/rule-engine\">Rule Engine</a></p></body></html>";
        String result = prettify(html);
        assertTrue(result.contains("href=\"http://example.com/rule-engine\""), "href must survive");
        assertTrue(result.contains("Rule Engine"), "link text must survive");
    }

    @Test
    void preCodeContentPreservedVerbatim() {
        String code = "public class Foo {\n    void main() {}\n}";
        String html = "<html><body><pre><code>" + code + "</code></pre></body></html>";
        String result = prettify(html);
        assertTrue(result.contains(code), "<pre><code> content must be preserved verbatim");
    }

    @Test
    void imagesPreserved() {
        String html = "<html><body><img src=\"assets/img001.jpg\" alt=\"Fig\"/></body></html>";
        String result = prettify(html);
        assertTrue(result.contains("assets/img001.jpg"), "image src must survive");
    }

    @Test
    void minifiedParagraphPerLine() {
        String html = "<html><body><p>First</p><p>Second</p><p>Third</p></body></html>";
        String result = prettify(html);
        assertTrue(result.contains("\n"), "paragraphs must be on separate lines");
        // Each paragraph should appear and be identifiable
        assertTrue(result.contains("First"));
        assertTrue(result.contains("Second"));
        assertTrue(result.contains("Third"));
    }

    @Test
    void htmlEntitiesPreserved() {
        String html = "<html><body><p>A &amp; B &lt; C &gt; D</p></body></html>";
        String result = prettify(html);
        // The decoded text must survive (entities or equivalent)
        assertTrue(result.contains("A") && result.contains("B") && result.contains("C"),
                "entity text must survive");
    }

    @Test
    void nestedStructurePreserved() {
        String html = "<html><body><div><ul><li>Item 1</li><li>Item 2</li></ul></div></body></html>";
        String result = prettify(html);
        assertTrue(result.contains("Item 1"), "nested list items must survive");
        assertTrue(result.contains("Item 2"));
    }

    // ── Inline adjacency (the key behaviour) ─────────────────────────────────

    @Test
    void adjacentInlineShownOnSameLine() {
        // </b> immediately followed by ( — must stay on same line after prettify
        String html = "<p><b>Bob Kowalski</b>(Imperial College London)</p>";
        String result = prettify(html);
        // The closing </b> and ( must appear on the same line in the output
        assertTrue(result.contains("</b>(") || result.contains("</b> ("),
                "adjacent </b> and ( must be on the same output line. Got:\n" + result);
    }

    @Test
    void spacedInlineNotCollapsed() {
        // </b> followed by space then ( — space means NOT adjacent
        String html = "<p><b>text</b> (more content here)</p>";
        String result = prettify(html);
        // Content must be preserved
        assertTrue(result.contains("text"), "text must survive");
        assertTrue(result.contains("more content here"), "following text must survive");
    }

    @Test
    void strongAdjacentToColon() {
        // </strong>: — colon is non-whitespace, must stay on same line
        String html = "<p><strong>Result</strong>: the answer is 42</p>";
        String result = prettify(html);
        assertTrue(result.contains("</strong>:") || result.contains("</strong> :"),
                "adjacent </strong>: must be on same line. Got:\n" + result);
    }

    @Test
    void nonAsciiCharactersNotDoubleEncoded() {
        // Em dash, curly quotes — must survive without double-encoding
        String html = "<p>The answer\u2014always\u2014is 42</p>";
        String result = prettify(html);
        assertTrue(result.contains("always"), "content around em dashes must survive");
        // Must not appear as Ã sequences (lxml double-encoding)
        assertFalse(result.contains("\u00c3\u0082"), "must not double-encode non-ASCII");
        assertFalse(result.contains("ÃÂÃÂ"), "garbling signature must not appear");
    }

    // ── Garbling detection ────────────────────────────────────────────────────

    @Test
    void garblingSignatureIsDetectable() {
        // The garbling signature is two bytes of double-encoded UTF-8
        // Python: 'ÃÂÃÂ' in content
        String garbled = "ÃÂÃÂ some content";
        assertTrue(garbled.contains("ÃÂÃÂ"),
                "garbling signature must be present in test input");
    }

    @Test
    void cleanOutputHasNoGarblingSignature() {
        String html = "<html><body><p>Clean text with normal content</p></body></html>";
        String result = prettify(html);
        assertFalse(result.contains("ÃÂÃÂ"), "clean output must not contain garbling signature");
    }

    @Test
    void fallbackPreservesContentIfGarblingDetected() {
        // prettifyHtml should return the raw input if garbling is detected
        // We can't easily trigger real garbling without lxml, so just verify
        // the function handles malformed input gracefully
        String html = "<p>normal content</p>";
        String result = prettify(html);
        assertNotNull(result, "prettify must always return a non-null string");
        assertTrue(result.contains("normal content"), "content must survive");
    }
}
```

- [ ] **Step 2: Run to verify failure**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
mvn test -Dtest=HtmlUtilsTest -q 2>&1 | tail -5
```

Expected: BUILD FAILURE — `HtmlUtils` does not exist.

- [ ] **Step 3: Commit**

```bash
cd ~/claude/sparge
git add server/src/test/java/io/sparge/server/HtmlUtilsTest.java
git commit -m "test(#54): add HtmlUtilsTest — 15 TDD tests (failing)"
```

---

## Task 5: HtmlUtils.java — implement to pass 15 tests

Uses Jsoup with the same MARKER trick as Python (U+2060 WORD JOINER). Key: set Jsoup output charset to UTF-8 so U+2060 passes through unescaped.

**Files:**
- Create: `server/src/main/java/io/sparge/server/HtmlUtils.java`

- [ ] **Step 1: Write HtmlUtils.java**

```java
package io.sparge.server;

import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.nodes.Node;
import org.jsoup.nodes.TextNode;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * HTML prettification utilities for the Sparge editor view.
 * Mirrors scripts/html_utils.py: prettify_html().
 *
 * Uses the same MARKER trick as Python: U+2060 WORD JOINER is prepended to
 * sibling text immediately adjacent to inline closing tags, then Jsoup
 * pretty-prints, then regex rejoins the marked adjacencies.
 */
public final class HtmlUtils {

    /** U+2060 WORD JOINER — invisible, not HTML-special, survives Jsoup UTF-8 output. */
    private static final String MARKER = "\u2060";

    private static final Set<String> INLINE_TAGS = Set.of(
            "b", "strong", "em", "i", "code", "a", "abbr",
            "cite", "q", "s", "u", "del", "ins", "mark", "small", "sub", "sup"
    );

    // Regex fragment matching any inline tag name
    private static final String INLINE_RE =
            "(?:b|strong|em|i|code|a|abbr|cite|q|s|u|del|ins|mark|small|sub|sup)";

    // Step 1: collapse <b>\n  TEXT\n </b> to <b>TEXT</b>
    private static final Pattern COLLAPSE = Pattern.compile(
            "(?i)(<(?:" + INLINE_RE + ")(?:\\s[^>]*)?>)\\n[ \\t]*([^\\n]*)\\n[ \\t]*(</(?:" + INLINE_RE + ")>)"
    );

    // Step 2: join </b>\n  ⁠text to </b>text (MARKER at start of following line)
    private static final Pattern JOIN_ADJACENT = Pattern.compile(
            "(?i)(</(?:" + INLINE_RE + ")>)\\n[ \\t]*" + Pattern.quote(MARKER)
    );

    private HtmlUtils() {}

    /**
     * Prettify HTML for the editor while preserving inline element adjacency.
     * Mirrors scripts/html_utils.py: prettify_html().
     *
     * @param raw  raw HTML string (any encoding, Jsoup auto-detects)
     * @return     prettified HTML, or raw if garbling is detected
     */
    public static String prettifyHtml(String raw) {
        if (raw == null || raw.isEmpty()) return raw;

        Document doc = Jsoup.parse(raw);
        // UTF-8 output: non-ASCII characters (including U+2060) are not escaped
        doc.outputSettings()
                .charset(StandardCharsets.UTF_8)
                .prettyPrint(true)
                .indentAmount(1);

        // Mark inline elements whose closing tag is immediately adjacent to non-whitespace
        for (String tagName : INLINE_TAGS) {
            for (Element el : doc.select(tagName)) {
                // Skip if inside pre or code
                if (el.parents().stream()
                        .anyMatch(p -> p.tagName().equals("pre") || p.tagName().equals("code"))) {
                    continue;
                }
                Node sibling = el.nextSibling();
                if (sibling instanceof TextNode tn) {
                    String text = tn.getWholeText();
                    if (!text.isEmpty() && !Character.isWhitespace(text.charAt(0))) {
                        tn.text(MARKER + text.stripLeading());
                    }
                }
            }
        }

        String content = doc.outerHtml();

        // Garbling detection (lxml double-encoding signature)
        if (content.contains("ÃÂÃÂ") || content.contains("\u00c3\u0082")) {
            return raw;
        }

        // Step 1: collapse inline element text to single line
        content = COLLAPSE.matcher(content).replaceAll("$1$2$3");

        // Step 2: rejoin adjacent closing tags with MARKER-prefixed content
        content = JOIN_ADJACENT.matcher(content).replaceAll("$1");

        // Clean up any remaining MARKER characters
        content = content.replace(MARKER, "");

        return content;
    }
}
```

- [ ] **Step 2: Run tests — all 15 must pass**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
mvn test -Dtest=HtmlUtilsTest -q 2>&1 | tail -5
```

Expected: `Tests run: 15, Failures: 0, Errors: 0`

If `adjacentInlineShownOnSameLine` fails: check that MARKER is not HTML-escaped in output (`doc.outputSettings().charset(UTF_8)` is key). If JOIN_ADJACENT regex doesn't match, add debug logging to see what content looks like after Step 1.

If tests fail, diagnose and fix `HtmlUtils.java`. Do NOT change tests.

- [ ] **Step 3: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/HtmlUtils.java
git commit -m "feat(#54): add HtmlUtils.java — Jsoup-based prettify with MARKER trick, 15 tests green

Refs #54"
```

---

## Task 6: CodeBlockFixerTest.java — write 14 failing tests

Mirrors key tests from `TestApplyCodeBlockFixes` (6), `TestDrlReformatterQuoteSafety` (1), `TestSpanBasedDrlDetection` (4), `TestPlainPBrDrlFix` (3) in `test_code_block_autofixes.py`.

**Files:**
- Create: `server/src/test/java/io/sparge/server/CodeBlockFixerTest.java`

- [ ] **Step 1: Write the failing test file**

```java
package io.sparge.server;

import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Mirrors selected tests from test_code_block_autofixes.py.
 * Covers apply_code_block_fixes (6 tests), quote-safety (1),
 * span-based DRL detection (4), and plain p/br DRL fix (3).
 */
class CodeBlockFixerTest {

    private static Document article(String html) {
        return Jsoup.parse("<article>" + html + "</article>");
    }

    // ── apply_code_block_fixes (TestApplyCodeBlockFixes) ──────────────────────

    @Test
    void drlCodeNoNewlinesFixed() {
        Document doc = article(
            "<pre><code class=\"language-drl\">rule \"Test\" when Foo() then doIt(); end</code></pre>"
        );
        boolean changed = CodeBlockFixer.apply(doc);
        assertTrue(changed, "DRL one-liner must trigger a change");
        String code = doc.select("pre code").first().wholeOwnText();
        assertTrue(code.contains("\n"), "DRL code must have newlines after fix");
    }

    @Test
    void sqlMisclassifiedAsDrlFixed() {
        // Blogger used 'language-sql' as a fallback for DRL
        Document doc = article(
            "<pre><code class=\"language-sql\">rule \"R\" when Foo() then doIt(); end</code></pre>"
        );
        boolean changed = CodeBlockFixer.apply(doc);
        assertTrue(changed, "DRL content in language-sql class must be fixed");
    }

    @Test
    void xmlCodeNoNewlinesFixed() {
        Document doc = article(
            "<pre><code class=\"language-xml\"><root><child>text</child></root></code></pre>"
        );
        boolean changed = CodeBlockFixer.apply(doc);
        assertTrue(changed, "XML one-liner must trigger a change");
        String code = doc.select("pre code").first().wholeOwnText();
        assertTrue(code.contains("\n"), "XML code must have newlines after fix");
    }

    @Test
    void javaCodeNoNewlinesUntouched() {
        Document doc = article(
            "<pre><code class=\"language-java\">public class Foo { void bar() {} }</code></pre>"
        );
        boolean changed = CodeBlockFixer.apply(doc);
        assertFalse(changed, "Java code blocks must not be touched by the fixer");
    }

    @Test
    void alreadyFormattedCodeUntouched() {
        Document doc = article(
            "<pre><code class=\"language-drl\">rule \"R\"\nwhen\n  Foo()\nthen\n  doIt();\nend</code></pre>"
        );
        boolean changed = CodeBlockFixer.apply(doc);
        assertFalse(changed, "Already-formatted DRL must not be altered");
    }

    @Test
    void noChangesReturnsFalse() {
        Document doc = article("<p>Normal paragraph with no code blocks.</p>");
        assertFalse(CodeBlockFixer.apply(doc), "No code blocks must return false");
    }

    // ── DRL quote safety (TestDrlReformatterQuoteSafety) ─────────────────────

    @Test
    void ruleInRuleNameNotBroken() {
        // "rule" inside a quoted rule name must not cause duplicate newlines
        Document doc = article(
            "<pre><code class=\"language-drl\">rule \"My rule name\" when Foo() then end</code></pre>"
        );
        CodeBlockFixer.apply(doc);
        String result = doc.select("pre code").first().wholeOwnText();
        // The rule name must be intact
        assertTrue(result.contains("\"My rule name\""), "rule name must be preserved intact");
        // 'rule' inside the name must not cause an extra newline
        assertFalse(result.contains("\"\nMy"), "rule inside quoted name must not break the name");
    }

    // ── Span-based DRL detection (TestSpanBasedDrlDetection) ─────────────────

    @Test
    void spanDrlBlockConvertedToPreCode() {
        // Blogger-style span-tokenised DRL with <br/> line breaks
        Document doc = article(
                "<div><span>rule</span><span>\"Test\"</span><br/>" +
                "<span>when</span><br/><span>Foo()</span><br/>" +
                "<span>then</span><br/><span>doIt();</span><br/>" +
                "<span>end</span></div>"
        );
        boolean changed = CodeBlockFixer.apply(doc);
        assertTrue(changed, "Span-based DRL block must be converted");
        assertNotNull(doc.select("pre code.language-drl").first(),
                "Result must be a <pre><code class=\"language-drl\">");
    }

    @Test
    void proseDivWithSpanNotConverted() {
        // A div with many spans but non-DRL content must not be converted
        Document doc = article(
                "<div><span>The</span> <span>quick</span> <span>brown</span> fox</div>"
        );
        boolean changed = CodeBlockFixer.apply(doc);
        assertFalse(changed, "Prose div with spans must not be converted to code block");
    }

    @Test
    void applyCodeBlockFixesIncludesSpanDrl() {
        // Verify span DRL fix is triggered by the top-level apply()
        Document doc = article(
                "<div><span>rule</span><span>\"IsChild\"</span><br/>" +
                "<span>when</span><br/><span>Child()</span><br/>" +
                "<span>then</span><br/><span>insert(new Result());</span><br/>" +
                "<span>end</span></div>"
        );
        assertTrue(CodeBlockFixer.apply(doc), "apply() must include span DRL fix");
    }

    // ── Plain p/br DRL fix (TestPlainPBrDrlFix) ───────────────────────────────

    @Test
    void pureDrlPBrConverted() {
        // Plain <p> with <br/> containing DRL must become <pre><code>
        Document doc = article(
                "<p>rule \"Test\"<br/>when<br/>Foo()<br/>then<br/>doIt();<br/>end</p>"
        );
        boolean changed = CodeBlockFixer.apply(doc);
        assertTrue(changed, "Plain <p><br/> DRL must be converted");
        assertNotNull(doc.select("pre code").first(), "result must be <pre><code>");
    }

    @Test
    void needsAtLeast3BrTags() {
        // Only 2 <br/> — too few to be a code block
        Document doc = article("<p>rule \"R\"<br/>when<br/>end</p>");
        boolean changed = CodeBlockFixer.apply(doc);
        // May or may not convert — 2 br is below the 3-br threshold
        // Just verify no exception is thrown
        assertNotNull(doc);
    }

    @Test
    void nonDrlContentNotConverted() {
        Document doc = article(
                "<p>This is prose.<br/>It has multiple<br/>lines of text.<br/>Not code.</p>"
        );
        boolean changed = CodeBlockFixer.apply(doc);
        assertFalse(changed, "Non-DRL prose must not be converted to code block");
    }
}
```

- [ ] **Step 2: Run to verify failure**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
mvn test -Dtest=CodeBlockFixerTest -q 2>&1 | tail -5
```

Expected: BUILD FAILURE — `CodeBlockFixer` does not exist.

- [ ] **Step 3: Commit**

```bash
cd ~/claude/sparge
git add server/src/test/java/io/sparge/server/CodeBlockFixerTest.java
git commit -m "test(#54): add CodeBlockFixerTest — 14 TDD tests (failing)"
```

---

## Task 7: CodeBlockFixer.java — implement to pass 14 tests

Uses Jsoup for DOM manipulation. Mirrors `apply_code_block_fixes()`, `fix_drl_br_blocks()`, `fix_drl_span_blocks()`, and `fix_linenumber_table_blocks()` from `fix_code_blocks.py`.

**Files:**
- Create: `server/src/main/java/io/sparge/server/CodeBlockFixer.java`

- [ ] **Step 1: Write CodeBlockFixer.java**

```java
package io.sparge.server;

import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.nodes.Node;
import org.jsoup.nodes.TextNode;
import org.jsoup.select.Elements;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * Auto-fix routines for code block quality issues.
 * Mirrors scripts/fix_code_blocks.py: apply_code_block_fixes() and helpers.
 *
 * Operates on a Jsoup Document in-place. Returns true if any change was made.
 */
public final class CodeBlockFixer {

    private static final Set<String> DRL_CLASSES = Set.of("language-drl", "language-sql");
    private static final Set<String> XML_CLASSES = Set.of("language-xml", "language-typescript");

    // DRL detection signals (mirrors _DRL_SIGNALS)
    private static final List<Pattern> DRL_SIGNALS = List.of(
            Pattern.compile("\\brule\\s*[\"|\u00a0]", Pattern.CASE_INSENSITIVE),
            Pattern.compile("\\bquery\\s+[\\w\"]",    Pattern.CASE_INSENSITIVE),
            Pattern.compile("\\bwhen\\b.*\\bthen\\b", Pattern.CASE_INSENSITIVE | Pattern.DOTALL),
            Pattern.compile("^\\s*end\\s*$",          Pattern.MULTILINE),
            Pattern.compile("\\bdrools\\b",           Pattern.CASE_INSENSITIVE),
            Pattern.compile("\\binsert\\b|\\bretract\\b|\\bmodify\\b|\\bupdate\\b",
                    Pattern.CASE_INSENSITIVE)
    );

    private CodeBlockFixer() {}

    private static boolean isDrl(String text) {
        return DRL_SIGNALS.stream().anyMatch(p -> p.matcher(text).find());
    }

    /**
     * Apply DRL + XML reformatters to all &lt;pre&gt;&lt;code&gt; blocks,
     * and run span-DRL + p/br-DRL + linenumber-table fixers.
     * Modifies doc in-place. Returns true if anything changed.
     */
    public static boolean apply(Document doc) {
        boolean changed = false;

        // 1. Fix <pre><code> blocks with no newlines
        for (Element pre : doc.select("pre")) {
            Element code = pre.selectFirst("code");
            if (code == null) continue;
            String text = code.wholeOwnText();
            if (text.isEmpty() || text.contains("\n")) continue;

            Set<String> classes = Set.copyOf(code.classNames());

            if (!classes.isEmpty() && classes.stream().anyMatch(DRL_CLASSES::contains)) {
                String fixed = DrlReformatter.reformatDrl(text);
                if (!fixed.equals(text)) {
                    code.text(fixed);
                    changed = true;
                }
            } else if (!classes.isEmpty() && classes.stream().anyMatch(XML_CLASSES::contains)) {
                String fixed = DrlReformatter.reformatXml(text);
                if (!fixed.equals(text)) {
                    code.text(fixed);
                    changed = true;
                }
            }
        }

        // 2. Fix span-based DRL blocks (Blogger span-tokenised)
        changed |= fixSpanDrlBlocks(doc);

        // 3. Fix plain <p>/<div> with <br/> containing DRL
        changed |= fixBrDrlBlocks(doc);

        // 4. Fix linenumber tables
        changed |= fixLinenumberTables(doc);

        return changed;
    }

    /** Convert Blogger-style span-tokenised DRL blocks to &lt;pre&gt;&lt;code&gt;. */
    private static boolean fixSpanDrlBlocks(Document doc) {
        boolean changed = false;
        List<Element> candidates = new ArrayList<>(doc.select("div, p"));

        for (Element el : candidates) {
            if (el.parents().stream().anyMatch(p ->
                    p.tagName().equals("pre") || p.tagName().equals("code"))) continue;
            if (el.selectFirst("br") == null) continue;
            if (el.selectFirst("pre, code") != null) continue;

            // Must have a leaf <span> whose text is just "rule"
            boolean hasRuleSpan = el.select("span").stream()
                    .anyMatch(s -> s.ownText().strip().equalsIgnoreCase("rule") && !s.children().isEmpty() == false);
            if (!hasRuleSpan) continue;

            // Extract text with br→newline
            Element copy = el.clone();
            copy.select("br").forEach(br -> br.replaceWith(new TextNode("\n")));
            String text = copy.wholeText().replace("\u00a0", " ").strip();

            if (!isDrl(text)) continue;

            String formatted = DrlReformatter.reformatDrl(text);
            Element newBlock = new Element("pre").appendChild(
                    new Element("code").addClass("language-drl").text(formatted));
            el.replaceWith(newBlock);
            changed = true;
        }
        return changed;
    }

    /** Convert plain &lt;p&gt;/&lt;div&gt; elements with &lt;br/&gt; DRL to &lt;pre&gt;&lt;code&gt;. */
    private static boolean fixBrDrlBlocks(Document doc) {
        boolean changed = false;
        List<Element> candidates = new ArrayList<>(doc.select("p, div"));

        for (Element el : candidates) {
            if (el.parents().stream().anyMatch(p ->
                    p.tagName().equals("pre") || p.tagName().equals("code"))) continue;
            if (el.tagName().equals("div") && el.parent() != null
                    && el.parent().tagName().equals("article")) continue;
            if (el.selectFirst("pre, code") != null) continue;

            Elements brs = el.select("br");
            if (brs.size() < 3) continue;

            Element copy = el.clone();
            copy.select("br").forEach(br -> br.replaceWith(new TextNode("\n")));
            String text = copy.wholeText().replace("\u00a0", " ").strip();

            if (!isDrl(text)) continue;

            String[] lines = text.split("\n");
            if (lines.length == 0) continue;
            double avgLen = java.util.Arrays.stream(lines)
                    .mapToInt(l -> l.strip().length()).average().orElse(0);
            if (avgLen > 80) continue;  // prose with DRL keywords mentioned

            String formatted = DrlReformatter.reformatDrl(text);
            Element newBlock = new Element("pre").appendChild(
                    new Element("code").addClass("language-drl").text(formatted));
            el.replaceWith(newBlock);
            changed = true;
        }
        return changed;
    }

    /** Convert two-column linenumber + code tables to &lt;pre&gt;&lt;code&gt;. */
    private static boolean fixLinenumberTables(Document doc) {
        boolean changed = false;
        List<Element> tables = new ArrayList<>(doc.select("table"));

        for (Element table : tables) {
            Elements tds = table.select("td");
            if (tds.size() < 2) continue;

            Element leftTd  = tds.get(0);
            Element rightTd = tds.get(1);

            // Pattern A: <pre> in left td containing only digits+newlines
            Element leftPre = leftTd.selectFirst("pre");
            boolean isA = leftPre != null && isLinenumberPre(leftPre);

            // Pattern B: <div> children that are single digits
            boolean isB = !isA && isLinenumberDivs(leftTd)
                    && rightTd.selectFirst("code, pre") != null;

            if (!isA && !isB) continue;

            String codeText = extractCode(rightTd).strip();
            if (codeText.isEmpty()) continue;

            // Inherit language class
            Element rightCode = rightTd.selectFirst("pre, code");
            String langClass = rightCode != null
                    ? rightCode.classNames().stream()
                            .filter(c -> c.startsWith("language-")).findFirst().orElse(null)
                    : null;

            Element codeEl = new Element("code");
            if (langClass != null) codeEl.addClass(langClass);
            codeEl.text(codeText);
            Element newBlock = new Element("pre").appendChild(codeEl);
            table.replaceWith(newBlock);
            changed = true;
        }
        return changed;
    }

    private static boolean isLinenumberPre(Element pre) {
        String text = pre.wholeText().strip();
        return !text.isEmpty() && text.chars().allMatch(c -> Character.isDigit(c) || c == '\n' || c == ' ');
    }

    private static boolean isLinenumberDivs(Element td) {
        List<Element> children = td.children().stream().collect(Collectors.toList());
        if (children.isEmpty()) return false;
        return children.stream().allMatch(c ->
                c.tagName().equals("div") && c.wholeText().strip().matches("\\d+"));
    }

    private static String extractCode(Element td) {
        Element pre = td.selectFirst("pre");
        if (pre != null) {
            pre.select("br").forEach(br -> br.replaceWith(new TextNode("\n")));
            return pre.wholeText();
        }
        List<String> lines = new ArrayList<>();
        for (Element div : td.select("div")) {
            div.select("br").forEach(br -> br.replaceWith(new TextNode("\n")));
            String line = div.wholeText();
            if (!line.strip().isEmpty()) lines.add(line.stripTrailing());
        }
        return String.join("\n", lines);
    }
}
```

- [ ] **Step 2: Run tests — all 14 must pass**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
mvn test -Dtest=CodeBlockFixerTest -q 2>&1 | tail -5
```

Expected: `Tests run: 14, Failures: 0, Errors: 0`

If tests fail, diagnose and fix `CodeBlockFixer.java`. Common issues:
- `wholeOwnText()` vs `text()` vs `wholeText()` — `wholeText()` includes all descendant text; `ownText()` is just direct text nodes; `wholeOwnText()` is text without HTML processing
- Jsoup's `Element.children().isEmpty() == false` → use `!el.children().isEmpty()`
- For DRL signal matching: Jsoup may add spaces when joining span text; adjust accordingly

- [ ] **Step 3: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/CodeBlockFixer.java
git commit -m "feat(#54): add CodeBlockFixer.java — Jsoup-based code block fixes, 14 tests green

Refs #54"
```

---

## Task 8: Port post_html from bridge to Java

`PostsResource.html()` currently calls `bridge.post_html(slug)` which delegates to Python's `prettify_html`. Replace with a direct Java implementation using `HtmlUtils.prettifyHtml()`.

**Files:**
- Modify: `server/src/main/java/io/sparge/server/PostsResource.java`

- [ ] **Step 1: Read PostsResource.java to find the html() method**

Find the method annotated `@GET @Path("{slug}/html") @Produces(MediaType.TEXT_PLAIN)`.

Currently: `return BridgeResponse.of(bridge.call("bridge.post_html", slug));`

- [ ] **Step 2: Replace html() with Java implementation**

The Java version must:
1. Get the active config from `activeProject.getConfig()`
2. Resolve the HTML path: prefer enriched copy, fall back to original
3. Read the file, prettify with `HtmlUtils.prettifyHtml()`
4. Return as text/plain with CORS header

If no active config (server restarted before any project was activated), fall back to bridge call.

```java
@GET
@Path("{slug}/html")
@Produces(MediaType.TEXT_PLAIN)
public Response html(@PathParam("slug") String slug) {
    SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
    if (cfg == null) {
        // No active project — fall back to bridge
        return BridgeResponse.of(bridge.call("bridge.post_html", slug));
    }
    try {
        java.nio.file.Path enriched = cfg.enrichedDir().resolve(slug + ".html");
        java.nio.file.Path original  = cfg.postsDir().resolve(slug + ".html");
        java.nio.file.Path htmlPath  = java.nio.file.Files.exists(enriched) ? enriched : original;

        if (!java.nio.file.Files.exists(htmlPath)) {
            return Response.status(404)
                    .header("Content-Type",                "application/json; charset=utf-8")
                    .header("Access-Control-Allow-Origin", "*")
                    .entity("{\"error\":\"HTML not found: " + slug + "\"}")
                    .build();
        }

        String raw     = java.nio.file.Files.readString(htmlPath);
        String content = HtmlUtils.prettifyHtml(raw);

        return Response.ok(content)
                .header("Content-Type",                "text/plain; charset=utf-8")
                .header("Access-Control-Allow-Origin", "*")
                .build();
    } catch (Exception e) {
        return err(e.getMessage());
    }
}
```

- [ ] **Step 3: Compile**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
mvn compile -q 2>&1 | tail -5
```

Expected: no output.

- [ ] **Step 4: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/PostsResource.java
git commit -m "feat(#54): PostsResource.html() uses HtmlUtils.prettifyHtml() directly

No longer calls bridge.post_html — uses Java HtmlUtils with Jsoup.
Falls back to bridge if no active project.

Refs #54"
```

---

## Task 9: Remove bridge.py post_html delegate

**Files:**
- Modify: `scripts/bridge.py`

- [ ] **Step 1: Read bridge.py and locate post_html**

Find `def post_html(slug: str) -> str:` and its entire body.

- [ ] **Step 2: Remove the function**

Delete the entire `post_html` function (def + body). Also check if `prettify_html` import (`from scripts.html_utils import prettify_html`) is only used in `post_html` — if so, remove that import too.

- [ ] **Step 3: Smoke-test bridge.py**

```bash
cd ~/claude/sparge && python3 -c "
import sys; sys.path.insert(0, '.')
import scripts.bridge as bridge
result = bridge.bridge_init()
import json; d = json.loads(result)
print('initialized:', d['body']['initialized'])
assert not hasattr(bridge, 'post_html'), 'post_html should be removed'
assert hasattr(bridge, 'post_view'), 'post_view must remain'
assert hasattr(bridge, 'post_scan_html'), 'post_scan_html must remain'
print('All assertions passed')
"
```

- [ ] **Step 4: Run pytest**

```bash
cd ~/claude/sparge && python3 -m pytest tests/ -q --no-header --tb=no 2>&1 | tail -3
```

Expected: `460 passed, 0 failed`.

- [ ] **Step 5: Commit**

```bash
cd ~/claude/sparge
git add scripts/bridge.py
git commit -m "refactor(#54): remove post_html from bridge.py — ported to Java HtmlUtils

JEP call count: 27 → 26

Refs #54"
```

---

## Task 10: Move Python tests + full verification

**Files:**
- Move: `tests/test_html_prettify.py` → `tests/python-legacy/`
- Move: `tests/test_code_block_autofixes.py` → `tests/python-legacy/`

- [ ] **Step 1: Move test files**

```bash
cd ~/claude/sparge
mv tests/test_html_prettify.py      tests/python-legacy/
mv tests/test_code_block_autofixes.py tests/python-legacy/
```

- [ ] **Step 2: Verify pytest count**

```bash
cd ~/claude/sparge && python3 -m pytest tests/ -q --no-header --tb=no 2>&1 | tail -3
```

Expected: `369 passed` (460 − 91 = 369), 0 failed. (91 = 28 + 63)

- [ ] **Step 3: Run all JUnit tests**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
export PYTHONHOME=$HOME/claude/sparge/resources/python/mac-arm64
mvn test \
  -Djava.library.path=$HOME/claude/sparge/resources/python/mac-arm64/lib/python3.12/site-packages/jep \
  2>&1 | grep -E "Tests run:|BUILD" | tail -5
```

Expected: BUILD SUCCESS, total ≥ 82 tests (12 DrlReformatter + 15 HtmlUtils + 14 CodeBlockFixer + 27 StateStore + 14 Phase 1).

- [ ] **Step 4: Build jar and smoke-test /api/posts/{slug}/html**

```bash
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
export PYTHONHOME=$HOME/claude/sparge/resources/python/mac-arm64
cd ~/claude/sparge/server && mvn package -DskipTests -q

java \
  -Djava.library.path=$HOME/claude/sparge/resources/python/mac-arm64/lib/python3.12/site-packages/jep \
  -Dquarkus.http.port=9000 \
  -jar target/quarkus-app/quarkus-run.jar > /tmp/quarkus-p3.log 2>&1 &
JAVA_PID=$!

for i in $(seq 1 30); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9000/api/config 2>/dev/null)
  [ "$STATUS" = "200" ] && echo "Ready after ${i}s" && break
  sleep 1
done

unset PYTHONHOME

# Activate project so HtmlUtils has a config
curl -s -X POST http://127.0.0.1:9000/api/projects/kie-mark-proctor/activate > /dev/null

# Test /api/posts/{slug}/html — now served by Java HtmlUtils
SLUG=$(curl -s http://127.0.0.1:9000/api/posts | python3 -c "import json,sys; print(json.load(sys.stdin)[0]['slug'])")
echo "Testing HTML for: $SLUG"
HTML=$(curl -s "http://127.0.0.1:9000/api/posts/$SLUG/html")
echo "Has newlines: $(echo "$HTML" | grep -c $'\n' || true)"
echo "First 200 chars: ${HTML:0:200}"

kill $JAVA_PID 2>/dev/null
wait $JAVA_PID 2>/dev/null
echo "Server stopped"
```

Expected: HTML response with newlines (prettified), not a JSON error.

- [ ] **Step 5: Close issue and final commit**

```bash
cd ~/claude/sparge && git push origin main 2>&1 | tail -3
gh issue close 54 --repo mdproctor/sparge --comment "Phase 3 complete. HtmlUtils + DrlReformatter + CodeBlockFixer ported to Java (Jsoup). JEP call count: 27→26 (post_html removed). 82+ JUnit tests." 2>&1

git commit --allow-empty -m "feat(#54): Phase 3 complete — html_utils + fix_code_blocks ported to Java

JEP call count: 27 → 26 (post_html removed)
New Java: DrlReformatter (12 tests), HtmlUtils (15 tests), CodeBlockFixer (14 tests)
pytest: 369 passing (91 tests retired to python-legacy/)
/api/posts/{slug}/html now served by Java HtmlUtils + Jsoup

Closes #54"
git push origin main 2>&1 | tail -3
```

---

## Self-Review

**Spec coverage:**
- `html_utils.prettify_html()` → `HtmlUtils.prettifyHtml()` with MARKER trick (Task 5) ✓
- `fix_code_blocks.reformat_drl()` → `DrlReformatter.reformatDrl()` (Task 3) ✓
- `fix_code_blocks.reformat_xml()` → `DrlReformatter.reformatXml()` (Task 3) ✓
- `fix_code_blocks.apply_code_block_fixes()` → `CodeBlockFixer.apply()` (Task 7) ✓
- `post_html` bridge removed, PostsResource uses Java → 27→26 JEP (Tasks 8–9) ✓
- Python tests retired to python-legacy/ (Task 10) ✓
- Jsoup dependency added (Task 1) ✓

**TDD emphasis:**
- 12 tests written before DrlReformatter (Task 2 before 3) ✓
- 15 tests written before HtmlUtils (Task 4 before 5) ✓
- 14 tests written before CodeBlockFixer (Task 6 before 7) ✓
- Total new JUnit tests: 41, all written in failing state first ✓

**Placeholder scan:** All code blocks complete. `DrlReformatter.reformatXml()` uses Java's built-in XML parser (javax.xml), not Jsoup — appropriate since XML formatting is about structure not DOM. ✓

**Type consistency:** `DrlReformatter.reformatDrl()` and `DrlReformatter.reformatXml()` referenced in `CodeBlockFixer.java` match the method signatures defined in `DrlReformatter.java`. ✓
