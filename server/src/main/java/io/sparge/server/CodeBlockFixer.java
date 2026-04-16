package io.sparge.server;

import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
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
     * Apply all code block fixes to the document in-place.
     * Returns true if any change was made.
     */
    public static boolean apply(Document doc) {
        boolean changed = false;

        // 1. Fix <pre><code> blocks with no newlines (DRL and XML)
        for (Element pre : doc.select("pre")) {
            Element code = pre.selectFirst("code");
            if (code == null) continue;

            Set<String> classes = code.classNames();

            if (classes.stream().anyMatch(DRL_CLASSES::contains)) {
                String text = code.wholeOwnText();
                if (text.isEmpty() || text.contains("\n")) continue;
                String fixed = DrlReformatter.reformatDrl(text);
                if (!fixed.equals(text)) {
                    code.text(fixed);
                    changed = true;
                }
            } else if (classes.stream().anyMatch(XML_CLASSES::contains)) {
                // XML tags inside <code> are parsed as DOM elements by Jsoup;
                // use html() to recover the markup, falling back to wholeOwnText().
                String text = code.childNodeSize() > 0 && !code.children().isEmpty()
                        ? code.html()
                        : code.wholeOwnText();
                if (text.isEmpty() || text.contains("\n")) continue;
                String fixed = DrlReformatter.reformatXml(text);
                if (!fixed.equals(text)) {
                    // Replace inner content with formatted plain text
                    code.empty();
                    code.appendChild(new TextNode(fixed));
                    changed = true;
                }
            }
        }

        // 2. Fix span-based DRL blocks
        changed |= fixSpanDrlBlocks(doc);

        // 3. Fix plain <p>/<div> with <br/> containing DRL
        changed |= fixBrDrlBlocks(doc);

        // 4. Fix linenumber tables
        changed |= fixLinenumberTables(doc);

        return changed;
    }

    private static boolean fixSpanDrlBlocks(Document doc) {
        boolean changed = false;
        List<Element> candidates = new ArrayList<>(doc.select("div, p"));

        for (Element el : candidates) {
            if (el.parent() == null) continue;  // already replaced/detached
            if (el.parents().stream().anyMatch(p ->
                    p.tagName().equals("pre") || p.tagName().equals("code"))) continue;
            if (el.selectFirst("br") == null) continue;
            if (el.selectFirst("pre, code") != null) continue;

            // Must have a leaf <span> whose stripped text is exactly "rule"
            boolean hasRuleSpan = el.select("span").stream()
                    .anyMatch(s -> s.ownText().strip().equalsIgnoreCase("rule")
                            && s.children().isEmpty());
            if (!hasRuleSpan) continue;

            Element copy = el.clone();
            copy.select("br").forEach(br -> br.replaceWith(new TextNode("\n")));
            String text = copy.wholeText().replace("\u00a0", " ").strip();

            if (!isDrl(text)) continue;

            String formatted = DrlReformatter.reformatDrl(text);
            Element newBlock = new Element("pre");
            newBlock.appendChild(new Element("code").addClass("language-drl").text(formatted));
            el.replaceWith(newBlock);
            changed = true;
        }
        return changed;
    }

    private static boolean fixBrDrlBlocks(Document doc) {
        boolean changed = false;
        List<Element> candidates = new ArrayList<>(doc.select("p, div"));

        for (Element el : candidates) {
            if (el.parent() == null) continue;  // already replaced/detached
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
            double avgLen = java.util.Arrays.stream(lines)
                    .mapToInt(l -> l.strip().length()).average().orElse(0);
            if (avgLen > 80) continue;

            String formatted = DrlReformatter.reformatDrl(text);
            Element newBlock = new Element("pre");
            newBlock.appendChild(new Element("code").addClass("language-drl").text(formatted));
            el.replaceWith(newBlock);
            changed = true;
        }
        return changed;
    }

    private static boolean fixLinenumberTables(Document doc) {
        boolean changed = false;
        List<Element> tables = new ArrayList<>(doc.select("table"));

        for (Element table : tables) {
            if (table.parent() == null) continue;  // already replaced/detached
            Elements tds = table.select("td");
            if (tds.size() < 2) continue;

            Element leftTd  = tds.get(0);
            Element rightTd = tds.get(1);

            Element leftPre = leftTd.selectFirst("pre");
            boolean isA = leftPre != null && isLinenumberPre(leftPre);
            boolean isB = !isA && isLinenumberDivs(leftTd)
                    && rightTd.selectFirst("code, pre") != null;

            if (!isA && !isB) continue;

            String codeText = extractCode(rightTd).strip();
            if (codeText.isEmpty()) continue;

            Element rightCode = rightTd.selectFirst("pre, code");
            String langClass  = rightCode != null
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
        return !text.isEmpty() && text.chars()
                .allMatch(c -> Character.isDigit(c) || c == '\n' || c == ' ');
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
