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

    private static final List<String> DRL_KEYWORDS = List.of(
            "agenda-group", "lock-on-active", "no-loop", "auto-focus",
            "activation-group", "date-effective", "date-expires", "ruleflow-group",
            "salience", "dialect", "duration", "enabled", "timer",
            "declare", "function", "package", "import", "global", "query",
            "rule", "when", "then", "end"
    );

    private static final Set<String> DRL_LINE_ALONE = Set.of("when", "then", "end");

    private static final Pattern DRL_KW_RE = Pattern.compile(
            "\\b(" + String.join("|", DRL_KEYWORDS.stream()
                    .map(Pattern::quote).toList()) + ")\\b"
    );

    private static final List<Pattern> DRL_SIGNALS = List.of(
            Pattern.compile("\\brule\\s*[\"|\u00a0]", Pattern.CASE_INSENSITIVE),
            Pattern.compile("\\bquery\\s+[\\w\"]",    Pattern.CASE_INSENSITIVE),
            Pattern.compile("\\bwhen\\b.*\\bthen\\b", Pattern.CASE_INSENSITIVE | Pattern.DOTALL),
            Pattern.compile("^\\s*end\\s*$",          Pattern.MULTILINE),
            Pattern.compile("\\bdrools\\b",           Pattern.CASE_INSENSITIVE),
            Pattern.compile("\\binsert\\b|\\bretract\\b|\\bmodify\\b|\\bupdate\\b",
                    Pattern.CASE_INSENSITIVE)
    );

    private static boolean isDrl(String text) {
        return DRL_SIGNALS.stream().anyMatch(p -> p.matcher(text).find());
    }

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

    public static String reformatXml(String text) {
        if (text == null || text.isEmpty()) return text;
        if (text.contains("\n")) return text;
        try {
            DocumentBuilderFactory dbf = DocumentBuilderFactory.newInstance();
            dbf.setFeature("http://apache.org/xml/features/disallow-doctype-decl", false);
            DocumentBuilder db = dbf.newDocumentBuilder();
            // Suppress error output for malformed XML
            db.setErrorHandler(null);
            Document doc = db.parse(
                    new ByteArrayInputStream(text.getBytes(StandardCharsets.UTF_8)));
            doc.normalize();

            boolean hasDecl = text.startsWith("<?xml");
            Transformer transformer = TransformerFactory.newInstance().newTransformer();
            transformer.setOutputProperty(OutputKeys.INDENT, "yes");
            transformer.setOutputProperty("{http://xml.apache.org/xslt}indent-amount", "2");
            transformer.setOutputProperty(OutputKeys.OMIT_XML_DECLARATION, hasDecl ? "no" : "yes");

            StringWriter sw = new StringWriter();
            transformer.transform(new DOMSource(doc), new StreamResult(sw));
            return sw.toString().strip();
        } catch (Exception e) {
            return text;
        }
    }
}
