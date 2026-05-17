package io.sparge.server;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.vladsch.flexmark.html2md.converter.FlexmarkHtmlConverter;
import com.vladsch.flexmark.util.data.MutableDataSet;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Comment;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.nodes.Node;
import org.jsoup.nodes.TextNode;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * HTML-to-Markdown converter — native Java port of scripts/convert_post.py.
 *
 * Pipeline: jsoup DOM cleanup → code block extraction → flexmark HTML→MD
 * → code block restoration → MD cleanup → YAML front matter.
 */
public final class ConvertPost {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    static final String[] JUNK_SELECTORS = {
        ".entry-header", "header", ".entry-meta",
        ".author-box", ".author-description", ".author-info",
        ".addtoany_share_save_container", ".addtoany_share_save",
        ".sharedaddy", "#comments", ".comments-area",
        ".jp-relatedposts", ".post-navigation",
        ".wpdiscuz-form-container", "script", "style",
        "noscript"  // KIE blog uses <noscript> as empty spacer cells in tables
    };

    private static final Set<String> CHROME_HEADINGS =
        Set.of("author", "related posts", "feedback", "share", "about");

    private static final Pattern[] META_PATTERNS = {
        Pattern.compile("^by\\s", Pattern.CASE_INSENSITIVE),
        Pattern.compile("Post Comment", Pattern.CASE_INSENSITIVE),
        Pattern.compile("View all posts", Pattern.CASE_INSENSITIVE),
        Pattern.compile("mailto:"),
        Pattern.compile("^\\[?\\s*Rules?\\s*\\]?\\s*\\[?\\s*Article", Pattern.CASE_INSENSITIVE),
    };

    private static final Pattern SOCIAL_PLATFORM_RE =
        Pattern.compile("addtoany|linkedin|twitter|facebook|reddit|tumblr",
            Pattern.CASE_INSENSITIVE);
    private static final Pattern SOCIAL_SHARE_URL_RE =
        Pattern.compile("twitter\\.com/intent|facebook\\.com/sharer|linkedin\\.com/share"
            + "|reddit\\.com/submit|plus\\.google\\.com/share|t\\.co/",
            Pattern.CASE_INSENSITIVE);

    private static final Pattern[] JUNK_LINE_PATTERNS = {
        Pattern.compile("^\\[\\]\\(<https?://"),
        Pattern.compile("^\\[\\]\\(<https://www\\.addtoany"),
        Pattern.compile("^\\[Post Comment\\]"),
        Pattern.compile("^## Author\\s*$"),
        Pattern.compile("^\\* !\\[.*?\\]\\(/legacy/assets/images.*?\\)\\s*$"),
        Pattern.compile("^\\[Mark Proctor\\].*?title=\"Mark Proctor\"\\)"),
        Pattern.compile("^\\[ View all posts \\]"),
        Pattern.compile("^\\[ \\]\\(<mailto:"),
    };

    private static final Pattern ENCODED_TAG_RE =
        Pattern.compile("&lt;(?:table|div|p|span|ul|ol|tr|td|th)\\b",
            Pattern.CASE_INSENSITIVE);
    private static final Pattern TRIPLE_NEWLINES = Pattern.compile("\n{3,}");
    private static final Pattern EMPTY_LINK_PREFIX =
        Pattern.compile("\\[\\]\\(<https?://[^)]*\\)");
    private static final Pattern SETEXT_H1 = Pattern.compile("(?m)^(\\S[^\n]*)\n=+$");
    private static final Pattern SETEXT_H2 = Pattern.compile("(?m)^([^-\n][^\n]*)\n-+$");

    static final Set<String> KNOWN_LANGUAGES = Set.of(
        "java", "python", "javascript", "js", "typescript", "ts",
        "xml", "json", "yaml", "yml", "sql", "bash", "sh", "shell",
        "groovy", "kotlin", "scala", "go", "rust", "c", "cpp",
        "html", "css", "properties", "text", "plain", "diff",
        "drools", "drl", "console", "log", "dockerfile"
    );

    private static final FlexmarkHtmlConverter HTML_CONVERTER;
    static {
        MutableDataSet opts = new MutableDataSet()
            .set(FlexmarkHtmlConverter.SETEXT_HEADINGS, false);
        HTML_CONVERTER = FlexmarkHtmlConverter.builder(opts).build();
    }

    private ConvertPost() {}

