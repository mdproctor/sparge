package io.sparge.server;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import io.quarkus.test.junit.QuarkusTest;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIf;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.*;
import static org.junit.jupiter.api.Assertions.*;

@QuarkusTest
class SearchResourceTest {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    static boolean kieArchivePresent() {
        return Files.isDirectory(Paths.get(
                System.getProperty("user.home"),
                "mdproctor.github.io/legacy/posts/mark-proctor"));
    }

    @BeforeEach
    void activateProject() {
        if (!kieArchivePresent()) return;
        // StartupActivation already activated the first project; this is a safety-net re-confirm.
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
            System.err.println("Warning: explicit project activation failed (JEP may be slow): " + e.getMessage());
        }
    }

    // ── Unit tests — filterSlugs (no HTTP, no KIE archive needed) ─────────────

    private static ObjectNode post(String slug, String title) {
        ObjectNode n = MAPPER.createObjectNode();
        n.put("slug", slug);
        n.put("title", title);
        return n;
    }

    @Test
    void filterSlugs_emptyQuery_returnsAllSlugs() {
        SearchResource r = new SearchResource();
        List<ObjectNode> posts = List.of(post("alpha", "Alpha Post"), post("beta", "Beta Post"));
        List<String> result = r.filterSlugs(posts, "", "both", null);
        assertEquals(List.of("alpha", "beta"), result);
    }

    @Test
    void filterSlugs_titleScope_matchesCaseInsensitive() {
        SearchResource r = new SearchResource();
        List<ObjectNode> posts = List.of(post("java-guide", "Java Guide"), post("python-tips", "Python Tips"));
        List<String> result = r.filterSlugs(posts, "java", "title", null);
        assertEquals(List.of("java-guide"), result);
    }

    @Test
    void filterSlugs_titleScope_doesNotMatchBody() {
        SearchResource r = new SearchResource();
        List<ObjectNode> posts = List.of(post("a", "Unrelated Title"));
        List<String> result = r.filterSlugs(posts, "quarkus", "title", null);
        assertTrue(result.isEmpty());
    }

    @Test
    void filterSlugs_noMatch_returnsEmpty() {
        SearchResource r = new SearchResource();
        List<ObjectNode> posts = List.of(post("a", "Alpha"), post("b", "Beta"));
        List<String> result = r.filterSlugs(posts, "zzznomatch", "both", null);
        assertTrue(result.isEmpty());
    }

    @Test
    void filterSlugs_bodyScope_readsMarkdownFile(@TempDir Path tmp) throws Exception {
        Files.writeString(tmp.resolve("a.md"), "# Hello Quarkus native world");
        SearchResource r = new SearchResource();
        List<ObjectNode> posts = List.of(post("a", "Unrelated Title"));
        List<String> result = r.filterSlugs(posts, "quarkus", "body", tmp);
        assertEquals(List.of("a"), result);
    }

    @Test
    void filterSlugs_bodyScope_missingMdFile_skipsPost(@TempDir Path tmp) {
        SearchResource r = new SearchResource();
        List<ObjectNode> posts = List.of(post("a", "Unrelated Title"));
        List<String> result = r.filterSlugs(posts, "quarkus", "body", tmp);
        assertTrue(result.isEmpty());
    }

    @Test
    void filterSlugs_bothScope_matchesTitle_doesNotReadBody(@TempDir Path tmp) throws Exception {
        Files.writeString(tmp.resolve("a.md"), "nothing relevant here");
        SearchResource r = new SearchResource();
        List<ObjectNode> posts = List.of(post("a", "Java Guide"));
        List<String> result = r.filterSlugs(posts, "java", "both", tmp);
        assertEquals(List.of("a"), result);
    }

    // ── E2E @QuarkusTest ───────────────────────────────────────────────────────

    @Test
    @EnabledIf("kieArchivePresent")
    void emptyQueryReturnsAllSlugs() {
        given()
                .queryParam("q",     "")
                .queryParam("scope", "both")
                .when().get("/api/search")
                .then()
                .statusCode(200)
                .body("slugs",        notNullValue())
                .body("slugs.size()", greaterThan(0));
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void defaultScopeParameterWorks() {
        given()
                .queryParam("q", "")
                .when().get("/api/search")
                .then()
                .statusCode(200)
                .body("slugs.size()", greaterThan(0));
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void unmatchedQueryReturnsEmptySlugs() {
        given()
                .queryParam("q",     "xyzzy-this-cannot-match-any-kie-title-99zz")
                .queryParam("scope", "title")
                .when().get("/api/search")
                .then()
                .statusCode(200)
                .body("slugs", hasSize(0));
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void titleSearchFindsKnownKeyword() {
        List<String> slugs = given()
                .queryParam("q",     "java")
                .queryParam("scope", "title")
                .when().get("/api/search")
                .then()
                .statusCode(200)
                .extract().jsonPath().getList("slugs", String.class);
        assertFalse(slugs.isEmpty(), "Expected at least one Java-titled post in the KIE archive");
    }
}
