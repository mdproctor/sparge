package io.sparge.server;

import org.jsoup.Jsoup;
import org.jsoup.nodes.Element;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * Markdown validation suite — port of scripts/md_validator.py.
 *
 * Runs 14 MD-only checks (pure string/regex) plus 5 cross-checks comparing
 * MD against the original HTML. Both use the same jsoup selectors as ConvertPost
 * for HTML preprocessing (coherence requirement from md_validator.py line 53-56).
 */
public final class MdValidator {

    private static final Set<String> KNOWN_LANGUAGES = Set.copyOf(ConvertPost.KNOWN_LANGUAGES);

    private static final Set<String> CHROME_HEADINGS =
        Set.of("author", "related posts", "feedback", "share", "about");

    private static final List<String> KIE_TERMS =
        List.of("drools", "jbpm", "kie", "optaplanner", "kogito", "guvnor", "rete");

    private MdValidator() {}

    // ── Public API ────────────────────────────────────────────────────────────

    public static List<MdIssue> validate(String md, String slug, Path htmlPath) {
        List<MdIssue> issues = new ArrayList<>();

        // MD-only checks
        issues.addAll(chkOrphanedPlaceholders(md));
        issues.addAll(chkStrayDigitAfterFence(md));
        issues.addAll(chkBalancedFences(md));
        issues.addAll(chkEmptyCodeBlocks(md));
        issues.addAll(chkFrontMatterValid(md));
        issues.addAll(chkEmptyBody(md));
        issues.addAll(chkWordPressJunk(md));
        issues.addAll(chkHtmlEntitiesInBody(md));
        issues.addAll(chkLocalImagePaths(md));
        issues.addAll(chkBrokenMdLinks(md));
        issues.addAll(chkNoTripleBlanks(md));
        issues.addAll(chkExcessiveLineLength(md));
        issues.addAll(chkManyMissingImages(md));
        issues.addAll(chkCodeFenceLanguage(md));

        // Cross-checks (need HTML)
        if (htmlPath != null && Files.exists(htmlPath)) {
            try {
                String html = Files.readString(htmlPath, StandardCharsets.UTF_8);
                Element article = loadArticle(html);
                if (article != null) {
                    issues.addAll(crossWordCount(md, slug, article));
                    issues.addAll(crossCodeBlockCount(md, slug, article));
                    issues.addAll(crossHeadingMatch(md, slug, article));
                    issues.addAll(crossLastSectionPresent(md, slug, article));
                    issues.addAll(crossTechnicalTerms(md, slug, article));
                }
            } catch (Exception e) {
                issues.add(new MdIssue("cross_check_error", "WARN",
                        "Could not load HTML: " + e.getMessage()));
            }
        }

        return issues;
    }

    // ── HTML preprocessing — must mirror ConvertPost.java exactly ─────────────

    static Element loadArticle(String html) {
        org.jsoup.nodes.Document doc = Jsoup.parse(html);
        Element article = doc.selectFirst("article");
        if (article == null) article = doc.selectFirst("body");
        if (article == null) return null;

        // Strip script/style/noscript
        article.select("script, style, noscript").remove();

        // Strip same junk selectors as ConvertPost (coherence requirement)
        for (String sel : ConvertPost.JUNK_SELECTORS) article.select(sel).remove();

        // Strip chrome headings
        for (Element h : new ArrayList<>(article.select("h2, h3"))) {
            if (CHROME_HEADINGS.contains(h.text().trim().toLowerCase())) {
                for (Element sib : new ArrayList<>(h.nextElementSiblings())) sib.remove();
                h.remove();
                break;
            }
        }

        // Strip bylines
        for (Element tag : new ArrayList<>(article.select("p, div, span"))) {
            String text = tag.text().strip();
            if (text.length() < 200 && text.matches("(?i)^by\\s+[A-Z].*")) tag.remove();
        }

        // Strip send_to_friend links
        for (Element a : new ArrayList<>(article.select("a[href]"))) {
            String href = a.attr("href");
            if (href.contains("send_to_friend") || href.toLowerCase().contains("sendtofriend")) {
                Element parent = a.parent();
                a.remove();
                if (parent != null && parent.text().isBlank()) parent.remove();
            }
        }

        return article;
    }

    // ── Body extraction ───────────────────────────────────────────────────────

    private static String body(String md) {
        int end = md.indexOf("\n---\n");
        return end >= 0 ? md.substring(end + 5) : md;
    }

    // ══════════════════════════════════════════════════════════════════════════
    // MD-ONLY CHECKS
    // ══════════════════════════════════════════════════════════════════════════