    public static String convert(Path htmlPath, Path jsonPath) throws Exception {
        Path sidecar = jsonPath != null ? jsonPath
            : htmlPath.resolveSibling(
                htmlPath.getFileName().toString().replaceAll("\\.html$", ".json"));
        JsonNode meta = MAPPER.readTree(sidecar.toFile());

        String htmlContent = Files.readString(htmlPath, StandardCharsets.UTF_8);
        Document doc = Jsoup.parse(htmlContent, htmlPath.toUri().toString());
        Element article = doc.selectFirst("article");
        if (article == null) article = doc.selectFirst("body");
        if (article == null) return null;

        // Phase 1: Remove junk selectors
        for (String sel : JUNK_SELECTORS) article.select(sel).remove();

        // Phase 2: DOM cleanup
        removeComments(article);
        decodeEncodedCodeBlocks(article);
        unwrapPlainBlockquotes(article);
        removeWpDiscuzAddToAny(article);
        removeAuthorChrome(article, meta);
        removeChromeHeadings(article);

        // Unwrap links inside headings — preserves text, removes href
        // (nav links inside headings render as [Section](url) in MD — unwanted)
        for (Element h : article.select("h1, h2, h3, h4, h5, h6")) {
            for (Element a : new ArrayList<>(h.select("a"))) {
                a.unwrap();
            }
        }

        // Remove h3 headings that duplicate the post title (CMS template artifact)
        String titleStart = meta.path("title").asText("").toLowerCase();
        if (titleStart.length() >= 12) {
            String prefix = titleStart.substring(0, Math.min(12, titleStart.length()));
            for (Element h3 : new ArrayList<>(article.select("h3"))) {
                if (h3.text().strip().toLowerCase().startsWith(prefix)) h3.remove();
            }
        }

        // Remove repeated nav links — same href appearing 5+ times is navigation chrome
        // (blog.athico.com archive has nav section repeated 119 times in some posts)
        removeRepeatedNavLinks(article);

        removeMetaElements(article);
        fixImagePaths(article);
        fixLinkPaths(article);
        flattenNestedTables(article);
        removeEmptyTags(article);
        normaliseTableHeaders(article);

        // Phase 3: Extract code blocks → placeholders
        Map<String, String[]> codeBlocks = new LinkedHashMap<>();
        extractCodeBlocks(article, codeBlocks);

        // Phase 4: HTML → Markdown
        String body = HTML_CONVERTER.convert(article.outerHtml()).strip();

        // Phase 5: Restore code blocks
        for (Map.Entry<String, String[]> e : codeBlocks.entrySet()) {
            String lang    = e.getValue()[0];
            String code    = e.getValue()[1];
            int    maxRun  = maxBacktickRun(code);
            int    fenceLen = Math.max(3, maxRun + 1);
            String fence   = "`".repeat(fenceLen);
            body = body.replace(e.getKey(), fence + lang + "\n" + code + "\n" + fence);
        }

        // Phase 6: MD cleanup + front matter
        body = cleanMarkdown(body);
        return buildFrontMatter(meta, htmlPath) + body;
    }

    // ── DOM helpers ───────────────────────────────────────────────────────────

    private static void removeComments(Element root) {
        for (Element el : root.getAllElements()) {
            new ArrayList<>(el.childNodes()).stream()
                .filter(n -> n instanceof Comment)
                .forEach(Node::remove);
        }
    }

    private static void decodeEncodedCodeBlocks(Element article) {
        for (Element pre : new ArrayList<>(article.select("pre"))) {
            Element code = pre.selectFirst("code");
            if (code == null) continue;
            if (ENCODED_TAG_RE.matcher(code.html()).find()) {
                String decoded = org.jsoup.parser.Parser.unescapeEntities(code.text(), true);
                decoded = decoded.replaceAll("<img[^>]*spacer[^>]*/>", "");
                decoded = decoded.replaceAll(
                    "<img[^>]+height=[\"']?[01][\"']?[^>]+alt=[\"']?[\"']?[^>]*/>", "");
                pre.replaceWith(Jsoup.parseBodyFragment(decoded).body());
            }
        }
    }

    private static void unwrapPlainBlockquotes(Element article) {
        for (Element bq : new ArrayList<>(article.select("blockquote"))) {
            String classes = String.join(" ", bq.classNames());
            if (classes.contains("missing-image")) continue;
            if (!bq.classNames().isEmpty()) continue;
            if (bq.selectFirst("cite") != null) continue;
            bq.unwrap();
        }
    }

    private static void removeWpDiscuzAddToAny(Element article) {
        for (Element tag : new ArrayList<>(article.getAllElements())) {
            String cls = String.join(" ", tag.classNames()).toLowerCase();
            if (cls.contains("wpdiscuz") || cls.contains("addtoany")) tag.remove();
        }
    }

    private static void removeAuthorChrome(Element article, JsonNode meta) {
        for (Element a : new ArrayList<>(article.select("a[href]"))) {
            String href = a.attr("href");
            if ((href.contains("search_authors") || href.contains("/author/"))
                    && a.selectFirst("img") != null) a.remove();
        }
        String authorName = meta.path("author").asText("").trim().toLowerCase();
        if (!authorName.isEmpty()) {
            for (Element img : new ArrayList<>(article.select("img"))) {
                if (img.attr("alt").trim().toLowerCase().equals(authorName)) img.remove();
            }
        }
    }

