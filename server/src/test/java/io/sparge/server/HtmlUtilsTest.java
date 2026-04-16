package io.sparge.server;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class HtmlUtilsTest {

    private static String prettify(String html) {
        return HtmlUtils.prettifyHtml(html);
    }

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
        assertTrue(result.contains("First"));
        assertTrue(result.contains("Second"));
        assertTrue(result.contains("Third"));
    }

    @Test
    void htmlEntitiesPreserved() {
        String html = "<html><body><p>A &amp; B &lt; C &gt; D</p></body></html>";
        String result = prettify(html);
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

    @Test
    void adjacentInlineShownOnSameLine() {
        // </b> immediately followed by ( — must stay on same line after prettify
        String html = "<p><b>Bob Kowalski</b>(Imperial College London)</p>";
        String result = prettify(html);
        assertTrue(result.contains("</b>(") || result.contains("</b> ("),
                "adjacent </b> and ( must be on the same output line. Got:\n" + result);
    }

    @Test
    void spacedInlineNotCollapsed() {
        String html = "<p><b>text</b> (more content here)</p>";
        String result = prettify(html);
        assertTrue(result.contains("text"), "text must survive");
        assertTrue(result.contains("more content here"), "following text must survive");
    }

    @Test
    void strongAdjacentToColon() {
        String html = "<p><strong>Result</strong>: the answer is 42</p>";
        String result = prettify(html);
        assertTrue(result.contains("</strong>:") || result.contains("</strong> :"),
                "adjacent </strong>: must be on same line. Got:\n" + result);
    }

    @Test
    void nonAsciiCharactersNotDoubleEncoded() {
        String html = "<p>The answer\u2014always\u2014is 42</p>";
        String result = prettify(html);
        assertTrue(result.contains("always"), "content around em dashes must survive");
        assertFalse(result.contains("\u00c3\u0082"), "must not double-encode non-ASCII");
        assertFalse(result.contains("ÃÂÃÂ"), "garbling signature must not appear");
    }

    @Test
    void garblingSignatureIsDetectable() {
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
        String html = "<p>normal content</p>";
        String result = prettify(html);
        assertNotNull(result, "prettify must always return a non-null string");
        assertTrue(result.contains("normal content"), "content must survive");
    }
}
