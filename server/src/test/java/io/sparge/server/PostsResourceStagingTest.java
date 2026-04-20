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
class PostsResourceStagingTest {

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

    // ── stagedGet ─────────────────────────────────────────────────────────────

    @Test
    @EnabledIf("kieArchivePresent")
    void stagedGet_noStagedFile_returns404() {
        String slug = firstSlug();
        given().when().post("/api/posts/{slug}/reject-staged", slug).then().statusCode(200); // ensure clean

        given()
                .when().get("/api/posts/{slug}/staged", slug)
                .then()
                .statusCode(404);
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void stagedGet_unknownSlug_returns404() {
        given()
                .when().get("/api/posts/this-slug-does-not-exist-xyz/staged")
                .then()
                .statusCode(404);
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void stagedGet_afterStage_returnsContent() {
        String slug    = firstSlug();
        String content = "# Staged heading\n\nStaged body text.";

        given()
                .contentType("text/plain")
                .body(content)
                .when().post("/api/posts/{slug}/stage", slug)
                .then().statusCode(200);

        given()
                .when().get("/api/posts/{slug}/staged", slug)
                .then()
                .statusCode(200)
                .body(containsString("Staged heading"));

        given().when().post("/api/posts/{slug}/reject-staged", slug).then().statusCode(200);
    }

    // ── stage ─────────────────────────────────────────────────────────────────

    @Test
    @EnabledIf("kieArchivePresent")
    void stage_writesFileAndSetsStateStagedTrue() {
        String slug = firstSlug();

        given()
                .contentType("text/plain")
                .body("# Staged content")
                .when().post("/api/posts/{slug}/stage", slug)
                .then()
                .statusCode(200)
                .body("md.staged", equalTo(true))
                .body("slug",      equalTo(slug));

        given().when().post("/api/posts/{slug}/reject-staged", slug).then().statusCode(200);
    }

    // ── rejectStaged ──────────────────────────────────────────────────────────

    @Test
    @EnabledIf("kieArchivePresent")
    void rejectStaged_removesFileAndSetsStagedFalse() {
        String slug = firstSlug();

        given()
                .contentType("text/plain")
                .body("# Content to reject")
                .when().post("/api/posts/{slug}/stage", slug)
                .then().statusCode(200);

        given()
                .when().post("/api/posts/{slug}/reject-staged", slug)
                .then()
                .statusCode(200)
                .body("md.staged", equalTo(false));

        given()
                .when().get("/api/posts/{slug}/staged", slug)
                .then()
                .statusCode(404);
    }

    // ── acceptStaged ──────────────────────────────────────────────────────────

    @Test
    @EnabledIf("kieArchivePresent")
    void acceptStaged_noStagedFile_returns404() {
        String slug = firstSlug();
        given().when().post("/api/posts/{slug}/reject-staged", slug).then().statusCode(200); // ensure clean

        given()
                .when().post("/api/posts/{slug}/accept-staged", slug)
                .then()
                .statusCode(404);
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void acceptStaged_unknownSlug_returns404() {
        given()
                .when().post("/api/posts/this-slug-does-not-exist-xyz/accept-staged")
                .then()
                .statusCode(404);
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void acceptStaged_withStagedFile_acceptsAndStagedFalse() {
        String slug    = firstSlug();
        String content = "# Accepted content\n\nReady to publish.";

        given()
                .contentType("text/plain")
                .body(content)
                .when().post("/api/posts/{slug}/stage", slug)
                .then().statusCode(200);

        given()
                .when().post("/api/posts/{slug}/accept-staged", slug)
                .then()
                .statusCode(200)
                .body("md.staged",      equalTo(false))
                .body("md.generated_at", notNullValue());

        given()
                .when().get("/api/posts/{slug}/staged", slug)
                .then()
                .statusCode(404);
    }

    // ── full lifecycle ────────────────────────────────────────────────────────

    @Test
    @EnabledIf("kieArchivePresent")
    void fullLifecycle_stageGetAccept() {
        String slug    = firstSlug();
        String content = "# Full lifecycle\n\nStage → get → accept.";

        given()
                .contentType("text/plain")
                .body(content)
                .when().post("/api/posts/{slug}/stage", slug)
                .then().statusCode(200).body("md.staged", equalTo(true));

        given()
                .when().get("/api/posts/{slug}/staged", slug)
                .then().statusCode(200).body(containsString("Full lifecycle"));

        given()
                .when().post("/api/posts/{slug}/accept-staged", slug)
                .then().statusCode(200).body("md.staged", equalTo(false));

        given()
                .when().get("/api/posts/{slug}/staged", slug)
                .then().statusCode(404);
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void fullLifecycle_stageGetReject() {
        String slug    = firstSlug();
        String content = "# Reject lifecycle\n\nStage → get → reject.";

        given()
                .contentType("text/plain")
                .body(content)
                .when().post("/api/posts/{slug}/stage", slug)
                .then().statusCode(200).body("md.staged", equalTo(true));

        given()
                .when().get("/api/posts/{slug}/staged", slug)
                .then().statusCode(200).body(containsString("Reject lifecycle"));

        given()
                .when().post("/api/posts/{slug}/reject-staged", slug)
                .then().statusCode(200).body("md.staged", equalTo(false));

        given()
                .when().get("/api/posts/{slug}/staged", slug)
                .then().statusCode(404);
    }
}
