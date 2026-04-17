package io.sparge.server;

import io.quarkus.test.junit.QuarkusTest;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIf;

import java.nio.file.Files;
import java.nio.file.Paths;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.*;

/**
 * E2E test: scanning a post triggers Java enrichment when no enriched copy exists.
 * Skipped when the KIE archive is not present.
 */
@QuarkusTest
class EnrichEndpointTest {

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
            System.err.println("Warning: could not activate project: " + e.getMessage());
        }
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void scanWithNoEnrichedCopySucceeds() {
        String slug = given()
                .when().get("/api/posts")
                .then().statusCode(200)
                .extract().jsonPath().getString("[0].slug");

        given().contentType("application/json")
                .when().post("/api/posts/" + slug + "/scan")
                .then()
                .statusCode(200)
                .body("slug", equalTo(slug))
                .body("html",   notNullValue())
                .body("assets", notNullValue());
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void scanReturnsJsonWithNoErrors() {
        String slug = given()
                .when().get("/api/posts")
                .then().statusCode(200)
                .extract().jsonPath().getString("[0].slug");

        given().contentType("application/json")
                .when().post("/api/posts/" + slug + "/scan")
                .then()
                .statusCode(200)
                .contentType(containsString("application/json"));
    }
}
