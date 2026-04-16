package io.sparge.server;

import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.nodes.Node;
import org.jsoup.nodes.TextNode;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * HTML issue scanner — mirrors scripts/scan_html.py.
 * 16 detectors + checkAll() + scanPost().
 */
public final class ScanHtml {

    private ScanHtml() {}

    public record Issue(String type, String level, String detail, String selector) {}

    private static final Pattern BYLINE_RE =
            Pattern.compile("^by\\s+[A-Z]", Pattern.CASE_INSENSITIVE);
    private static final Pattern URL_IN_NOSCRIPT =
            Pattern.compile("src=[\"']?(https?://[^\"'>\\s]+)");
    private static final Pattern CODE_MULTILINE_RE =
            Pattern.compile("[;{}]|when\\s+\\w|\\bthen\\b|\\bend\\b");
    private static final Pattern ENCODED_TAG_RE = Pattern.compile(
            "&lt;(?:\\?xml|table|div|p|span|ul|ol|li|section|article|h[1-6]|tr|td|th)\\b",
            Pattern.CASE_INSENSITIVE);

    // ── Helpers ───────────────────────────────────────────────────────────────

    public static String selector(Element el) {
        if (el == null) return null;
        if (el.hasAttr("id") && !el.id().isEmpty()) return "#" + el.id();
        List<String> parts = new ArrayList<>();
        Element current = el;
        for (int depth = 0; depth < 6; depth++) {
            Element parent = current.parent();
            if (parent == null) break;
            String tag = current.tagName();
            if (tag.equals("html") || tag.equals("body") || tag.equals("article")
                    || tag.equals("[document]")) break;
            List<Element> siblings = parent.children().stream()
                    .filter(e -> e.tagName().equals(tag))
                    .collect(Collectors.toList());
            if (siblings.size() > 1) {
                parts.add(tag + ":nth-of-type(" + (siblings.indexOf(current) + 1) + ")");
            } else {
                parts.add(tag);
            }
            current = parent;
        }
        if (parts.isEmpty()) return el.tagName();
        Collections.reverse(parts);
        return String.join(" > ", parts);
    }

    private static Issue issue(String type, String level, String detail, Element el) {
        return new Issue(type, level, detail, el != null ? selector(el) : null);
    }

    private static String trunc(String s, int max) {
        if (s == null) return "";
        return s.length() > max ? s.substring(0, max) : s;
    }

    private static String filename(String src) {
        try {
            String path = new java.net.URI(src).getPath();
            if (path == null) return "";
            int slash = path.lastIndexOf('/');
            return slash >= 0 ? path.substring(slash + 1) : path;
        } catch (Exception e) {
            int slash = src.lastIndexOf('/');
            return slash >= 0 ? src.substring(slash + 1) : src;
        }
    }

    // ── 16 detectors ──────────────────────────────────────────────────────────

    public static List<Issue> checkDataPlaceholders(Element article) {
        List<Issue> issues = new ArrayList<>();
        for (Element img : article.select("img")) {
            if (img.attr("src").startsWith("data:"))
                issues.add(issue("data_placeholder", "ERROR",
                        "Unrecovered lazy-load placeholder — alt=\"" + trunc(img.attr("alt"), 60) + "\"", img));
        }
        return issues;
    }

    public static List<Issue> checkNoscriptRemnants(Element article) {
        List<Issue> issues = new ArrayList<>();
        for (Element ns : article.select("noscript")) {
            Matcher m = URL_IN_NOSCRIPT.matcher(ns.outerHtml());
            if (m.find())
                issues.add(issue("noscript_remnant", "WARN",
                        "Orphaned <noscript> with image URL: " + trunc(m.group(1), 80), ns));
        }
        return issues;
    }

    public static List<Issue> checkExternalImages(Element article) {
        List<Issue> issues = new ArrayList<>();
        for (Element img : article.select("img")) {
            String src = img.attr("src");
            if (!src.startsWith("http")) continue;
            String w = img.attr("width"), h = img.attr("height");
            if ((w.equals("1") || w.equals("0")) && (h.equals("1") || h.equals("0"))) continue;
            issues.add(issue("external_image", "WARN",
                    "Image not localised: " + trunc(src, 80), img));
        }
        return issues;
    }

