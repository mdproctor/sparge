package io.sparge.server;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIf;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Integration test: scan real KIE archive HTML files.
 * Skipped when the KIE archive is not present.
 */
class ScanHtmlIntegrationTest {

    private static final Path KIE_POSTS = Paths.get(
            System.getProperty("user.home"),
            "mdproctor.github.io/legacy/posts/mark-proctor"
    );

    static boolean kieArchivePresent() {
        return Files.isDirectory(KIE_POSTS);
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void scanSinglePostReturnsValidIssueList() throws Exception {
        Path post = Files.list(KIE_POSTS)
                .filter(p -> p.toString().endsWith(".html"))
                .findFirst()
                .orElseThrow(() -> new RuntimeException("No HTML files in KIE archive"));

        List<ScanHtml.Issue> issues = ScanHtml.scanPost(post, KIE_POSTS);

        assertNotNull(issues, "scanPost must return a non-null list");
        for (ScanHtml.Issue issue : issues) {
            assertNotNull(issue.type(),   "type must not be null");
            assertNotNull(issue.level(),  "level must not be null");
            assertNotNull(issue.detail(), "detail must not be null");
            assertTrue(issue.level().equals("ERROR") || issue.level().equals("WARN"),
                    "level must be ERROR or WARN, got: " + issue.level());
        }
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void scanTenPostsAllReturnNonNullLists() throws Exception {
        List<Path> posts = Files.list(KIE_POSTS)
                .filter(p -> p.toString().endsWith(".html"))
                .limit(10)
                .toList();

        for (Path post : posts) {
            List<ScanHtml.Issue> issues = ScanHtml.scanPost(post, KIE_POSTS);
            assertNotNull(issues, "scanPost must not return null for: " + post.getFileName());
        }
    }
}
