package io.sparge.server;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

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
        assertEquals(formatted, result, "Already-formatted XML must not be altered");
    }

    @Test
    void emptyStringUnchangedForXml() {
        assertEquals("", DrlReformatter.reformatXml(""));
    }
}