    public static List<Issue> checkTrackingPixels(Element article) {
        List<Issue> issues = new ArrayList<>();
        for (Element img : article.select("img")) {
            String src = img.attr("src"), w = img.attr("width"), h = img.attr("height");
            if (SpargeConstants.isTrackingPixel(src, w, h)) {
                String domain = SpargeConstants.extractDomain(src);
                issues.add(issue("tracking_pixel", "WARN",
                        "Tracking pixel from " + (domain.isEmpty() ? "unknown" : domain)
                        + ": " + trunc(src, 60), img));
            }
        }
        return issues;
    }

    public static List<Issue> checkMissingLocalImages(Element article, Path postPath, Path postsDir) {
        List<Issue> issues = new ArrayList<>();
        Path baseDir = postsDir != null
                ? postsDir.getParent().getParent()
                : postPath.getParent().getParent().getParent();
        for (Element img : article.select("img")) {
            String src = img.attr("src");
            if (!src.startsWith("../../assets/")) continue;
            String rel = src.replace("../../", "");
            if (!Files.exists(baseDir.resolve(rel)))
                issues.add(issue("missing_local_image", "ERROR",
                        "Local image file missing: " + rel, img));
        }
        return issues;
    }

    public static List<Issue> checkEmptyEmbeds(Element article) {
        List<Issue> issues = new ArrayList<>();
        for (Element iframe : article.select("iframe")) {
            String src = iframe.attr("src").strip(), dataSrc = iframe.attr("data-src").strip();
            if (src.isEmpty() && dataSrc.isEmpty()) {
                String title = iframe.attr("title");
                if (title.isEmpty()) title = iframe.classNames().stream().findFirst().orElse("iframe");
                issues.add(issue("empty_embed", "ERROR",
                        "Empty iframe (no src recovered) — title=\"" + trunc(title, 40) + "\"", iframe));
            } else if (src.isEmpty()) {
                issues.add(issue("empty_embed", "WARN",
                        "iframe has data-src but no src — needs wiring: " + trunc(dataSrc, 60), iframe));
            }
        }
        return issues;
    }

    public static List<Issue> checkUnreplacedGists(Element article) {
        List<Issue> issues = new ArrayList<>();
        for (Element script : article.select("script[src]")) {
            String src = script.attr("src");
            if (src.contains("gist.github.com"))
                issues.add(issue("unreplaced_gist", "ERROR",
                        "Gist not inlined: " + trunc(src, 80), script));
        }
        return issues;
    }

    public static List<Issue> checkWordpressChrome(Element article) {
        List<Issue> issues = new ArrayList<>();
        for (String sel : SpargeConstants.CHROME_SELECTORS) {
            for (Element el : article.select(sel)) {
                String text = el.text().strip();
                if (text.length() >= 3)
                    issues.add(issue("wordpress_chrome", "WARN",
                            "WordPress UI element in article (" + sel + "): \"" + trunc(text, 50) + "\"", el));
            }
        }
        for (Element tag : article.select("p, div, span")) {
            String text = tag.wholeText().replaceAll("\\s+", " ").strip();
            if (text.length() > 200) continue;
            for (Pattern pat : SpargeConstants.CHROME_TEXT_PATTERNS) {
                if (pat.matcher(text).find()) {
                    issues.add(issue("wordpress_chrome", "WARN",
                            "Metadata text in article: \"" + trunc(text, 60) + "\"", tag));
                    break;
                }
            }
        }
        return issues;
    }

    public static List<Issue> checkMissingImageSignals(Element article) {
        List<Issue> issues = new ArrayList<>();
        for (Element p : article.select("p, div")) {
            if (p.hasClass("missing-image")) continue;
            String text = p.text().strip();
            if (text.isEmpty() || text.length() > 300) continue;
            if (SpargeConstants.MISSING_IMG_SIGNALS.stream().noneMatch(pat -> pat.matcher(text).find())) continue;
            if (p.selectFirst("img") != null) continue;
            Element next = p.nextElementSibling();
            if (next != null) {
                if (next.tagName().equals("img") || next.tagName().equals("figure")) continue;
                if (next.selectFirst("img") != null) continue;
                if (next.hasClass("missing-image")) continue;
            }
            issues.add(issue("missing_image_signal", "WARN",
                    "Text signals missing image: \"" + trunc(text, 80) + "\"", p));
        }
        return issues;
    }

