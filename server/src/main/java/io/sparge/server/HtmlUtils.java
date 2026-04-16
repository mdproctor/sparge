package io.sparge.server;

import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.nodes.Node;
import org.jsoup.nodes.TextNode;

import java.nio.charset.StandardCharsets;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * HTML prettification utilities for the Sparge editor view.
 * Mirrors scripts/html_utils.py: prettify_html().
 *
 * Uses the same MARKER trick as Python: U+2060 WORD JOINER is prepended to
 * sibling text immediately adjacent to inline closing tags, then Jsoup
 * pretty-prints (with UTF-8 charset so U+2060 passes through unescaped),
 * then regex rejoins the marked adjacencies.
 */
public final class HtmlUtils {

    /** U+2060 WORD JOINER — invisible, not HTML-special, survives Jsoup UTF-8 output. */
    private static final String MARKER = "\u2060";

    private static final Set<String> INLINE_TAGS = Set.of(
            "b", "strong", "em", "i", "code", "a", "abbr",
            "cite", "q", "s", "u", "del", "ins", "mark", "small", "sub", "sup"
    );

    private static final String INLINE_RE =
            "(?:b|strong|em|i|code|a|abbr|cite|q|s|u|del|ins|mark|small|sub|sup)";

    // Step 1: collapse <b>\n  TEXT\n </b> to <b>TEXT</b>
    private static final Pattern COLLAPSE = Pattern.compile(
            "(?i)(<(?:" + INLINE_RE + ")(?:\\s[^>]*)?>)\\n[ \\t]*([^\\n]*)\\n[ \\t]*(</(?:" + INLINE_RE + ")>)"
    );

    // Step 2: join </b>\n  ⁠text → </b>text (MARKER at start of following line)
    private static final Pattern JOIN_ADJACENT = Pattern.compile(
            "(?i)(</(?:" + INLINE_RE + ")>)\\n[ \\t]*" + Pattern.quote(MARKER)
    );

    private HtmlUtils() {}

    /**
     * Prettify HTML for the editor while preserving inline element adjacency.
     * Mirrors scripts/html_utils.py: prettify_html().
     */
    public static String prettifyHtml(String raw) {
        if (raw == null || raw.isEmpty()) return raw;

        Document doc = Jsoup.parse(raw);
        // UTF-8 output: non-ASCII chars (including U+2060) pass through unescaped
        doc.outputSettings()
                .charset(StandardCharsets.UTF_8)
                .prettyPrint(true)
                .indentAmount(1);

        // Mark inline elements whose closing tag is immediately adjacent to non-whitespace
        for (String tagName : INLINE_TAGS) {
            for (Element el : doc.select(tagName)) {
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

        // Garbling detection
        if (content.contains("ÃÂÃÂ") || content.contains("\u00c3\u0082")) {
            return raw;
        }

        // Step 1: collapse inline element text to single line
        content = COLLAPSE.matcher(content).replaceAll("$1$2$3");

        // Step 2: rejoin adjacent closing tags with MARKER-prefixed content
        content = JOIN_ADJACENT.matcher(content).replaceAll("$1");

        // Clean up remaining MARKER characters
        content = content.replace(MARKER, "");

        return content;
    }
}
