package io.sparge.server;

import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class CodeBlockFixerTest {

    private static Document article(String html) {
        return Jsoup.parse("<article>" + html + "</article>");
    }

    // ── apply() for pre/code blocks ───────────────────────────────────────────

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

    // ── DRL quote safety ──────────────────────────────────────────────────────

    @Test
    void ruleInRuleNameNotBroken() {
        Document doc = article(
            "<pre><code class=\"language-drl\">rule \"My rule name\" when Foo() then end</code></pre>"
        );
        CodeBlockFixer.apply(doc);
        String result = doc.select("pre code").first().wholeOwnText();
        assertTrue(result.contains("\"My rule name\""), "rule name must be preserved intact");
        assertFalse(result.contains("\"\nMy"), "rule inside quoted name must not break the name");
    }

    // ── Span-based DRL detection ──────────────────────────────────────────────

    @Test
    void spanDrlBlockConvertedToPreCode() {
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
        Document doc = article(
                "<div><span>The</span> <span>quick</span> <span>brown</span> fox</div>"
        );
        boolean changed = CodeBlockFixer.apply(doc);
        assertFalse(changed, "Prose div with spans must not be converted to code block");
    }

    @Test
    void applyIncludesSpanDrl() {
        Document doc = article(
                "<div><span>rule</span><span>\"IsChild\"</span><br/>" +
                "<span>when</span><br/><span>Child()</span><br/>" +
                "<span>then</span><br/><span>insert(new Result());</span><br/>" +
                "<span>end</span></div>"
        );
        assertTrue(CodeBlockFixer.apply(doc), "apply() must include span DRL fix");
    }

    // ── Plain p/br DRL fix ────────────────────────────────────────────────────

    @Test
    void pureDrlPBrConverted() {
        Document doc = article(
                "<p>rule \"Test\"<br/>when<br/>Foo()<br/>then<br/>doIt();<br/>end</p>"
        );
        boolean changed = CodeBlockFixer.apply(doc);
        assertTrue(changed, "Plain <p><br/> DRL must be converted");
        assertNotNull(doc.select("pre code").first(), "result must be <pre><code>");
    }

    @Test
    void needsAtLeast3BrTags() {
        // Only 2 <br/> — below the threshold — should not throw
        Document doc = article("<p>rule \"R\"<br/>when<br/>end</p>");
        assertDoesNotThrow(() -> CodeBlockFixer.apply(doc));
    }

    @Test
    void nonDrlContentNotConverted() {
        Document doc = article(
                "<p>This is prose.<br/>It has multiple<br/>lines of text.<br/>Not code.</p>"
        );
        boolean changed = CodeBlockFixer.apply(doc);
        assertFalse(changed, "Non-DRL prose must not be converted to code block");
    }

    @Test
    void linenumberTableConvertedToPreCode() {
        // Two-column table: left = line numbers, right = code
        Document doc = article(
                "<table><tr>" +
                "<td><pre>1\n2\n3\n</pre></td>" +
                "<td><pre>rule \"R\"\nwhen\n  Foo()\nthen\n  bar();\nend</pre></td>" +
                "</tr></table>"
        );
        boolean changed = CodeBlockFixer.apply(doc);
        assertTrue(changed, "Line-number table must be converted to <pre><code>");
        assertNull(doc.selectFirst("table"), "table must be replaced");
        assertNotNull(doc.selectFirst("pre"), "result must have <pre>");
    }
}
