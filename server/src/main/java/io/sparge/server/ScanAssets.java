package io.sparge.server;

import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

/**
 * Asset localisation scanner — mirrors scripts/scan_assets.py.
 */
public final class ScanAssets {

    private ScanAssets() {}

    public record Result(
            int total, int localised, int broken,
            List<String> missingLocal, List<String> external
    ) {}

    public static Result scan(Path htmlPath, Path originalPath) throws IOException {
        return scan(htmlPath, originalPath, null);
    }

    public static Result scan(Path htmlPath, Path originalPath, Path serveRoot) throws IOException {
        Path relativeBase = (originalPath != null ? originalPath : htmlPath).getParent();
        String html = Files.readString(htmlPath);
        Document doc = Jsoup.parse(html);

        Element article = doc.selectFirst("article");
        if (article == null) article = doc.selectFirst("body");
        if (article == null) return new Result(0, 0, 0, List.of(), List.of());

        List<String> missingLocal = new ArrayList<>();
        List<String> external = new ArrayList<>();
        int localised = 0;

        for (Element img : article.select("img")) {
            String src = img.attr("src");
            if (src.isEmpty() || src.startsWith("data:")) continue;
            if (SpargeConstants.isTrackingPixel(src, img.attr("width"), img.attr("height"))) continue;

            if (src.startsWith("http://") || src.startsWith("https://")) {
                external.add(src);
            } else if (src.startsWith("/")) {
                if (serveRoot != null) {
                    Path abs = serveRoot.resolve(src.substring(1));
                    if (Files.exists(abs)) localised++; else missingLocal.add(src);
                } else {
                    missingLocal.add(src);
                }
            } else {
                Path abs = relativeBase.resolve(src).normalize();
                if (Files.exists(abs)) localised++; else missingLocal.add(src);
            }
        }

        int total = localised + missingLocal.size() + external.size();
        return new Result(total, localised, total - localised,
                List.copyOf(missingLocal), List.copyOf(external));
    }
}
