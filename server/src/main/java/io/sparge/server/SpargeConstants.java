package io.sparge.server;

import java.net.URI;
import java.util.List;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * Shared constants mirroring scripts/constants.py.
 */
public final class SpargeConstants {

    private SpargeConstants() {}

    public static final Set<String> TRACKING_DOMAINS = Set.of(
            "stats.wordpress.com", "pixel.wp.com", "pixel.quantserve.com",
            "b.scorecardresearch.com", "beacon.krxd.net", "ad.doubleclick.net",
            "googleads.g.doubleclick.net", "google-analytics.com",
            "connect.facebook.net", "platform.twitter.com", "bat.bing.com",
            "ct.pinterest.com", "analytics.twitter.com", "px.ads.linkedin.com",
            "mc.yandex.ru", "counter.yadro.ru"
    );

    public static boolean isTrackingPixel(String src, String width, String height) {
        String domain = extractDomain(src);
        boolean isTiny = (width.strip().equals("1") || width.strip().equals("0"))
                      && (height.strip().equals("1") || height.strip().equals("0"));
        return TRACKING_DOMAINS.contains(domain) || (isTiny && src.startsWith("http"));
    }

    static String extractDomain(String src) {
        try {
            String host = URI.create(src).getHost();
            if (host == null) return "";
            return host.toLowerCase().replaceFirst("^www\\.", "");
        } catch (Exception e) {
            return "";
        }
    }

    public static final List<String> CHROME_SELECTORS = List.of(
            ".entry-header", ".entry-meta", ".author-box", ".author-description",
            ".author-info", ".addtoany_share_save_container", ".sharedaddy",
            "#comments", ".comments-area", ".jp-relatedposts", ".post-navigation",
            ".wpdiscuz-form-container", "[class*=wpDiscuz]", "[class*=addtoany]"
    );

    public static final List<Pattern> CHROME_TEXT_PATTERNS = List.of(
            Pattern.compile("^by\\s+[A-Z]", Pattern.CASE_INSENSITIVE),
            Pattern.compile("View all posts by", Pattern.CASE_INSENSITIVE),
            Pattern.compile("Post Comment", Pattern.CASE_INSENSITIVE),
            Pattern.compile("Leave a Reply", Pattern.CASE_INSENSITIVE),
            Pattern.compile("You might also like", Pattern.CASE_INSENSITIVE),
            Pattern.compile("Share this:", Pattern.CASE_INSENSITIVE)
    );

    public static final List<Pattern> MISSING_IMG_SIGNALS = List.of(
            Pattern.compile("as shown (below|above|here)", Pattern.CASE_INSENSITIVE),
            Pattern.compile("(see|view) (the )?(image|screenshot|figure|diagram|chart|graph|photo) (below|above)", Pattern.CASE_INSENSITIVE),
            Pattern.compile("(the )?(following|below) (image|screenshot|figure|diagram|chart|graph) shows?", Pattern.CASE_INSENSITIVE),
            Pattern.compile("(image|screenshot|figure|diagram|chart|graph|photo):?\\s*$", Pattern.CASE_INSENSITIVE),
            Pattern.compile("click (to )?(enlarge|zoom|view)", Pattern.CASE_INSENSITIVE)
    );

    public static final List<Pattern> CODE_SIGNALS_STRONG = List.of(
            Pattern.compile("\\brule[\\s\\u00a0]*\"", Pattern.CASE_INSENSITIVE),
            Pattern.compile("^\\s*when\\s*$", Pattern.MULTILINE),
            Pattern.compile("^\\s*then\\s*$", Pattern.MULTILINE),
            Pattern.compile("\\bpublic\\s+(class|static\\s+void|interface)\\b"),
            Pattern.compile("\\bimport\\s+[\\w.]+;"),
            Pattern.compile("<\\?xml\\b"),
            Pattern.compile("<[a-zA-Z][a-zA-Z0-9:._-]*\\b[^>]+/>")
    );

    public static final List<Pattern> CODE_SIGNALS_WEAK = List.of(
            Pattern.compile("^\\s*end\\s*$", Pattern.MULTILINE),
            Pattern.compile("\\bnew\\s+\\w+\\s*\\("),
            Pattern.compile("<[a-zA-Z][a-zA-Z0-9]*\\b[^>]*/?>"),
            Pattern.compile("[;{}]\\s*$", Pattern.MULTILINE)
    );
}