    public static List<Issue> checkMdNotationInText(Element article) {
        List<Issue> issues = new ArrayList<>();
        for (Element tag : article.select("strong, b, em, i")) {
            if (tag.parents().stream().anyMatch(p ->
                    p.tagName().equals("pre") || p.tagName().equals("code"))) continue;
            Node sib = tag.nextSibling();
            if (sib instanceof TextNode tn) {
                String text = tn.getWholeText();
                if (!text.isEmpty() && !Character.isWhitespace(text.charAt(0))) {
                    char adjacent = text.charAt(0);
                    issues.add(issue("md_notation_in_text", "WARN",
                            "<" + tag.tagName() + "> immediately followed by '" + adjacent + "' — "
                            + "html2text produces **" + trunc(tag.text(), 20) + "**" + adjacent
                            + " (no space), mismatching the HTML plain text which has a space", tag));
                }
            }
        }
        return issues;
    }

    public static List<Issue> checkSuspiciousEncodedHtml(Element article) {
        List<Issue> issues = new ArrayList<>();
        for (Element pre : article.select("pre")) {
            Element code = pre.selectFirst("code");
            if (code == null) continue;
            if (ENCODED_TAG_RE.matcher(code.outerHtml()).find())
                issues.add(issue("suspicious_code_content", "WARN",
                        "<pre><code> contains HTML-encoded markup — may be a conversion artefact "
                        + "rather than intentional code (e.g. &lt;table&gt;). "
                        + "Check original page and dismiss if intentional.", pre));
        }
        return issues;
    }

    public static List<Issue> checkLayoutSpacerImages(Element article) {
        List<Element> spacers = new ArrayList<>();
        for (Element img : article.select("img")) {
            String src = img.attr("src"), alt = img.attr("alt").strip();
            String h = img.attr("height").strip(), w = img.attr("width").strip();
            if (SpargeConstants.isTrackingPixel(src, w, h)) continue;
            if (filename(src).toLowerCase().contains("spacer") || ((h.equals("0") || h.equals("1")) && alt.isEmpty()))
                spacers.add(img);
        }
        if (spacers.isEmpty()) return List.of();
        Element first = spacers.get(0);
        return List.of(issue("layout_spacer_image", "WARN",
                spacers.size() + " layout spacer image(s) (e.g. spacer.gif "
                + first.attr("width") + "×" + first.attr("height") + "px) — no content value, safe to remove",
                first));
    }

    public static List<Issue> checkImgurImages(Element article) {
        List<Issue> issues = new ArrayList<>();
        for (Element img : article.select("img")) {
            String src = img.attr("src");
            if (src.contains("imgur.com") && !src.contains("web.archive.org"))
                issues.add(issue("imgur_image", "WARN",
                        "imgur img src — geo-blocked in some regions, replace with Wayback URL: " + trunc(src, 100), img));
        }
        for (Element a : article.select("a[href]")) {
            String href = a.attr("href");
            if (href.contains("imgur.com") && !href.contains("web.archive.org"))
                issues.add(issue("imgur_image", "WARN",
                        "imgur link href — geo-blocked in some regions, replace with Wayback URL: " + trunc(href, 100), a));
        }
        return issues;
    }

    public static List<Issue> checkLinenumberTableCode(Element article) {
        List<Issue> issues = new ArrayList<>();
        for (Element table : article.select("table")) {
            var tds = table.select("td");
            if (tds.size() < 2) continue;
            Element leftTd = tds.get(0), rightTd = tds.get(1);
            Element leftPre = leftTd.selectFirst("pre");
            boolean isA = leftPre != null && !leftPre.text().strip().isEmpty()
                    && leftPre.text().strip().chars().allMatch(c ->
                    Character.isDigit(c) || c == '\n' || c == ' ');
            boolean isB = !isA
                    && !leftTd.children().isEmpty()
                    && leftTd.children().stream().allMatch(c ->
                    c.tagName().equals("div") && c.text().strip().matches("\\d+"))
                    && rightTd.selectFirst("code, pre") != null;
            if (!isA && !isB) continue;
            Element rightCode = rightTd.selectFirst("pre, code");
            String snippet = rightCode != null ? trunc(rightCode.text(), 50) : "";
            issues.add(issue("linenumber_table_code", "WARN",
                    "Two-column line-number table — left column is line numbers, "
                    + "right column is code. Convert to <pre><code>: \"" + snippet + "\"", table));
        }
        return issues;
    }