    private static void removeRepeatedNavLinks(Element article) {
        // Count how many times each href appears
        Map<String, Long> hrefCounts = article.select("a[href]").stream()
            .collect(Collectors.groupingBy(
                a -> a.attr("href"), Collectors.counting()));
        // Remove any <a> whose href appears 5+ times (nav template chrome)
        for (Map.Entry<String, Long> entry : hrefCounts.entrySet()) {
            if (entry.getValue() >= 5) {
                for (Element a : new ArrayList<>(article.select("a[href=\"" + entry.getKey() + "\"]"))) {
                    a.unwrap(); // keep text content, strip the link
                }
            }
        }
    }

    private static void removeChromeHeadings(Element article) {
        for (Element h : new ArrayList<>(article.select("h2, h3"))) {
            if (CHROME_HEADINGS.contains(h.text().trim().toLowerCase())) {
                for (Element sib : new ArrayList<>(h.nextElementSiblings())) sib.remove();
                h.remove();
                break;
            }
        }
    }

    private static void removeMetaElements(Element article) {
        for (Element tag : new ArrayList<>(article.select("p, div, span"))) {
            String text    = tag.text().strip();
            String hrefs   = tag.select("a[href]").stream()
                .map(a -> a.attr("href")).collect(Collectors.joining(" "));
            String combined = text + " " + hrefs;
            if (tag.tagName().equals("div") && text.length() > 120) {
                if (text.length() < 300 && META_PATTERNS[0].matcher(text).find()) tag.remove();
                continue;
            }
            if (text.length() < 500 && matchesAnyMeta(combined)) { tag.remove(); continue; }
            if (SOCIAL_PLATFORM_RE.matcher(combined).find()) {
                boolean isShareUrl  = SOCIAL_SHARE_URL_RE.matcher(hrefs).find();
                boolean isBareLabel = text.length() < 50 && hrefs.isEmpty();
                if (isShareUrl || isBareLabel) { tag.remove(); continue; }
            }
            if (META_PATTERNS[0].matcher(text).find() && text.length() < 300) tag.remove();
        }
    }

    private static boolean matchesAnyMeta(String s) {
        for (Pattern p : META_PATTERNS) if (p.matcher(s).find()) return true;
        return false;
    }

    private static void fixImagePaths(Element article) {
        for (Element img : new ArrayList<>(article.select("img"))) {
            String src = img.attr("src");
            if (src.startsWith("data:")) { img.remove(); continue; }
            if (src.startsWith("../../assets/"))
                img.attr("src", "/legacy/" + src.replace("../../", ""));
        }
    }

    private static void fixLinkPaths(Element article) {
        for (Element a : article.select("a[href]")) {
            String href = a.attr("href");
            if (href.startsWith("../../assets/"))
                a.attr("href", "/legacy/" + href.replace("../../", ""));
        }
    }

    // Tables with no <thead> produce malformed GFM — flexmark emits separator
    // rows without a header. Promote the first <tr> to a <thead> so the table
    // renders correctly. Only applies to tables with 2+ rows.
    private static void normaliseTableHeaders(Element article) {
        for (Element table : article.select("table")) {
            if (table.selectFirst("thead") != null) continue;
            Element tbody = table.selectFirst("tbody");
            if (tbody == null) continue;
            List<Element> rows = new ArrayList<>(tbody.select("> tr"));
            if (rows.size() < 2) continue;
            // Move first row into a new <thead>
            Element firstRow = rows.get(0);
            // Convert its <td> cells to <th>
            for (Element td : firstRow.select("td")) td.tagName("th");
            Element thead = table.ownerDocument().createElement("thead");
            thead.appendChild(firstRow);
            table.prependChild(thead);
        }
    }

    // If a table is nested inside a td and the outer table carries no other
    // meaningful content, promote the inner table to replace the outer one.
    // KIE blog uses this pattern for agenda/schedule tables.
    private static void flattenNestedTables(Element article) {
        boolean changed = true;
        while (changed) {
            changed = false;
            for (Element inner : new ArrayList<>(article.select("td > table"))) {
                Element outerTable = inner.parents().select("table").first();
                if (outerTable == null) continue;
                // Only promote when outer table carries no additional text
                String outerText = outerTable.text().strip();
                String innerText = inner.text().strip();
                if (!outerText.equals(innerText)) continue;
                outerTable.replaceWith(inner);
                changed = true;
                break;
            }
        }
    }

