package io.sparge.server;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.*;

class ScanAssetsTest {

    @Test
    void allLocalisedImagesCountedCorrectly(@TempDir Path dir) throws Exception {
        Path assetsDir = dir.resolve("assets");
        Files.createDirectories(assetsDir);
        Files.writeString(assetsDir.resolve("img1.jpg"), "fake");
        Files.writeString(assetsDir.resolve("img2.jpg"), "fake");

        Path postsDir = dir.resolve("posts").resolve("mark-proctor");
        Files.createDirectories(postsDir);
        Path postPath = postsDir.resolve("post.html");
        Files.writeString(postPath,
            "<article>" +
            "<img src=\"../../assets/img1.jpg\"/>" +
            "<img src=\"../../assets/img2.jpg\"/>" +
            "</article>");

        var result = ScanAssets.scan(postPath, postPath);

        assertEquals(2, result.total());
        assertEquals(2, result.localised());
        assertEquals(0, result.broken());
        assertTrue(result.missingLocal().isEmpty());
        assertTrue(result.external().isEmpty());
    }

    @Test
    void missingLocalImagesCountedAsBroken(@TempDir Path dir) throws Exception {
        Path assetsDir = dir.resolve("assets");
        Files.createDirectories(assetsDir);
        Files.writeString(assetsDir.resolve("img1.jpg"), "fake");

        Path postsDir = dir.resolve("posts").resolve("mark-proctor");
        Files.createDirectories(postsDir);
        Path postPath = postsDir.resolve("post.html");
        Files.writeString(postPath,
            "<article>" +
            "<img src=\"../../assets/img1.jpg\"/>" +
            "<img src=\"../../assets/missing.jpg\"/>" +
            "</article>");

        var result = ScanAssets.scan(postPath, postPath);

        assertEquals(2, result.total());
        assertEquals(1, result.localised());
        assertEquals(1, result.broken());
        assertEquals(1, result.missingLocal().size());
        assertTrue(result.missingLocal().get(0).contains("missing.jpg"));
    }

    @Test
    void externalImagesCountedAsBroken(@TempDir Path dir) throws Exception {
        Path postsDir = dir.resolve("posts").resolve("mark-proctor");
        Files.createDirectories(postsDir);
        Path postPath = postsDir.resolve("post.html");
        Files.writeString(postPath,
            "<article><img src=\"https://example.com/photo.jpg\"/></article>");

        var result = ScanAssets.scan(postPath, postPath);

        assertEquals(1, result.total());
        assertEquals(0, result.localised());
        assertEquals(1, result.broken());
        assertEquals(1, result.external().size());
        assertTrue(result.external().get(0).contains("example.com"));
    }

    @Test
    void dataUriImagesExcludedFromCount(@TempDir Path dir) throws Exception {
        Path postsDir = dir.resolve("posts").resolve("mark-proctor");
        Files.createDirectories(postsDir);
        Path postPath = postsDir.resolve("post.html");
        Files.writeString(postPath,
            "<article><img src=\"data:image/gif;base64,R0lGODlh\"/></article>");

        var result = ScanAssets.scan(postPath, postPath);
        assertEquals(0, result.total(), "data: URI images must be excluded");
    }

    @Test
    void trackingPixelExcludedFromCount(@TempDir Path dir) throws Exception {
        Path postsDir = dir.resolve("posts").resolve("mark-proctor");
        Files.createDirectories(postsDir);
        Path postPath = postsDir.resolve("post.html");
        Files.writeString(postPath,
            "<article><img src=\"https://stats.wordpress.com/g.gif\" width=\"1\" height=\"1\"/></article>");

        var result = ScanAssets.scan(postPath, postPath);
        assertEquals(0, result.total(), "tracking pixels must be excluded");
    }

    @Test
    void mixedImagesCountedCorrectly(@TempDir Path dir) throws Exception {
        Path assetsDir = dir.resolve("assets");
        Files.createDirectories(assetsDir);
        Files.writeString(assetsDir.resolve("present.jpg"), "fake");

        Path postsDir = dir.resolve("posts").resolve("mark-proctor");
        Files.createDirectories(postsDir);
        Path postPath = postsDir.resolve("post.html");
        Files.writeString(postPath,
            "<article>" +
            "<img src=\"../../assets/present.jpg\"/>" +
            "<img src=\"../../assets/missing.jpg\"/>" +
            "<img src=\"https://example.com/photo.jpg\"/>" +
            "<img src=\"data:image/gif;base64,R0\"/>" +
            "<img src=\"https://stats.wordpress.com/g.gif\" width=\"1\" height=\"1\"/>" +
            "</article>");

        var result = ScanAssets.scan(postPath, postPath);

        assertEquals(3, result.total());
        assertEquals(1, result.localised());
        assertEquals(2, result.broken());
        assertEquals(1, result.missingLocal().size());
        assertEquals(1, result.external().size());
    }

    @Test
    void articleWithNoImagesReturnsZeros(@TempDir Path dir) throws Exception {
        Path postsDir = dir.resolve("posts").resolve("mark-proctor");
        Files.createDirectories(postsDir);
        Path postPath = postsDir.resolve("post.html");
        Files.writeString(postPath, "<article><p>Text only, no images.</p></article>");

        var result = ScanAssets.scan(postPath, postPath);

        assertEquals(0, result.total());
        assertEquals(0, result.broken());
        assertEquals(0, result.localised());
    }

    @Test
    void noArticleBodyReturnsZeroResult(@TempDir Path dir) throws Exception {
        Path postPath = dir.resolve("empty.html");
        Files.writeString(postPath, "<html><head><title>empty</title></head></html>");

        var result = ScanAssets.scan(postPath, postPath);
        assertEquals(0, result.total());
    }
}