    public static List<Issue> checkPotentialCodeBlocks(Element article) {
        List<Issue> issues = new ArrayList<>();
        for (Element p : article.select("p, div")) {
            if (p.parents().stream().anyMatch(par ->
                    par.tagName().equals("pre") || par.tagName().equals("code"))) continue;
            if (p.tagName().equals("div") && p.parent() != null
                    && p.parent().tagName().equals("article")) continue;
            if (p.selectFirst("pre") != null || p.selectFirst("br") == null) continue;
            String text = p.wholeText().replace("\u00a0", " ");
            if (text.length() < 20 || text.length() > 5000) continue;
            boolean strong = SpargeConstants.CODE_SIGNALS_STRONG.stream().anyMatch(s -> s.matcher(text).find());
            long weak = SpargeConstants.CODE_SIGNALS_WEAK.stream().filter(s -> s.matcher(text).find()).count();
            if (!strong && weak < 2) continue;
            long nonBlank = Arrays.stream(text.split("\n")).filter(l -> !l.strip().isEmpty()).count();
            if (nonBlank < 2) continue;
            double avg = Arrays.stream(text.split("\n")).filter(l -> !l.strip().isEmpty())
                    .mapToInt(String::length).average().orElse(0);
            if (avg > 80) continue;
            issues.add(issue("potential_code_block", "WARN",
                    "<p> with <br/> line breaks looks like unformatted code — "
                    + "consider wrapping in <pre><code>: \""
                    + trunc(text.replace("\n", " ").strip(), 60) + "\"", p));
        }
        return issues;
    }

    public static List<Issue> checkCodeBlockNoNewlines(Element article) {
        List<Issue> issues = new ArrayList<>();
        for (Element pre : article.select("pre")) {
            if ("true".equals(pre.attr("data-oneliner"))) continue;
            Element code = pre.selectFirst("code");
            Element target = code != null ? code : pre;
            var brs = target.select("br");
            if (brs.size() >= 2) {
                Element clone = target.clone();
                clone.select("br").forEach(br -> br.replaceWith(new TextNode("\n")));
                issues.add(issue("code_no_newlines", "WARN",
                        "<pre><code> uses <br/> for line breaks — must be converted "
                        + "to \\n at ingest/enrich time: \""
                        + trunc(clone.wholeText().replace("\n", " "), 60) + "\"", pre));
                continue;
            }
            String text = target.wholeText();
            if (text.contains("\n") || text.length() < 40) continue;
            if (!CODE_MULTILINE_RE.matcher(text).find()) continue;
            issues.add(issue("code_no_newlines", "WARN",
                    "<pre><code> content has no line breaks — likely lost during ingest "
                    + "(CMS adds <br/> at render time): \"" + trunc(text, 60) + "\"", pre));
        }
        return issues;
    }

    // ── checkAll + scanPost ────────────────────────────────────────────────────

    public static List<Issue> checkAll(Element article) {
        List<Issue> issues = new ArrayList<>();
        issues.addAll(checkDataPlaceholders(article));
        issues.addAll(checkNoscriptRemnants(article));
        issues.addAll(checkExternalImages(article));
        issues.addAll(checkTrackingPixels(article));
        issues.addAll(checkEmptyEmbeds(article));
        issues.addAll(checkUnreplacedGists(article));
        issues.addAll(checkWordpressChrome(article));
        issues.addAll(checkMissingImageSignals(article));
        issues.addAll(checkMdNotationInText(article));
        issues.addAll(checkSuspiciousEncodedHtml(article));
        issues.addAll(checkLayoutSpacerImages(article));
        issues.addAll(checkImgurImages(article));
        issues.addAll(checkLinenumberTableCode(article));
        issues.addAll(checkPotentialCodeBlocks(article));
        issues.addAll(checkCodeBlockNoNewlines(article));
        return issues;
    }

    public static List<Issue> scanPost(Path htmlPath, Path postsDir) throws IOException {
        String html = Files.readString(htmlPath);
        Document doc = Jsoup.parse(html);
        Element article = doc.selectFirst("article");
        if (article == null) article = doc.selectFirst("body");
        if (article == null)
            return List.of(issue("no_article", "ERROR",
                    "No <article> or <body> element found", null));
        for (Element tag : new ArrayList<>(article.select("p, div, span"))) {
            String text = tag.wholeText().replaceAll("\\s+", " ").strip();
            if (text.length() < 200 && BYLINE_RE.matcher(text).find()) tag.remove();
        }
        List<Issue> issues = new ArrayList<>(checkAll(article));
        issues.addAll(checkMissingLocalImages(article, htmlPath, postsDir));
        return issues;
    }
}