    static List<MdIssue> chkOrphanedPlaceholders(String md) {
        List<String> found = new ArrayList<>();
        var m = Pattern.compile("@@CODEBLOCK_\\d+@@|CODEBLOCK_FENCE_\\d+").matcher(md);
        while (m.find()) found.add(m.group());
        if (!found.isEmpty())
            return List.of(new MdIssue("orphaned_placeholder", "ERROR",
                    "Unreplaced placeholders: " + found.subList(0, Math.min(3, found.size()))));
        return List.of();
    }

    static List<MdIssue> chkStrayDigitAfterFence(String md) {
        if (Pattern.compile("(?m)^`{3,}\\d").matcher(md).find())
            return List.of(new MdIssue("stray_digit_after_fence", "ERROR",
                    "Fence followed by digit — partial placeholder replacement"));
        return List.of();
    }

    static List<MdIssue> chkBalancedFences(String md) {
        boolean inFence = false;
        int openLen = 0;
        for (String line : md.split("\n", -1)) {
            String t = line.strip();
            if (t.startsWith("`")) {
                int len = 0;
                while (len < t.length() && t.charAt(len) == '`') len++;
                if (len >= 3) {
                    if (!inFence) { inFence = true; openLen = len; }
                    else if (len >= openLen && t.matches("`+\\s*")) {
                        inFence = false; openLen = 0;
                    }
                }
            }
        }
        if (inFence)
            return List.of(new MdIssue("unbalanced_fences", "ERROR", "Unclosed code fence"));
        return List.of();
    }

    static List<MdIssue> chkEmptyCodeBlocks(String md) {
        if (Pattern.compile("(?m)^`{3,}[^\n]*\n`{3,}").matcher(md).find())
            return List.of(new MdIssue("empty_code_block", "WARN", "Empty fenced code block"));
        return List.of();
    }

    static List<MdIssue> chkFrontMatterValid(String md) {
        if (!md.startsWith("---\n"))
            return List.of(new MdIssue("front_matter_invalid", "ERROR", "No front matter"));
        int end = md.indexOf("\n---\n", 4);
        if (end < 0)
            return List.of(new MdIssue("front_matter_invalid", "ERROR", "Front matter not closed"));
        String fm = md.substring(4, end);
        List<String> missing = new ArrayList<>();
        if (!fm.contains("title:"))  missing.add("title");
        if (!fm.contains("date:"))   missing.add("date");
        if (!fm.contains("author:")) missing.add("author");
        if (!missing.isEmpty())
            return List.of(new MdIssue("front_matter_invalid", "ERROR",
                    "Missing fields: " + missing));
        if (!Pattern.compile("(?m)^date:\\s*\\d{4}-\\d{2}-\\d{2}").matcher(fm).find())
            return List.of(new MdIssue("front_matter_invalid", "WARN",
                    "date not in YYYY-MM-DD format"));
        return List.of();
    }

    static List<MdIssue> chkEmptyBody(String md) {
        if (body(md).strip().length() < 20)
            return List.of(new MdIssue("empty_body", "ERROR",
                    "Body < 20 chars (" + body(md).strip().length() + ")"));
        return List.of();
    }

    static List<MdIssue> chkWordPressJunk(String md) {
        String b = body(md);
        for (Pattern p : List.of(
            Pattern.compile("View all posts", Pattern.CASE_INSENSITIVE),
            Pattern.compile("Post Comment", Pattern.CASE_INSENSITIVE),
            Pattern.compile("addtoany", Pattern.CASE_INSENSITIVE),
            Pattern.compile("wpDiscuz", Pattern.CASE_INSENSITIVE))) {
            if (p.matcher(b).find())
                return List.of(new MdIssue("wordpress_junk", "WARN",
                        "WordPress junk detected: " + p.pattern()));
        }
        return List.of();
    }

    static List<MdIssue> chkHtmlEntitiesInBody(String md) {
        long count = Pattern.compile("&amp;|&lt;|&gt;|&quot;|&nbsp;").matcher(body(md))
            .results().count();
        if (count >= 5)
            return List.of(new MdIssue("html_entities_in_body", "WARN",
                    count + " HTML entities in body"));
        return List.of();
    }

    static List<MdIssue> chkLocalImagePaths(String md) {
        if (Pattern.compile("\\.\\./\\.\\./assets/").matcher(md).find())
            return List.of(new MdIssue("local_image_paths", "ERROR",
                    "Relative ../../assets/ path — must be /legacy/assets/"));
        return List.of();
    }

    static List<MdIssue> chkBrokenMdLinks(String md) {
        if (Pattern.compile("\\[[^\\]]+\\]\\(\\)").matcher(md).find())
            return List.of(new MdIssue("broken_md_links", "WARN", "Empty href [text]()"));
        return List.of();
    }