    private static void removeEmptyTags(Element article) {
        boolean changed = true;
        while (changed) {
            changed = false;
            // p/div/span/li: remove if no text and no image
            for (Element tag : new ArrayList<>(article.select("p, div, span, li"))) {
                if (tag.text().isBlank() && tag.selectFirst("img") == null) {
                    tag.remove(); changed = true;
                }
            }
            // td/th: remove if completely empty (no text, no img, no nested table)
            for (Element tag : new ArrayList<>(article.select("td, th"))) {
                if (tag.text().isBlank()
                        && tag.selectFirst("img, table") == null) {
                    tag.remove(); changed = true;
                }
            }
            // tr: remove if it has no remaining cells
            for (Element tag : new ArrayList<>(article.select("tr"))) {
                if (tag.select("td, th").isEmpty()) {
                    tag.remove(); changed = true;
                }
            }
        }
    }

    // ── Code block extraction ─────────────────────────────────────────────────

    private static void extractCodeBlocks(Element article, Map<String, String[]> blocks) {
        int idx = 0;
        for (Element pre : new ArrayList<>(article.select("pre"))) {
            Element code = pre.selectFirst("code");
            if (code == null) continue;
            String lang = extractLang(code);
            String text = code.wholeText().replace('\u00a0', ' ');
            String key  = String.format("@@CODEBLOCK_%03d@@", idx++);
            blocks.put(key, new String[]{lang, text});
            Element placeholder = Jsoup.parseBodyFragment("<p>" + key + "</p>").selectFirst("p");
            pre.replaceWith(placeholder);
        }
    }

    private static String extractLang(Element code) {
        String lang = "";
        for (String cls : code.classNames()) {
            if (cls.startsWith("language-")) { lang = cls.substring("language-".length()); break; }
            if (KNOWN_LANGUAGES.contains(cls.toLowerCase())) { lang = cls.toLowerCase(); break; }
        }
        // Remap sql→java when content looks like Java (mirrors Python's heuristic)
        if ("sql".equals(lang)) {
            String text = code.wholeText().toLowerCase();
            if (text.contains("public ") || text.contains("class ")
                    || text.contains("void ") || text.contains("import ")) {
                lang = "java";
            }
        }
        return lang;
    }

    private static int maxBacktickRun(String text) {
        int max = 0, cur = 0;
        for (char c : text.toCharArray()) {
            if (c == '`') { cur++; max = Math.max(max, cur); } else cur = 0;
        }
        return max;
    }

    // ── Markdown cleanup ──────────────────────────────────────────────────────

    private static String cleanMarkdown(String body) {
        String[] lines = body.split("\n", -1);
        List<String> cleaned = new ArrayList<>();
        for (String line : lines) {
            boolean junk = false;
            for (Pattern p : JUNK_LINE_PATTERNS) {
                if (p.matcher(line).find()) { junk = true; break; }
            }
            if (!junk) cleaned.add(line);
        }
        body = String.join("\n", cleaned);
        body = EMPTY_LINK_PREFIX.matcher(body).replaceAll("");
        body = SETEXT_H1.matcher(body).replaceAll("# $1");
        body = SETEXT_H2.matcher(body).replaceAll("## $1");
        // Convert === visual separators to blank + --- HR
        // (Blogger posts use ===... lines as visual section dividers)
        body = body.replaceAll("(?m)^={4,}\\s*$", "\n---");
        body = TRIPLE_NEWLINES.matcher(body).replaceAll("\n\n");
        return body.strip();
    }

    // ── Front matter ──────────────────────────────────────────────────────────

    static String buildFrontMatter(JsonNode meta, Path htmlPath) {
        String title = meta.path("title").asText(
            htmlPath != null ? htmlPath.getFileName().toString().replace(".html", "") : "");
        title = title.replaceAll("\\s*[-–]\\s*KIE Community\\s*$", "").strip();
        title = title.replace("\"", "\\\"");
        String date = meta.path("date").asText("");
        if (date.length() >= 10) date = date.substring(0, 10);
        List<String> cats = new ArrayList<>();
        for (JsonNode c : meta.path("categories")) {
            String s = c.asText("").strip(); if (!s.isEmpty()) cats.add(s);
        }
        List<String> tags = new ArrayList<>();
        for (JsonNode t : meta.path("tags")) {
            String s = t.asText("").strip(); if (!s.isEmpty()) tags.add(s);
        }
        return "---\n"
            + "layout: post\n"
            + "title: \"" + title + "\"\n"
            + "date: " + date + "\n"
            + "author: Mark Proctor\n"
            + "categories: " + yamlList(cats) + "\n"
            + "tags: " + yamlList(tags) + "\n"
            + "original_url: " + meta.path("original_url").asText("") + "\n"
            + "---\n\n";
    }

    private static String yamlList(List<String> items) {
        if (items.isEmpty()) return "[]";
        return "\n" + items.stream().map(i -> "  - " + i).collect(Collectors.joining("\n"));
    }
}
