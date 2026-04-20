package io.sparge.server;

import io.quarkus.test.junit.QuarkusTest;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIf;

import java.nio.file.Files;
import java.nio.file.Paths;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.*;

@QuarkusTest
class PostsResourceConvertTest {

    static boolean kieArchivePresent() {
        return Files.isDirectory(Paths.get(
                System.getProperty("user.home"),
                "mdproctor.github.io/legacy/posts/mark-proctor"));
    }

    @BeforeEach
    void activateProject() {
        if (!kieArchivePresent()) return;
        try {
            String id = given()
                    .when().get("/api/projects")
                    .then().statusCode(200)
                    .extract().jsonPath().getString("[0].id");
            if (id != null && !id.isEmpty()) {
                given().contentType("application/json")
                        .when().post("/api/projects/{id}/activate", id)
                        .then().statusCode(200);
            }
        } catch (Exception e) {
            System.err.println("Warning: project activation failed: " + e.getMessage());
        }
    }

    private String firstSlug() {
        return given()
                .when().get("/api/posts")
                .then().statusCode(200)
                .extract().jsonPath().getString("[0].slug");
    }

    // ── html ──────────────────────────────────────────────────────────────────

    @Test
    @EnabledIf("kieArchivePresent")
    void htmlEndpointReturns200WithTextPlain() {
        String slug = firstSlug();
        given()
                .when().get("/api/posts/{slug}/html", slug)
                .then()
                .statusCode(200)
                .contentType(containsString("text/plain"));
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void htmlEndpointReturnsHtmlContent() {
        String slug = firstSlug();
        String content = given()
                .when().get("/api/posts/{slug}/html", slug)
                .then().statusCode(200)
                .extract().asString();
        assertTrue(content.contains("<") && content.contains(">"),
                "Expected HTML content but got: " + content.substring(0, Math.min(200, content.length())));
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void htmlUnknownSlugReturns404() {
        given()
                .when().get("/api/posts/this-slug-does-not-exist-xyz/html")
                .then()
                .statusCode(404);
    }

    // ── view ──────────────────────────────────────────────────────────────────

    @Test
    @EnabledIf("kieArchivePresent")
    void viewEndpointReturns200WithTextHtml() {
        String slug = firstSlug();
        given()
                .when().get("/api/posts/{slug}/view", slug)
                .then()
                .statusCode(200)
                .contentType(containsString("text/html"));
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void viewDoesNotContainArchiveHeader() {
        String slug = firstSlug();
        String html = given()
                .when().get("/api/posts/{slug}/view", slug)
                .then().statusCode(200)
                .extract().asString();
        assertFalse(html.contains("archive-header"),
                "view endpoint should strip archive-header elements");
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void viewUnknownSlugReturns404() {
        given()
                .when().get("/api/posts/this-slug-does-not-exist-xyz/view")
                .then()
                .statusCode(404);
    }

    // ── save-html ─────────────────────────────────────────────────────────────

    @Test
    @EnabledIf("kieArchivePresent")
    void saveHtmlPersistsContent() {
        String slug = firstSlug();
        String marker = "<!-- test-save-html-marker-6c -->";

        given()
                .contentType("text/plain")
                .body("<html><body>" + marker + "</body></html>")
                .when().post("/api/posts/{slug}/save-html", slug)
                .then()
                .statusCode(200)
                .body("slug", equalTo(slug));

        // Verify stored by reading view (which uses enriched-first)
        String viewContent = given()
                .when().get("/api/posts/{slug}/view", slug)
                .then().statusCode(200)
                .extract().asString();
        assertTrue(viewContent.contains(marker),
                "save-html content should be readable via view endpoint");
    }

    // ── save-md ───────────────────────────────────────────────────────────────

    @Test
    @EnabledIf("kieArchivePresent")
    void saveMdPersistsAndUpdatesState() {
        String slug = firstSlug();
        String content = "---\nlayout: post\ntitle: \"Test\"\ndate: 2024-01-01\n"
                + "author: Mark Proctor\ncategories: []\ntags: []\noriginal_url: x\n---\n\n# Test content";

        given()
                .contentType("text/plain")
                .body(content)
                .when().post("/api/posts/{slug}/save-md", slug)
                .then()
                .statusCode(200)
                .body("slug",            equalTo(slug))
                .body("md.generated_at", notNullValue());
    }

    private static void assertTrue(boolean c, String msg) { if (!c) throw new AssertionError(msg); }
    private static void assertFalse(boolean c, String msg) { if (c)  throw new AssertionError(msg); }
}