    static List<MdIssue> chkNoTripleBlanks(String md) {
        if (Pattern.compile("\n{4,}").matcher(md).find())
            return List.of(new MdIssue("no_triple_blanks", "WARN",
                    "3+ consecutive blank lines"));
        return List.of();
    }

    static List<MdIssue> chkExcessiveLineLength(String md) {
        for (String line : md.split("\n")) {
            if (line.length() > 8000)
                return List.of(new MdIssue("excessive_line_length", "WARN",
                        "Line > 8000 chars (" + line.length() + ")"));
        }
        return List.of();
    }

    static List<MdIssue> chkManyMissingImages(String md) {
        long count = Pattern.compile("MISSING_IMAGE|missing-image-placeholder")
            .matcher(md).results().count();
        if (count > 10)
            return List.of(new MdIssue("many_missing_images", "WARN",
                    count + " missing image placeholders"));
        return List.of();
    }

    static List<MdIssue> chkCodeFenceLanguage(String md) {
        var m = Pattern.compile("(?m)^`{3,}(\\w+)").matcher(md);
        List<String> unknown = new ArrayList<>();
        while (m.find()) {
            String lang = m.group(1).toLowerCase();
            if (!KNOWN_LANGUAGES.contains(lang)) unknown.add(lang);
        }
        if (!unknown.isEmpty())
            return List.of(new MdIssue("code_fence_language", "WARN",
                    "Unknown languages: " + unknown.subList(0, Math.min(3, unknown.size()))));
        return List.of();
    }

    // ══════════════════════════════════════════════════════════════════════════
    // CROSS-CHECKS
    // ══════════════════════════════════════════════════════════════════════════

    static List<MdIssue> crossWordCount(String md, String slug, Element article) {
        String bodyMd = removeFences(body(md));
        int mdWords  = bodyMd.trim().isEmpty() ? 0 : bodyMd.trim().split("\\s+").length;
        Element copy = article.clone();
        copy.select("pre, code").remove();
        String htmlText = copy.text().trim();
        int htmlWords   = htmlText.isEmpty() ? 0 : htmlText.split("\\s+").length;
        if (htmlWords > 150 && mdWords < htmlWords * 0.35)
            return List.of(new MdIssue("word_count", "WARN",
                    "MD " + mdWords + " words vs HTML " + htmlWords + " (< 35%)"));
        return List.of();
    }

    static List<MdIssue> crossCodeBlockCount(String md, String slug, Element article) {
        long htmlPres = article.select("pre").size();
        long mdFences = Pattern.compile("(?m)^`{3,}").matcher(md).results().count() / 2;
        if (htmlPres > 0 && mdFences < htmlPres * 0.5)
            return List.of(new MdIssue("code_block_count", "WARN",
                    "HTML " + htmlPres + " <pre> vs MD " + mdFences + " fences"));
        return List.of();
    }

    static List<MdIssue> crossHeadingMatch(String md, String slug, Element article) {
        String bodyLower = body(md).toLowerCase();
        List<String> missing = new ArrayList<>();
        for (Element h : article.select("h2, h3")) {
            String text = h.text().strip().toLowerCase();
            if (text.length() < 3) continue;
            if (!bodyLower.contains(text)) missing.add(h.text());
        }
        if (!missing.isEmpty())
            return List.of(new MdIssue("heading_match", "WARN",
                    "HTML headings not in MD: " + missing.subList(0, Math.min(3, missing.size()))));
        return List.of();
    }

    static List<MdIssue> crossLastSectionPresent(String md, String slug, Element article) {
        var paras = article.select("p");
        for (int i = paras.size() - 1; i >= 0; i--) {
            String text = paras.get(i).text().strip();
            if (text.length() > 30) {
                String snippet = text.substring(0, Math.min(40, text.length())).toLowerCase();
                if (!body(md).toLowerCase().contains(snippet))
                    return List.of(new MdIssue("last_section_present", "WARN",
                            "Last HTML paragraph missing from MD: '"
                            + text.substring(0, Math.min(60, text.length())) + "'"));
                break;
            }
        }
        return List.of();
    }

    static List<MdIssue> crossTechnicalTerms(String md, String slug, Element article) {
        String htmlLower = article.text().toLowerCase();
        String mdLower   = md.toLowerCase();
        List<String> lost = KIE_TERMS.stream()
            .filter(t -> htmlLower.contains(t) && !mdLower.contains(t))
            .collect(Collectors.toList());
        if (!lost.isEmpty())
            return List.of(new MdIssue("technical_terms", "WARN",
                    "KIE terms lost: " + lost));
        return List.of();
    }

    private static String removeFences(String md) {
        return Pattern.compile("(?s)```[^\n]*\n.*?```").matcher(md).replaceAll("");
    }
}
